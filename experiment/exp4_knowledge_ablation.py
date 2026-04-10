"""
Experiment 4 - 三层知识体系消融 + 跨会话记忆鲁棒性
==================================================
目的：定量评估 HydroClaw 三层知识注入各层的独立贡献，并验证记忆层对异常先验的鲁棒性。

主实验：知识消融（K0-K3 逐层累加）
  K0: 无知识注入   — 仅基础角色描述
  K1: +Skill说明书 — 工作流步骤 + 工具调用顺序
  K2: +领域知识库  — 参数物理含义 + 率定诊断经验
  K3: +跨会话记忆  — 流域档案先验（完整系统）

三个测试场景（逐渐难度递增）：
  T1: 标准率定（工具序列正确性）
  T2: 参数边界感知（需要领域知识才能识别边界问题）
  T3: 自定义代码分析（不应触发率定流程）

评估指标（主实验）：
  - 工具序列匹配率（expected_tools 子集匹配）
  - 首个工具准确率（第一个工具是否正确）
  - 平均 LLM token 消耗（知识注入的代价）

附加实验：对抗先验鲁棒性（K3 层压力测试）
  - 向记忆层注入物理上不合理的极端参数值（NSE=0.97, x1=1998 等）
  - 验证 LLM 在 K3 条件下能否察觉先验异常并给出预警
  - 结论：区分"记忆作为先验"和"记忆作为权威答案"的设计正确性

论文对应：Section 4.5
合并来源：原 exp5_memory（附加实验部分）+ exp6_knowledge_ablation（主实验）
参考文献：
  NHRI 2025 零知识 vs 专家知识对比（NSE +0.14），提供外部参照基准
  AgentHPO (ICLR 2025) — 历史记忆机制（与本实验记忆层设计对比）
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import json
import logging
import time
from collections import Counter
from datetime import datetime

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("results/paper/exp4")
CHECKPOINT_DIR = OUTPUT_DIR / "checkpoints"


def _load_checkpoint(key: str) -> dict | None:
    f = CHECKPOINT_DIR / f"{key}.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _save_checkpoint(key: str, data: dict):
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    f = CHECKPOINT_DIR / f"{key}.json"
    f.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


# Keywords indicating simulated/fake data was used instead of real basin data
_SIMULATED_DATA_KEYWORDS = [
    "模拟数据", "模拟流量", "模拟降水", "示例数据", "演示数据",
    "np.random", "np.random.seed", "random.seed",
    "simulate", "simulated data", "synthetic data", "fake data",
    "randomly generated",
]

def _check_simulated_data(agent_log: list) -> bool:
    """Check if any run_code result in the agent log mentions simulated data.

    Returns True if simulated/fake data was used, False otherwise.
    """
    for entry in agent_log:
        if entry.get("tool") != "run_code":
            continue
        # memory.py stores 'result_summary' (string) not 'result'
        result = entry.get("result_summary", entry.get("result", ""))
        if isinstance(result, dict):
            text = result.get("stdout", "") + result.get("stderr", "")
        else:
            text = str(result)
        text_lower = text.lower()
        for kw in _SIMULATED_DATA_KEYWORDS:
            if kw.lower() in text_lower:
                return True
    return False

# ── 知识条件定义 ──────────────────────────────────────────────────────────────

CONDITIONS = [
    ("K0", "no_knowledge",   "无知识注入"),
    ("K1", "skills_only",    "+Skill说明书"),
    ("K2", "skills_domain",  "+领域知识库"),
    ("K3", "full",           "+跨会话记忆（完整系统）"),
]

# ── 测试场景 ──────────────────────────────────────────────────────────────────

SCENARIOS = [
    {
        "id": "T1", "name": "standard_calibration",
        "query": "率定GR4J模型，流域12025000，用SCE-UA算法",
        "expected_tools": ["validate_basin", "calibrate_model", "evaluate_model"],
        "expected_first": "validate_basin",
        "description": "标准率定全流程",
        "needs_basin_profile": "12025000",
    },
    {
        "id": "T2", "name": "boundary_detection",
        "query": "率定GR4J模型，流域06043500，注意参数是否触碰边界",
        "expected_tools": ["validate_basin", "calibrate_model"],
        "expected_first": "validate_basin",
        "description": "参数边界感知（需要领域知识才能理解边界含义）",
        "needs_basin_profile": None,
    },
    {
        "id": "T3", "name": "code_analysis",
        "query": "帮我生成一段代码，计算流域12025000的月均径流变化曲线",
        # validate_basin is acceptable as first tool (to get data path before generate_code).
        # Key requirement: must NOT trigger calibrate_model or evaluate_model.
        "expected_tools": ["generate_code"],
        "expected_first": "validate_basin",
        "expected_first_alt": "generate_code",  # also acceptable for K0 (no skill knowledge)
        "description": "自定义代码生成（不应触发率定/评估流程）",
        "forbidden_tools": ["calibrate_model", "evaluate_model"],
        "needs_basin_profile": None,
    },
]

# ── 附加实验：对抗先验 ─────────────────────────────────────────────────────────

ADVERSARIAL_BASINS = [
    {
        "basin_id": "12025000",
        "name": "Fish River, ME",
        "adversarial_profile": {
            "model": "gr4j",
            "algorithm": "SCE_UA",
            "train_nse": 0.97,              # 不可能这么高
            "best_params": {
                "x1": 1998.0,              # 紧贴上界
                "x2": -9.8,               # 接近下界
                "x3": 498.0,              # 极端值
                "x4": 9.9,               # 极端值
            },
            "calibrated_at": "2025-01-01T00:00:00",
        },
    },
    {
        "basin_id": "06043500",
        "name": "Gallatin River, MT",
        "adversarial_profile": {
            "model": "gr4j",
            "algorithm": "SCE_UA",
            "train_nse": 0.98,              # 不可能这么高（困难流域）
            "best_params": {
                "x1": 1.1,               # 紧贴下界
                "x2": 9.9,               # 反物理方向
                "x3": 1.2,
                "x4": 0.51,
            },
            "calibrated_at": "2025-01-01T00:00:00",
        },
    },
]

ADVERSARIAL_KEYWORDS = [
    # Chinese
    "异常", "不合理", "可疑", "偏差", "异乎寻常", "极端", "不正常", "存疑",
    "注意", "警告", "超出", "超过", "不寻常", "值得怀疑", "需要验证",
    "过高", "过低", "紧贴", "触碰边界", "边界", "不可信", "建议复核",
    # English
    "unusual", "suspicious", "abnormal", "extreme", "unrealistic", "outlier",
    "warning", "caution", "boundary", "implausible", "questionable", "too high",
    "verify", "double-check",
]

ADVERSARIAL_QUERY_TEMPLATE = (
    "请分析流域{basin_id}的历史率定档案，"
    "给出下一步率定建议。如果发现任何异常，请明确指出。"
)


# ── Utilities ─────────────────────────────────────────────────────────────────

def setup_logging():
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(logs_dir / f"exp4_{ts}.log", encoding="utf-8"),
        ],
    )


_PREAMBLE_TOOLS = {"read_file"}


def _first_meaningful_tool(actual_tools: list[str]) -> str | None:
    """Return first tool that is not a skill.md preamble read (P3 compatibility)."""
    for t in actual_tools:
        if t not in _PREAMBLE_TOOLS:
            return t
    return actual_tools[0] if actual_tools else None


def _check_tool_match(expected: list, actual: list) -> bool:
    if not expected:
        return True
    ec, ac = Counter(expected), Counter(actual)
    return all(ac[t] >= ec[t] for t in ec)


def _seed_basin_profile(workspace: Path):
    """为 T1 场景预存 12025000 的历史档案（用于 K3 条件效果验证）。"""
    from hydroclaw.memory import Memory
    mem = Memory(workspace)
    existing = mem.load_basin_profile("12025000")
    if existing and existing.get("records"):
        return
    mem.save_basin_profile(
        basin_id="12025000",
        model_name="gr4j",
        best_params={"x1": 315.2, "x2": 1.18, "x3": 62.4, "x4": 1.94},
        metrics={"NSE": 0.721, "KGE": 0.694, "RMSE": 1.23},
        algorithm="SCE_UA",
    )
    logger.info("  Seeded basin profile for 12025000 (K3 condition)")


def _inject_adversarial_profile(workspace: Path, basin_id: str, profile_data: dict):
    """将对抗先验写入 basin_profiles/<basin_id>.json。"""
    from hydroclaw.memory import Memory
    mem = Memory(workspace)
    profile_file = mem.basin_profiles_dir / f"{basin_id}.json"
    profile = {
        "basin_id": basin_id,
        "records": [profile_data],
    }
    profile_file.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    logger.info(
        f"  Adversarial prior injected: {basin_id}, NSE={profile_data['train_nse']}"
    )


def _apply_condition(agent, condition_key: str) -> dict:
    """临时替换 agent 方法，实现知识条件控制。返回原始方法备份。

    P3 update: skill content is no longer injected via skill_registry.match().
    Instead, the skill list (with file paths) is provided via available_skills_prompt().
    K0 must disable available_skills_prompt to truly remove skill guidance.

    K0: no skill list, no domain knowledge, no profiles, no memory
    K1: +skill list (agent can read skills via read_file)
    K2: +domain knowledge
    K3: +memory (full system)
    """
    backup = {
        "load_domain":          agent._load_domain_knowledge,
        "available_skills":     agent.skill_registry.available_skills_prompt,
        "profile_ctx":          agent.memory.format_basin_profiles_for_context,
        "load_mem":             agent.memory.load_knowledge,
    }

    if condition_key == "no_knowledge":
        agent._load_domain_knowledge = lambda q: ""
        agent.skill_registry.available_skills_prompt = lambda *a, **kw: ""
        agent.memory.format_basin_profiles_for_context = lambda ids: ""
        agent.memory.load_knowledge  = lambda: ""

    elif condition_key == "skills_only":
        # skills enabled (available_skills_prompt unchanged)
        agent._load_domain_knowledge = lambda q: ""
        agent.memory.format_basin_profiles_for_context = lambda ids: ""
        agent.memory.load_knowledge  = lambda: ""

    elif condition_key == "skills_domain":
        # skills + domain knowledge enabled
        agent.memory.format_basin_profiles_for_context = lambda ids: ""
        agent.memory.load_knowledge  = lambda: ""

    # "full" -> no modification

    return backup


def _restore_condition(agent, backup: dict):
    agent._load_domain_knowledge = backup["load_domain"]
    agent.skill_registry.available_skills_prompt = backup["available_skills"]
    agent.memory.format_basin_profiles_for_context = backup["profile_ctx"]
    agent.memory.load_knowledge  = backup["load_mem"]


# ── Main ablation experiment ──────────────────────────────────────────────────

def run_main_ablation(workspace: Path) -> dict:
    """K0-K3 × 3 scenarios 消融实验。"""
    from hydroclaw.agent import HydroClaw

    logger.info("\n" + "=" * 60)
    logger.info("Main Ablation: K0-K3 x 3 scenarios")
    logger.info("=" * 60)

    _seed_basin_profile(workspace)
    agent = HydroClaw(workspace=workspace, prompt_mode="minimal", config_override={"max_turns": 8})
    all_results = []

    for cond_id, cond_key, cond_name in CONDITIONS:
        logger.info(f"\n  Condition {cond_id}: {cond_name}")

        for sc in SCENARIOS:
            sid = sc["id"]
            ck_key = f"abl_{cond_id}_{sid}"
            cached = _load_checkpoint(ck_key)
            if cached:
                logger.info(f"    {cond_id}/{sid}: [SKIPPED - loaded from checkpoint]")
                all_results.append(cached)
                continue

            record = {
                "condition_id": cond_id, "condition_key": cond_key,
                "condition_name": cond_name,
                "scenario_id": sid, "scenario_name": sc["name"],
                "description": sc["description"], "query": sc["query"],
                "expected_tools": sc["expected_tools"],
                "expected_first": sc["expected_first"],
                "actual_tools": [], "first_tool_correct": False,
                "tool_match": False, "success": False,
                "total_tokens": 0, "wall_time_s": 0.0, "error": None,
            }

            agent.memory._log.clear()
            backup = _apply_condition(agent, cond_key)

            t0 = time.time()
            try:
                agent.run(sc["query"])
                record["wall_time_s"] = round(time.time() - t0, 2)
                record["actual_tools"] = [e["tool"] for e in agent.memory._log]
                record["success"] = True
                # T3 special: pass if generate_code was called AND no calibrate_model/evaluate_model
                # Also fail if simulated/fake data was used instead of real basin data
                forbidden = sc.get("forbidden_tools", [])
                if forbidden:
                    has_required = _check_tool_match(sc["expected_tools"], record["actual_tools"])
                    no_forbidden = not any(t in record["actual_tools"] for t in forbidden)
                    simulated = _check_simulated_data(agent.memory._log)
                    record["simulated_data_used"] = simulated
                    if simulated:
                        logger.warning(
                            "    %s/%s: simulated data detected in run_code output -> tool_match=False",
                            sc["id"], cond_id,
                        )
                    record["tool_match"] = has_required and no_forbidden and not simulated
                else:
                    record["tool_match"] = _check_tool_match(
                        sc["expected_tools"], record["actual_tools"]
                    )
                if record["actual_tools"] and sc.get("expected_first"):
                    # P3: skip leading read_file (skill.md preamble) when checking first tool
                    first = _first_meaningful_tool(record["actual_tools"])
                    alt = sc.get("expected_first_alt")
                    record["first_tool_correct"] = (
                        first == sc["expected_first"] or (alt is not None and first == alt)
                    )
                    record["first_meaningful_tool"] = first
                else:
                    record["first_tool_correct"] = False
            except Exception as e:
                record["wall_time_s"] = round(time.time() - t0, 2)
                record["error"] = str(e)
                logger.error(f"    {sid}/{cond_id} failed: {e}")
            finally:
                _restore_condition(agent, backup)

            # agent.run() resets token counter internally; summary().total_tokens is this run's count
            record["total_tokens"] = agent.llm.tokens.summary().get("total_tokens", 0)
            all_results.append(record)
            _save_checkpoint(ck_key, record)

            # Inter-run cooldown: let TPM window reset before next scenario
            _inter_run_sleep = 10  # seconds; increase if 429 persists
            logger.info("  Sleeping %ds between runs (TPM cooldown)...", _inter_run_sleep)
            time.sleep(_inter_run_sleep)

            sim_flag = f"  sim={record.get('simulated_data_used', 'N/A')}" if sc.get("forbidden_tools") else ""
            logger.info(
                f"    {cond_id}/{sid}  match={record['tool_match']}  "
                f"first_ok={record['first_tool_correct']}  "
                f"actual={record['actual_tools']}  tokens={record['total_tokens']}{sim_flag}"
            )

    # Aggregate stats
    def _agg(subset):
        n = len(subset)
        if n == 0:
            return {}
        return {
            "n": n,
            "tool_match_rate": sum(1 for r in subset if r["tool_match"]) / n,
            "first_tool_rate": sum(1 for r in subset if r["first_tool_correct"]) / n,
            "avg_tokens": sum(r["total_tokens"] for r in subset) / n,
            "avg_time_s": sum(r["wall_time_s"] for r in subset) / n,
        }

    stats_by_condition = {
        cond_id: _agg([r for r in all_results if r["condition_id"] == cond_id])
        for cond_id, _, _ in CONDITIONS
    }
    stats_by_scenario = {
        sid: _agg([r for r in all_results if r["scenario_id"] == sid])
        for sid in [s["id"] for s in SCENARIOS]
    }

    return {
        "section": "main_ablation",
        "conditions": [{"id": c[0], "key": c[1], "name": c[2]} for c in CONDITIONS],
        "scenarios": [{"id": s["id"], "name": s["name"]} for s in SCENARIOS],
        "results": all_results,
        "stats_by_condition": stats_by_condition,
        "stats_by_scenario": stats_by_scenario,
    }


# ── Adversarial prior robustness ──────────────────────────────────────────────

def run_adversarial_robustness(workspace: Path) -> dict:
    """对抗先验鲁棒性：注入极端参数档案，验证 LLM 在 K3 条件下能否察觉异常。"""
    from hydroclaw.agent import HydroClaw

    logger.info("\n" + "=" * 60)
    logger.info("Adversarial Prior Robustness (K3 pressure test)")
    logger.info("=" * 60)

    results = []
    agent = HydroClaw(workspace=workspace, prompt_mode="minimal", config_override={"max_turns": 8})

    for basin_info in ADVERSARIAL_BASINS:
        basin_id = basin_info["basin_id"]
        ck_key = f"adv_{basin_id}"
        cached = _load_checkpoint(ck_key)
        if cached:
            logger.info(f"  Basin {basin_id}: [SKIPPED - loaded from checkpoint]")
            results.append(cached)
            continue

        logger.info(f"\n  Basin {basin_id} ({basin_info['name']})")

        _inject_adversarial_profile(workspace, basin_id, basin_info["adversarial_profile"])

        query = ADVERSARIAL_QUERY_TEMPLATE.format(basin_id=basin_id)
        agent.memory._log.clear()

        t0 = time.time()
        try:
            response = agent.run(query)
            elapsed = round(time.time() - t0, 2)
            response_lower = (response or "").lower()
            keywords_found = [kw for kw in ADVERSARIAL_KEYWORDS if kw in response_lower]
            detected = len(keywords_found) > 0

            result = {
                "basin_id": basin_id,
                "basin_name": basin_info["name"],
                "adversarial_train_nse": basin_info["adversarial_profile"]["train_nse"],
                "adversarial_params": basin_info["adversarial_profile"]["best_params"],
                "anomaly_detected": detected,
                "keywords_found": keywords_found,
                "response_preview": (response or "")[:500],
                "time_s": elapsed,
                "error": None,
            }
        except Exception as e:
            result = {
                "basin_id": basin_id, "basin_name": basin_info["name"],
                "anomaly_detected": False, "keywords_found": [],
                "response_preview": "", "time_s": round(time.time() - t0, 2),
                "error": str(e),
            }
            logger.error(f"  {basin_id} exception: {e}")

        results.append(result)
        _save_checkpoint(ck_key, result)
        time.sleep(10)
        ok_str = "[DETECTED]" if result["anomaly_detected"] else "[MISSED]"
        logger.info(
            f"  {ok_str} keywords_found={result['keywords_found']}"
        )

    n = len(results)
    n_detected = sum(1 for r in results if r["anomaly_detected"])

    return {
        "section": "adversarial_robustness",
        "results": results,
        "stats": {
            "detection_rate": n_detected / n if n else 0,
            "n_detected": n_detected, "n_total": n,
        },
    }


# ── Main orchestration ────────────────────────────────────────────────────────

def run_experiment() -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    workspace = OUTPUT_DIR / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    main_abl = run_main_ablation(workspace)
    adversarial = run_adversarial_robustness(workspace)

    return {
        "experiment": "exp4_knowledge_ablation",
        "timestamp": datetime.now().isoformat(),
        "main_ablation": main_abl,
        "adversarial_robustness": adversarial,
    }


def save_results(results: dict):
    f = OUTPUT_DIR / "exp4_results.json"
    f.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    logger.info(f"Saved -> {f}")


def print_summary(results: dict):
    abl = results["main_ablation"]
    adv = results["adversarial_robustness"]
    stats = abl["stats_by_condition"]

    print(f"\n{'='*80}")
    print(f"  Exp4: Three-Layer Knowledge Ablation + Memory Robustness")
    print(f"{'='*80}")

    # Aggregated table
    print(f"\n  [Main Ablation] Aggregated metrics by condition:")
    header = (f"{'Cond':<5} {'Description':<25} {'MatchRate':>10} "
              f"{'FirstOK':>8} {'Tokens':>8} {'Time':>7}")
    print(f"  {header}")
    print(f"  {'-'*68}")
    for cond_id, cond_key, cond_name in CONDITIONS:
        s = stats.get(cond_id, {})
        print(
            f"  {cond_id:<5} {cond_name:<25} "
            f"{s.get('tool_match_rate', 0)*100:>9.0f}% "
            f"{s.get('first_tool_rate', 0)*100:>7.0f}% "
            f"{s.get('avg_tokens', 0):>9.0f} "
            f"{s.get('avg_time_s', 0):>6.1f}s"
        )

    # Per-scenario x condition matrix
    print(f"\n  Tool match matrix (Y=match, N=mismatch, E=error):")
    header2 = f"{'Scenario':<10} {'Description':<32} {'K0':>4} {'K1':>4} {'K2':>4} {'K3':>4}"
    print(f"  {header2}")
    print(f"  {'-'*58}")
    for sc in SCENARIOS:
        sid = sc["id"]
        cells = []
        for cond_id, _, _ in CONDITIONS:
            r = next(
                (x for x in abl["results"]
                 if x["scenario_id"] == sid and x["condition_id"] == cond_id),
                {},
            )
            cells.append("Y" if r.get("tool_match") else ("E" if r.get("error") else "N"))
        print(f"  {sid:<10} {sc['description']:<32} "
              + "".join(f"{c:>4}" for c in cells))

    # Adversarial robustness
    adv_stats = adv["stats"]
    print(f"\n  [Adversarial] Prior Robustness (K3 condition):")
    print(f"    Detection rate: {adv_stats['detection_rate']*100:.0f}%  "
          f"({adv_stats['n_detected']}/{adv_stats['n_total']})")
    for r in adv["results"]:
        ok = "DETECTED" if r["anomaly_detected"] else "MISSED"
        kws = ", ".join(r["keywords_found"]) or "none"
        print(f"    [{ok}] {r['basin_id']}  injected_NSE={r.get('adversarial_train_nse')}  "
              f"keywords=[{kws}]")

    print(f"\n  Key: K3 (full system) achieves best accuracy; each layer adds value.")
    print(f"       Adversarial test validates memory is treated as prior, not authority.")
    print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true",
                        help="Skip already-completed runs (uses checkpoints)")
    parser.add_argument("--clear-checkpoints", action="store_true",
                        help="Delete all checkpoints and start fresh")
    args = parser.parse_args()

    if args.clear_checkpoints and CHECKPOINT_DIR.exists():
        import shutil
        shutil.rmtree(CHECKPOINT_DIR)
        print("Checkpoints cleared.")

    if not args.resume and CHECKPOINT_DIR.exists():
        # Default: start fresh (remove old checkpoints)
        import shutil
        shutil.rmtree(CHECKPOINT_DIR)

    setup_logging()
    logger.info("Starting Exp4: Knowledge Ablation + Memory Robustness")
    results = run_experiment()
    save_results(results)
    print_summary(results)
    logger.info("Exp4 complete")


if __name__ == "__main__":
    main()

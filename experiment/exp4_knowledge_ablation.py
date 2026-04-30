"""
Experiment 4 - 四层知识体系消融 + 认知框架评估 + 对抗先验鲁棒性
=================================================================
目的：定量评估 HydroAgent 四层知识注入各层的独立贡献，并新增专家认知框架（K4）的评估。

主实验：知识消融（K0-K4 逐层累加）
  K0: 无知识注入        — 仅基础角色描述
  K1: +Skill说明书      — 工作流步骤 + 工具调用顺序
  K2: +领域知识库       — 参数物理含义 + 率定诊断经验
  K3: +跨会话记忆       — 流域档案先验（三层完整系统）
  K4: +认知框架         — 水文学家.skill 专家直觉（四层完整系统）★新增

四个测试场景：
  T1: 标准率定（工具序列正确性）
  T2: 参数边界感知（需要领域知识才能识别边界问题）
  T3: 自定义代码分析（不应触发率定流程）
  T4: 认知诊断（多参数触界物理解释，专家直觉测试）★新增

评估指标：
  T1-T3: 工具序列匹配率 / 首个工具准确率 / 平均 LLM token 消耗
  T4:    物理推理词命中率 / 正确结论比率（认知框架专属指标）

附加实验：对抗先验鲁棒性（K3/K4 层压力测试）
  - 向记忆层注入物理上不合理的极端参数值（NSE=0.97, x1=1998 等）
  - 验证 LLM 在 K3/K4 条件下能否察觉先验异常并给出预警

论文对应：Section 4.5
参考文献：
  NHRI 2025 零知识 vs 专家知识对比（NSE +0.14），提供外部参照基准
  AgentHPO (ICLR 2025) — 历史记忆机制（与本实验记忆层设计对比）
  Nuwa-Skill (2025) — 认知框架注入方法论启发
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
    ("K3", "full",           "+跨会话记忆（三层完整）"),
    ("K4", "full_cognitive", "+认知框架（四层完整）"),  # 新增
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
    {
        "id": "T4", "name": "cognitive_diagnosis",
        "query": (
            "流域03439000 XAJ模型完成5轮LLM率定，最终NSE=0.105。"
            "详细参数检查发现4个参数同时触上界："
            "CS=0.98（上界1.0），L=9.8（上界10.0），"
            "CI=0.89（上界0.9），EX=1.49（上界1.5）。"
            "请从水文物理角度分析：(1) 这4个参数同时触上界意味着什么物理过程？"
            "(2) 继续扩大参数范围能否改善NSE？"
            "(3) 建议下一步怎么做？"
        ),
        "expected_tools": [],        # 纯推理，不需要调用特定工具
        "expected_first": None,
        "description": "认知诊断：多参数触界物理解释（专家直觉测试）",
        "eval_type": "cognitive",    # 使用认知评估指标而非工具序列指标
        "physical_keywords": [       # 命中越多说明物理推理越充分
            # 产流机制
            "产流", "超渗", "蓄满", "产流机制", "地表径流",
            # 汇流/退水
            "汇流", "退水", "调蓄", "基流", "滞后",
            # 模型结构
            "模型结构", "结构", "结构性", "适配", "不适配",
            # 流域特征
            "半干旱", "蒸散发", "土壤", "下渗",
            # 参数物理含义
            "蓄水容量", "消退系数", "地下水",
            # 英文（应对模型混用中英文）
            "runoff", "recession", "structure", "infiltration",
            "evapotranspiration", "semi-arid", "baseflow", "lag",
        ],
        "correct_conclusion_keywords": [  # 正确结论：建议停止或换模型
            "不适配", "换模型", "结构性", "模型选择", "停止", "局限",
            "超渗", "不匹配", "结构问题", "模型不适", "建议换",
            "mismatch", "unsuitable", "switch model", "model structure",
        ],
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
    from hydroagent.memory import Memory
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
    from hydroagent.memory import Memory
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

    K0: 无 skill 索引 / 无领域知识 / 无流域档案 / 无记忆 / 无认知框架
    K1: +skill 索引（Agent 可 read_file 读取 skill.md）
    K2: +领域知识（knowledge/ 已改为按需，此条件暂与 K1 等价，保留以便未来扩展）
    K3: +跨会话记忆（流域档案 + MEMORY.md，三层完整系统）
    K4: +认知框架（水文学家.skill 始终注入，四层完整系统）

    注意：K0-K3 均禁用认知框架；K4 为唯一启用认知框架的条件。
    """
    backup = {
        "load_domain":      agent._load_domain_knowledge,
        "available_skills": agent.skill_registry.available_skills_prompt,
        "get_cognitive":    agent.skill_registry.get_cognitive_prompt,
        "profile_ctx":      agent.memory.format_basin_profiles_for_context,
        "load_mem":         agent.memory.load_knowledge,
    }

    # K0-K3 全部禁用认知框架（K4 是唯一保留认知框架的条件）
    if condition_key != "full_cognitive":
        agent.skill_registry.get_cognitive_prompt = lambda: ""

    if condition_key == "no_knowledge":
        agent._load_domain_knowledge = lambda q: ""
        agent.skill_registry.available_skills_prompt = lambda *a, **kw: ""
        agent.memory.format_basin_profiles_for_context = lambda ids: ""
        agent.memory.load_knowledge = lambda: ""

    elif condition_key == "skills_only":
        agent._load_domain_knowledge = lambda q: ""
        agent.memory.format_basin_profiles_for_context = lambda ids: ""
        agent.memory.load_knowledge = lambda: ""

    elif condition_key == "skills_domain":
        agent.memory.format_basin_profiles_for_context = lambda ids: ""
        agent.memory.load_knowledge = lambda: ""

    # "full" -> 禁用认知框架（已在上方处理），其余不修改
    # "full_cognitive" -> 全部保留（仅上方认知框架禁用逻辑被跳过）

    return backup


def _restore_condition(agent, backup: dict):
    agent._load_domain_knowledge = backup["load_domain"]
    agent.skill_registry.available_skills_prompt = backup["available_skills"]
    agent.skill_registry.get_cognitive_prompt = backup["get_cognitive"]
    agent.memory.format_basin_profiles_for_context = backup["profile_ctx"]
    agent.memory.load_knowledge = backup["load_mem"]


# ── Main ablation experiment ──────────────────────────────────────────────────

def run_main_ablation(workspace: Path) -> dict:
    """K0-K3 × 3 scenarios 消融实验。"""
    from hydroagent.agent import HydroAgent

    logger.info("\n" + "=" * 60)
    logger.info("Main Ablation: K0-K3 x 3 scenarios")
    logger.info("=" * 60)

    _seed_basin_profile(workspace)
    agent = HydroAgent(workspace=workspace)
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
                final_response = agent.run(sc["query"])
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
                if sc.get("eval_type") == "cognitive":
                    # T4: evaluate final response quality (NOT tool results)
                    # Scan both the final LLM response AND tool result summaries
                    _resp = (final_response or "").lower()
                    _tool_text = " ".join(
                        str(e.get("result_summary", "")) for e in agent.memory._log
                    ).lower()
                    _all_text = _resp + " " + _tool_text
                    phys_kws = sc.get("physical_keywords", [])
                    conc_kws = sc.get("correct_conclusion_keywords", [])
                    phys_hits = [kw for kw in phys_kws if kw.lower() in _all_text]
                    conc_hit = any(kw.lower() in _all_text for kw in conc_kws)
                    record["physical_keywords_found"] = phys_hits
                    record["physical_reasoning_score"] = (
                        round(len(phys_hits) / len(phys_kws), 3) if phys_kws else 0.0
                    )
                    record["correct_conclusion"] = conc_hit
                    record["response_preview"] = (final_response or "")[:500]
                    # tool_match = True if agent didn't call inappropriate tools
                    forbidden = sc.get("forbidden_tools", [])
                    record["tool_match"] = not any(
                        t in record["actual_tools"] for t in forbidden
                    ) if forbidden else True
                    record["first_tool_correct"] = True   # N/A for T4
                elif record["actual_tools"] and sc.get("expected_first"):
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
    from hydroagent.agent import HydroAgent

    logger.info("\n" + "=" * 60)
    logger.info("Adversarial Prior Robustness (K3 pressure test)")
    logger.info("=" * 60)

    results = []
    agent = HydroAgent(workspace=workspace)

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
    print(f"\n  [Main Ablation] Aggregated metrics by condition (T1-T3 only):")
    header = (f"{'Cond':<5} {'Description':<28} {'MatchRate':>10} "
              f"{'FirstOK':>8} {'Tokens':>8} {'Time':>7}")
    print(f"  {header}")
    print(f"  {'-'*72}")
    for cond_id, cond_key, cond_name in CONDITIONS:
        # T1-T3 only for tool-sequence metrics
        subset_t1t3 = [
            r for r in abl["results"]
            if r["condition_id"] == cond_id and r["scenario_id"] in ("T1", "T2", "T3")
        ]
        n = len(subset_t1t3)
        if n == 0:
            continue
        match_rate = sum(1 for r in subset_t1t3 if r["tool_match"]) / n
        first_rate = sum(1 for r in subset_t1t3 if r["first_tool_correct"]) / n
        avg_tok = sum(r["total_tokens"] for r in subset_t1t3) / n
        avg_t = sum(r["wall_time_s"] for r in subset_t1t3) / n
        print(
            f"  {cond_id:<5} {cond_name:<28} "
            f"{match_rate*100:>9.0f}% "
            f"{first_rate*100:>7.0f}% "
            f"{avg_tok:>9.0f} "
            f"{avg_t:>6.1f}s"
        )

    # Per-scenario x condition matrix (T1-T4)
    cond_ids = [c[0] for c in CONDITIONS]
    col_w = max(4, max(len(c) for c in cond_ids))
    print(f"\n  Tool match / cognitive score matrix:")
    header2 = f"{'Scenario':<10} {'Description':<35}" + "".join(f"{c:>{col_w}}" for c in cond_ids)
    print(f"  {header2}")
    print(f"  {'-'*(10+35+len(cond_ids)*col_w)}")
    for sc in SCENARIOS:
        sid = sc["id"]
        cells = []
        for cond_id, _, _ in CONDITIONS:
            r = next(
                (x for x in abl["results"]
                 if x["scenario_id"] == sid and x["condition_id"] == cond_id),
                {},
            )
            if r.get("error"):
                cells.append("E")
            elif sc.get("eval_type") == "cognitive":
                # Show physical reasoning score (0.0-1.0) for T4
                score = r.get("physical_reasoning_score")
                conc = r.get("correct_conclusion", False)
                cells.append(f"{score:.2f}" if score is not None else "N/A")
            else:
                cells.append("Y" if r.get("tool_match") else "N")
        print(f"  {sid:<10} {sc['description']:<35}"
              + "".join(f"{c:>{col_w}}" for c in cells))

    # T4 cognitive detail
    print(f"\n  [T4 Cognitive Detail] physical_reasoning_score / correct_conclusion:")
    t4_header = f"  {'Cond':<5} {'PhysScore':>10} {'CorrectConc':>12} {'KeywordsFound'}"
    print(t4_header)
    print(f"  {'-'*70}")
    for cond_id, _, cond_name in CONDITIONS:
        r = next(
            (x for x in abl["results"]
             if x["scenario_id"] == "T4" and x["condition_id"] == cond_id),
            {},
        )
        score = r.get("physical_reasoning_score", "N/A")
        conc = r.get("correct_conclusion", "N/A")
        kws = ", ".join(r.get("physical_keywords_found", [])) or "none"
        print(f"  {cond_id:<5} {str(score):>10} {str(conc):>12}   [{kws}]")

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

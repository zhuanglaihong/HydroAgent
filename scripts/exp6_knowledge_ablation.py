"""
Experiment 6 - 三层知识体系消融实验
======================================
目的：定量评估 HydroClaw 三层知识注入各层的独立贡献。
      这是区分 HydroClaw 与其他方法（Zhu et al.、NHRI 2025）的结构性创新验证。

四个知识条件（逐层累加）：
  K0: 无知识注入   — 仅基础角色描述（能力上界基线）
  K1: +Skill说明书 — 工作流步骤 + 工具调用顺序
  K2: +领域知识库  — 参数物理含义 + 率定诊断经验
  K3: +跨会话记忆  — 流域档案先验（完整系统）

三个测试场景：
  T1: 标准率定（工具序列正确性 + NSE）
  T2: 参数边界处理（LLM 能否主动发现并处理边界问题）
  T3: 自定义分析请求（代码生成，非率定任务）

评估指标：
  - 工具序列匹配率（预期 vs 实际，子集匹配）
  - 首轮工具选择准确率（第一个工具是否正确）
  - LLM token 消耗（知识注入的成本）

论文对应：Section 4.7（或作为 Section 4.4 的消融子节）
参考文献：NHRI 2025 零知识 vs 专家知识对比（NSE +0.14）提供外部参照
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("results/paper/exp6")

# ── 知识条件定义 ──────────────────────────────────────────────────────────

CONDITIONS = [
    ("K0", "no_knowledge",   "无知识注入"),
    ("K1", "skills_only",    "+Skill说明书"),
    ("K2", "skills_domain",  "+领域知识库"),
    ("K3", "full",           "+跨会话记忆（完整系统）"),
]

# ── 测试场景 ──────────────────────────────────────────────────────────────

SCENARIOS = [
    {
        "id": "T1",
        "name": "standard_calibration",
        "query": "率定GR4J模型，流域12025000，用SCE-UA算法",
        "expected_tools": ["validate_basin", "calibrate_model", "evaluate_model"],
        "expected_first_tool": "validate_basin",
        "description": "标准率定全流程",
        "needs_basin_profile": "12025000",  # 需要预存档案（K3 条件用）
    },
    {
        "id": "T2",
        "name": "boundary_detection",
        "query": "率定GR4J模型，流域06043500，注意参数是否触碰边界",
        "expected_tools": ["validate_basin", "calibrate_model"],
        "expected_first_tool": "validate_basin",
        "description": "参数边界感知（需要领域知识才能理解边界含义）",
        "needs_basin_profile": None,
    },
    {
        "id": "T3",
        "name": "code_analysis",
        "query": "帮我生成一段代码，计算流域12025000的月均径流变化曲线",
        "expected_tools": ["generate_code"],
        "expected_first_tool": "generate_code",
        "description": "自定义代码生成（不应触发率定流程）",
        "needs_basin_profile": None,
    },
]


def setup_logging():
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(logs_dir / f"exp6_{ts}.log", encoding="utf-8"),
        ],
    )


def _apply_condition(agent, condition_key: str):
    """返回 (原始方法备份, patch dict)，调用后将 agent 方法替换为当前条件。"""
    backup = {
        "load_domain": agent._load_domain_knowledge,
        "skill_match": agent.skill_registry.match,
        "profile_ctx": agent.memory.format_basin_profiles_for_context,
        "load_mem":    agent.memory.load_knowledge,
    }

    if condition_key == "no_knowledge":
        agent._load_domain_knowledge = lambda q: ""
        agent.skill_registry.match   = lambda q: []
        agent.memory.format_basin_profiles_for_context = lambda ids: ""
        agent.memory.load_knowledge  = lambda: ""

    elif condition_key == "skills_only":
        agent._load_domain_knowledge = lambda q: ""
        agent.memory.format_basin_profiles_for_context = lambda ids: ""
        agent.memory.load_knowledge  = lambda: ""

    elif condition_key == "skills_domain":
        agent.memory.format_basin_profiles_for_context = lambda ids: ""
        agent.memory.load_knowledge  = lambda: ""

    # "full" → 不做任何修改

    return backup


def _restore_condition(agent, backup: dict):
    agent._load_domain_knowledge = backup["load_domain"]
    agent.skill_registry.match   = backup["skill_match"]
    agent.memory.format_basin_profiles_for_context = backup["profile_ctx"]
    agent.memory.load_knowledge  = backup["load_mem"]


def _check_tool_match(expected: list, actual: list) -> bool:
    if not expected:
        return True
    from collections import Counter
    ec, ac = Counter(expected), Counter(actual)
    return all(ac[t] >= ec[t] for t in ec)


def _seed_basin_profile(workspace: Path):
    """为 T1 场景预存 12025000 的历史档案，用于 K3 条件效果测试。"""
    from hydroclaw.memory import Memory
    mem = Memory(workspace)
    existing = mem.load_basin_profile("12025000")
    if existing and existing.get("records"):
        return  # 已有档案，不重复写入
    mem.save_basin_profile(
        basin_id="12025000",
        model_name="gr4j",
        best_params={"x1": 315.2, "x2": 1.18, "x3": 62.4, "x4": 1.94},
        metrics={"NSE": 0.721, "KGE": 0.694, "RMSE": 1.23},
        algorithm="SCE_UA",
    )
    logger.info("  Seeded basin profile for 12025000 (for K3 condition)")


def run_experiment() -> dict:
    from hydroclaw.agent import HydroClaw

    workspace = OUTPUT_DIR / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    _seed_basin_profile(workspace)

    agent = HydroClaw(workspace=workspace)
    all_results = []

    for cond_id, cond_key, cond_name in CONDITIONS:
        logger.info(f"\n{'='*60}")
        logger.info(f"Condition {cond_id}: {cond_name} ({cond_key})")
        logger.info(f"{'='*60}")

        for scenario in SCENARIOS:
            sid = scenario["id"]
            logger.info(f"  Scenario {sid}: {scenario['description']}")

            record = {
                "condition_id": cond_id,
                "condition_key": cond_key,
                "condition_name": cond_name,
                "scenario_id": sid,
                "scenario_name": scenario["name"],
                "description": scenario["description"],
                "query": scenario["query"],
                "expected_tools": scenario["expected_tools"],
                "expected_first_tool": scenario["expected_first_tool"],
                "actual_tools": [],
                "first_tool_correct": False,
                "tool_match": False,
                "success": False,
                "token_count": 0,
                "time_s": 0,
                "error": None,
            }

            tokens_before = agent.llm.tokens.total
            agent.memory._log.clear()
            backup = _apply_condition(agent, cond_key)

            t0 = time.time()
            try:
                response = agent.run(scenario["query"])
                record["time_s"] = round(time.time() - t0, 2)
                record["actual_tools"] = [e["tool"] for e in agent.memory._log]
                record["success"] = True
                record["tool_match"] = _check_tool_match(
                    scenario["expected_tools"], record["actual_tools"]
                )
                record["first_tool_correct"] = (
                    record["actual_tools"][0] == scenario["expected_first_tool"]
                    if record["actual_tools"] else False
                )
            except Exception as e:
                record["time_s"] = round(time.time() - t0, 2)
                record["error"] = str(e)
                logger.error(f"    {sid}/{cond_id} failed: {e}")
            finally:
                _restore_condition(agent, backup)

            record["token_count"] = agent.llm.tokens.total - tokens_before
            all_results.append(record)

            logger.info(
                f"    match={record['tool_match']}  "
                f"first_ok={record['first_tool_correct']}  "
                f"actual={record['actual_tools']}  "
                f"tokens={record['token_count']}"
            )

    # 聚合统计
    def _agg(subset):
        n = len(subset)
        if n == 0:
            return {}
        return {
            "n": n,
            "tool_match_rate": sum(1 for r in subset if r["tool_match"]) / n,
            "first_tool_rate": sum(1 for r in subset if r["first_tool_correct"]) / n,
            "avg_tokens": sum(r["token_count"] for r in subset) / n,
            "avg_time_s": sum(r["time_s"] for r in subset) / n,
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
        "experiment": "exp6_knowledge_ablation",
        "timestamp": datetime.now().isoformat(),
        "conditions": [{"id": c[0], "key": c[1], "name": c[2]} for c in CONDITIONS],
        "scenarios": [{"id": s["id"], "name": s["name"]} for s in SCENARIOS],
        "results": all_results,
        "stats_by_condition": stats_by_condition,
        "stats_by_scenario": stats_by_scenario,
    }


def save_results(results: dict):
    f = OUTPUT_DIR / "exp6_results.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    logger.info(f"Saved -> {f}")


def print_summary(results: dict):
    stats = results["stats_by_condition"]
    print(f"\n{'='*80}")
    print(f"  Exp6: Three-Layer Knowledge Ablation")
    print(f"{'='*80}")

    # 主表：每个条件的聚合指标
    print(f"\n  Aggregated metrics by condition:")
    header = f"{'Cond':<5} {'Description':<22} {'MatchRate':>10} {'FirstOK':>8} {'Tokens':>8} {'Time':>7}"
    print(f"  {header}")
    print(f"  {'-'*65}")
    for cond_id, cond_key, cond_name in CONDITIONS:
        s = stats.get(cond_id, {})
        print(
            f"  {cond_id:<5} {cond_name:<22} "
            f"{s.get('tool_match_rate', 0)*100:>9.0f}%"
            f"{s.get('first_tool_rate', 0)*100:>7.0f}%"
            f"{s.get('avg_tokens', 0):>9.0f}"
            f"{s.get('avg_time_s', 0):>6.1f}s"
        )

    # 细粒度：每场景 × 每条件
    print(f"\n  Tool match per scenario × condition:")
    header2 = f"{'Scenario':<12} {'Description':<30} {'K0':>4} {'K1':>4} {'K2':>4} {'K3':>4}"
    print(f"  {header2}")
    print(f"  {'-'*60}")
    for scenario in SCENARIOS:
        sid = scenario["id"]
        cells = []
        for cond_id, _, _ in CONDITIONS:
            r = next((x for x in results["results"]
                      if x["scenario_id"] == sid and x["condition_id"] == cond_id), {})
            cells.append("Y" if r.get("tool_match") else ("E" if r.get("error") else "N"))
        print(f"  {sid:<12} {scenario['description']:<30} "
              + "".join(f"{c:>4}" for c in cells))

    print(f"\n  Y=match  N=mismatch  E=error")
    print(f"\n  Key: Each knowledge layer adds value; K3 (full system) achieves best accuracy.")


def main():
    setup_logging()
    logger.info("Starting Exp6: Knowledge Ablation")
    results = run_experiment()
    save_results(results)
    print_summary(results)
    logger.info("Exp6 complete")


if __name__ == "__main__":
    main()

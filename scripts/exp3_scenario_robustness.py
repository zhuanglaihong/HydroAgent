"""
Experiment 3 - 自然语言鲁棒性测试
==================================
目的：验证 HydroClaw Agentic 工作流对多样化自然语言查询的泛化能力。
方法：12 个场景 × 2 个知识注入条件，通过完整 HydroClaw.run() 对话驱动。

知识注入条件（对应 Exp6 消融实验的预实验）：
  - full_knowledge:  完整三层知识（Skill说明书 + 领域知识库 + 跨会话记忆）
  - no_knowledge:    仅基础角色描述，禁用所有知识注入

评估：工具序列匹配率（预期 vs 实际），中英文处理能力，残缺信息处理能力

论文对应：Section 4.4
参考文献：NHRI 2025（零知识 vs 专家知识对比提供参照基准）
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("results/paper/exp3")

# ── 测试场景定义 ────────────────────────────────────────────────────────────
# expected_tools 采用"必须出现"语义（子集匹配），空列表 = 任意结果均可接受

SCENARIOS = [
    # 标准率定
    {
        "id": "S01", "category": "standard_calibration",
        "query": "请帮我率定GR4J模型，流域12025000",
        "expected_tools": ["validate_basin", "calibrate_model", "evaluate_model"],
        "description": "完整信息标准率定",
    },
    {
        "id": "S02", "category": "calibration_with_algo_params",
        "query": "用SCE-UA算法率定XAJ模型，流域03439000，迭代500轮",
        "expected_tools": ["validate_basin", "calibrate_model", "evaluate_model"],
        "description": "指定算法参数（迭代轮数）",
    },
    # 多模型/多流域
    {
        "id": "S03", "category": "model_comparison",
        "query": "对比GR4J和XAJ在流域12025000上的率定性能",
        "expected_tools": ["create_task_list", "calibrate_model", "update_task"],
        "description": "多模型对比（Agent 应自驱动规划任务列表）",
    },
    {
        "id": "S04", "category": "batch_multi_basin",
        "query": "批量率定流域12025000和03439000，使用GR4J模型",
        "expected_tools": ["create_task_list", "get_pending_tasks", "calibrate_model", "update_task"],
        "description": "多流域批量率定（Agent 应自主创建任务列表并逐步执行）",
    },
    # LLM 智能率定
    {
        "id": "S05", "category": "llm_calibration",
        "query": "用AI智能率定GR4J模型，流域06043500，目标NSE 0.75",
        "expected_tools": ["validate_basin", "llm_calibrate"],
        "description": "LLM 智能参数范围调整",
    },
    # 自定义分析（不涉及流域数据验证）
    {
        "id": "S06", "category": "code_analysis",
        "query": "帮我计算流域12025000的径流系数，并画FDC曲线",
        "expected_tools": ["generate_code", "run_code"],
        "description": "代码生成 + 执行（应跳过 validate_basin）",
    },
    # 残缺信息处理
    {
        "id": "S07", "category": "missing_model",
        "query": "帮我率定流域12025000",
        "expected_tools": ["validate_basin", "calibrate_model"],
        "description": "缺模型名称，应使用默认模型",
    },
    {
        "id": "S08", "category": "missing_basin",
        "query": "率定GR4J模型",
        "expected_tools": [],
        "description": "缺流域ID，系统应询问或报错",
    },
    # 英文查询
    {
        "id": "S09", "category": "english_query",
        "query": "Calibrate GR4J model for basin 12025000 using SCE-UA algorithm",
        "expected_tools": ["validate_basin", "calibrate_model", "evaluate_model"],
        "description": "英文查询，验证双语能力",
    },
    # 隐含意图
    {
        "id": "S10", "category": "implicit_intent",
        "query": "流域06043500的GR4J率定效果不好，参数可能碰到了边界",
        "expected_tools": ["llm_calibrate"],
        "description": "隐含意图：参数边界问题 → 应触发 LLM 智能率定",
    },
    # 仅评估（不重新率定）
    {
        "id": "S11", "category": "eval_only",
        "query": "评估一下 results/paper/exp1/gr4j_12025000 这个率定结果的测试期表现",
        "expected_tools": ["evaluate_model"],
        "description": "仅评估，不率定（应跳过 calibrate_model）",
    },
    # 动态 Skill 创建
    {
        "id": "S12", "category": "skill_creation",
        "query": "我需要一个参数敏感性分析工具，帮我创建一个",
        "expected_tools": ["create_skill"],
        "description": "动态 Skill 生成（应跳过率定流程）",
    },
]

KNOWLEDGE_CONDITIONS = ["full_knowledge", "no_knowledge"]


def setup_logging():
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(logs_dir / f"exp3_{ts}.log", encoding="utf-8"),
        ],
    )


def _run_with_knowledge_condition(agent, query: str, condition: str) -> str:
    """在指定知识注入条件下运行 agent。

    通过临时替换 agent 内部方法实现条件控制，实验结束后还原。
    """
    if condition == "full_knowledge":
        return agent.run(query)

    # no_knowledge：禁用 Skill说明书 + 领域知识 + 跨会话记忆
    orig_domain  = agent._load_domain_knowledge
    orig_match   = agent.skill_registry.match
    orig_profile = agent.memory.format_basin_profiles_for_context
    orig_mem     = agent.memory.load_knowledge

    try:
        agent._load_domain_knowledge = lambda q: ""
        agent.skill_registry.match   = lambda q: []
        agent.memory.format_basin_profiles_for_context = lambda ids: ""
        agent.memory.load_knowledge  = lambda: ""
        return agent.run(query)
    finally:
        agent._load_domain_knowledge = orig_domain
        agent.skill_registry.match   = orig_match
        agent.memory.format_basin_profiles_for_context = orig_profile
        agent.memory.load_knowledge  = orig_mem


def _check_tool_match(expected: list, actual: list) -> bool:
    """子集匹配：expected 中每个工具都出现在 actual 中即通过。"""
    if not expected:
        return True
    from collections import Counter
    ec, ac = Counter(expected), Counter(actual)
    return all(ac[t] >= ec[t] for t in ec)


def run_experiment() -> dict:
    from hydroclaw.agent import HydroClaw

    workspace = OUTPUT_DIR / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    agent = HydroClaw(workspace=workspace)
    all_results = []

    for condition in KNOWLEDGE_CONDITIONS:
        logger.info(f"\n{'='*60}")
        logger.info(f"Knowledge condition: {condition}")
        logger.info(f"{'='*60}")

        for scenario in SCENARIOS:
            sid = scenario["id"]
            logger.info(f"  Scenario {sid}: {scenario['description']}")

            record = {
                "id": sid,
                "category": scenario["category"],
                "description": scenario["description"],
                "query": scenario["query"],
                "condition": condition,
                "expected_tools": scenario["expected_tools"],
                "actual_tools": [],
                "match": False,
                "success": False,
                "response_preview": "",
                "time_s": 0,
                "error": None,
            }

            agent.memory._log.clear()
            t0 = time.time()
            try:
                response = _run_with_knowledge_condition(agent, scenario["query"], condition)
                record["time_s"] = round(time.time() - t0, 2)
                record["actual_tools"] = [e["tool"] for e in agent.memory._log]
                record["response_preview"] = (response or "")[:400]
                record["success"] = True
                record["match"] = _check_tool_match(
                    scenario["expected_tools"], record["actual_tools"]
                )
            except Exception as e:
                record["time_s"] = round(time.time() - t0, 2)
                record["error"] = str(e)
                logger.error(f"    {sid} failed: {e}")

            all_results.append(record)
            logger.info(
                f"    match={record['match']} actual={record['actual_tools']}"
            )

    token_summary = agent.llm.tokens.summary()

    # 按条件聚合
    def _stats(results_subset):
        n = len(results_subset)
        ok = sum(1 for r in results_subset if r["match"])
        return {"n": n, "match": ok, "match_rate": ok / n if n else 0}

    stats = {
        cond: _stats([r for r in all_results if r["condition"] == cond])
        for cond in KNOWLEDGE_CONDITIONS
    }

    return {
        "experiment": "exp3_scenario_robustness",
        "timestamp": datetime.now().isoformat(),
        "n_scenarios": len(SCENARIOS),
        "conditions": KNOWLEDGE_CONDITIONS,
        "results": all_results,
        "stats_by_condition": stats,
        "token_usage": token_summary,
    }


def save_results(results: dict):
    f = OUTPUT_DIR / "exp3_results.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    logger.info(f"Saved -> {f}")


def print_summary(results: dict):
    data = results["results"]
    stats = results["stats_by_condition"]

    print(f"\n{'='*90}")
    print(f"  Exp3: Natural Language Robustness  ({len(SCENARIOS)} scenarios × {len(KNOWLEDGE_CONDITIONS)} conditions)")
    print(f"{'='*90}")

    for cond, s in stats.items():
        print(f"  [{cond:<15}]  match {s['match']}/{s['n']}  ({s['match_rate']*100:.0f}%)")

    print(f"\n  Per-scenario breakdown (full_knowledge vs no_knowledge):")
    header = f"{'ID':<5} {'Category':<28} {'full':>6} {'none':>6} {'Expected tools (subset)'}"
    print(f"  {header}")
    print(f"  {'-'*80}")

    for scenario in SCENARIOS:
        sid = scenario["id"]
        for_full = next((r for r in data if r["id"] == sid and r["condition"] == "full_knowledge"), {})
        for_none = next((r for r in data if r["id"] == sid and r["condition"] == "no_knowledge"), {})
        mk = lambda r: ("Y" if r.get("match") else "N") if r.get("success") else "ERR"
        exp_str = " + ".join(scenario["expected_tools"][:3]) or "(any)"
        print(f"  {sid:<5} {scenario['category']:<28} {mk(for_full):>6} {mk(for_none):>6}  {exp_str}")

    # 按类别分析
    print(f"\n  Match rate by category (full_knowledge):")
    from collections import defaultdict
    cat_stats: dict = defaultdict(lambda: {"n": 0, "ok": 0})
    for r in data:
        if r["condition"] == "full_knowledge":
            cat_stats[r["category"]]["n"] += 1
            if r["match"]:
                cat_stats[r["category"]]["ok"] += 1
    for cat, s in sorted(cat_stats.items()):
        rate = s["ok"] / s["n"] * 100 if s["n"] else 0
        print(f"    {cat:<30} {s['ok']}/{s['n']} ({rate:.0f}%)")

    tokens = results.get("token_usage", {})
    print(f"\n  LLM: {tokens.get('calls', 0)} calls, {tokens.get('total_tokens', 0)} tokens")


def main():
    setup_logging()
    logger.info("Starting Exp3: Natural Language Robustness")
    results = run_experiment()
    save_results(results)
    print_summary(results)
    logger.info("Exp3 complete")


if __name__ == "__main__":
    main()

"""
Author: HydroClaw Team
Date: 2026-02-09
Description: Experiment 3 - Multi-scenario robustness test.
             Tests LLM decision-making across diverse query types,
             validates skill matching and tool call sequences.
             Uses full HydroClaw.run() dialogue (requires LLM API).
FilePath: /HydroAgent/scripts/exp3_scenario_robustness.py
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("results/paper/exp3")

# ── Test scenarios: query + expected tool sequence ─────────────────────

SCENARIOS = [
    {
        "id": "S01",
        "category": "standard_calibration",
        "query": "请帮我率定GR4J模型，流域01013500",
        "expected_tools": ["validate_basin", "calibrate_model", "evaluate_model", "visualize"],
        "description": "Standard calibration with model and basin specified",
    },
    {
        "id": "S02",
        "category": "calibration_with_params",
        "query": "用SCE-UA算法率定XAJ模型，流域03439000，迭代500轮",
        "expected_tools": ["validate_basin", "calibrate_model", "evaluate_model", "visualize"],
        "description": "Calibration with explicit algorithm parameters",
    },
    {
        "id": "S03",
        "category": "multi_model_comparison",
        "query": "对比GR4J和XAJ在流域01013500上的率定性能",
        "expected_tools": ["validate_basin", "calibrate_model", "evaluate_model",
                           "calibrate_model", "evaluate_model"],
        "description": "Multi-model comparison on single basin",
    },
    {
        "id": "S04",
        "category": "batch_multi_basin",
        "query": "批量率定流域01013500和03439000，使用GR4J模型",
        "expected_tools": ["validate_basin", "calibrate_model", "evaluate_model",
                           "calibrate_model", "evaluate_model"],
        "description": "Batch calibration across multiple basins",
    },
    {
        "id": "S05",
        "category": "llm_calibration",
        "query": "用AI智能率定GR4J模型，流域06043500",
        "expected_tools": ["validate_basin", "llm_calibrate", "evaluate_model", "visualize"],
        "description": "LLM-guided iterative calibration",
    },
    {
        "id": "S06",
        "category": "analysis_code_gen",
        "query": "帮我计算流域01013500的径流系数，并画FDC曲线",
        "expected_tools": ["generate_code", "run_code"],
        "description": "Custom analysis with code generation",
    },
    {
        "id": "S07",
        "category": "incomplete_info",
        "query": "帮我率定流域01013500",
        "expected_tools": ["validate_basin", "calibrate_model", "evaluate_model"],
        "description": "Missing model name - system should use default (xaj)",
    },
    {
        "id": "S08",
        "category": "incomplete_info",
        "query": "率定GR4J模型",
        "expected_tools": [],
        "description": "Missing basin ID - system should ask or report error",
    },
    {
        "id": "S09",
        "category": "english_query",
        "query": "Calibrate GR4J model for basin 01013500 using SCE-UA algorithm",
        "expected_tools": ["validate_basin", "calibrate_model", "evaluate_model", "visualize"],
        "description": "English language query",
    },
    {
        "id": "S10",
        "category": "iterative_optimization",
        "query": "率定GR4J模型，流域06043500，如果参数触碰边界就扩展范围重新率定",
        "expected_tools": ["validate_basin", "calibrate_model", "evaluate_model"],
        "description": "Iterative optimization with boundary detection",
    },
    {
        "id": "S11",
        "category": "stability_test",
        "query": "用不同随机种子重复率定GR4J模型3次，流域01013500",
        "expected_tools": ["validate_basin", "calibrate_model", "calibrate_model", "calibrate_model"],
        "description": "Repeated calibration for stability analysis",
    },
    {
        "id": "S12",
        "category": "tool_creation",
        "query": "我需要一个参数敏感性分析工具，帮我创建一个",
        "expected_tools": ["create_tool"],
        "description": "Dynamic tool creation",
    },
]


def setup_logging():
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    log_file = logs_dir / f"exp3_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )


def run_experiment() -> dict:
    """Run all scenarios through HydroClaw.run() and record tool call sequences."""
    from hydroclaw.agent import HydroClaw

    workspace = OUTPUT_DIR / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    agent = HydroClaw(workspace=workspace)
    results = []

    for scenario in SCENARIOS:
        sid = scenario["id"]
        logger.info(f"{'='*60}")
        logger.info(f"Scenario {sid}: {scenario['description']}")
        logger.info(f"Query: {scenario['query']}")
        logger.info(f"{'='*60}")

        record = {
            "id": sid,
            "category": scenario["category"],
            "query": scenario["query"],
            "description": scenario["description"],
            "expected_tools": scenario["expected_tools"],
            "actual_tools": [],
            "success": False,
            "match": False,
            "response_preview": "",
            "time_s": 0,
            "error": None,
        }

        # Reset memory tool log to capture this scenario's calls
        agent.memory._log.clear()

        try:
            t0 = time.time()
            response = agent.run(scenario["query"])
            record["time_s"] = round(time.time() - t0, 2)

            # Extract actual tool calls from memory log
            record["actual_tools"] = [
                entry["tool"] for entry in agent.memory._log
            ]
            record["response_preview"] = (response or "")[:500]
            record["success"] = True

            # Check if actual tools match expected (order-independent subset check)
            record["match"] = _check_tool_match(
                scenario["expected_tools"], record["actual_tools"]
            )

        except Exception as e:
            logger.error(f"Scenario {sid} failed: {e}", exc_info=True)
            record["error"] = str(e)
            record["time_s"] = round(time.time() - t0, 2)

        results.append(record)
        logger.info(
            f"Scenario {sid}: success={record['success']}, match={record['match']}, "
            f"tools={record['actual_tools']}"
        )

    # Token usage summary
    token_summary = agent.llm.tokens.summary()

    return {
        "experiment": "exp3_scenario_robustness",
        "timestamp": datetime.now().isoformat(),
        "total_scenarios": len(SCENARIOS),
        "results": results,
        "token_usage": token_summary,
        "success_rate": sum(1 for r in results if r["success"]) / len(results),
        "match_rate": sum(1 for r in results if r["match"]) / len(results),
    }


def _check_tool_match(expected: list[str], actual: list[str]) -> bool:
    """Check if actual tool calls satisfy the expected sequence.

    Uses a flexible matching strategy:
    - All expected tools should appear in actual (order-independent)
    - Empty expected means any result is acceptable (e.g., error handling)
    """
    if not expected:
        return True  # No specific expectation

    # Check that each expected tool appears at least as many times in actual
    from collections import Counter
    expected_counts = Counter(expected)
    actual_counts = Counter(actual)

    for tool, count in expected_counts.items():
        if actual_counts.get(tool, 0) < count:
            return False
    return True


def save_results(results: dict):
    output_file = OUTPUT_DIR / "exp3_results.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"Results saved to {output_file}")


def print_summary(results: dict):
    print(f"\n{'='*80}")
    print(f"  Experiment 3: Scenario Robustness Test")
    print(f"  Success: {results['success_rate']*100:.0f}%  |  "
          f"Tool Match: {results['match_rate']*100:.0f}%")
    print(f"{'='*80}\n")

    header = f"{'ID':<5} {'Category':<25} {'Match':>6} {'Expected Tools':<40} {'Actual Tools'}"
    print(header)
    print("-" * 110)

    for r in results["results"]:
        match_str = "Y" if r["match"] else "N"
        if not r["success"]:
            match_str = "ERR"

        expected_str = " -> ".join(r["expected_tools"][:4]) or "(any)"
        if len(r["expected_tools"]) > 4:
            expected_str += "..."
        actual_str = " -> ".join(r["actual_tools"][:4]) or "(none)"
        if len(r["actual_tools"]) > 4:
            actual_str += f"... (+{len(r['actual_tools'])-4})"

        print(f"{r['id']:<5} {r['category']:<25} {match_str:>6} {expected_str:<40} {actual_str}")

    # Category success rates
    print(f"\nPer-category results:")
    categories = {}
    for r in results["results"]:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"total": 0, "match": 0}
        categories[cat]["total"] += 1
        if r["match"]:
            categories[cat]["match"] += 1

    for cat, stats in categories.items():
        rate = stats["match"] / stats["total"] * 100
        print(f"  {cat:<30} {stats['match']}/{stats['total']} ({rate:.0f}%)")

    # Token usage
    tokens = results.get("token_usage", {})
    print(f"\nLLM usage: {tokens.get('calls', 0)} calls, "
          f"{tokens.get('total_tokens', 0)} tokens total")


def main():
    setup_logging()
    logger.info("Starting Experiment 3: Scenario Robustness Test")
    results = run_experiment()
    save_results(results)
    print_summary(results)
    logger.info("Experiment 3 complete")


if __name__ == "__main__":
    main()

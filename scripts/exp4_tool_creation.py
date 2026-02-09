"""
Author: HydroClaw Team
Date: 2026-02-09
Description: Experiment 4 - Dynamic tool creation demonstration.
             Shows that create_tool can extend system capabilities at runtime.
             Uses full HydroClaw.run() dialogue (requires LLM API).
FilePath: /HydroAgent/scripts/exp4_tool_creation.py
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("results/paper/exp4")


# ── Tool creation scenarios ───────────────────────────────────────────

TOOL_SCENARIOS = [
    {
        "id": "T01",
        "query": (
            "我需要一个参数敏感性分析工具。它应该对率定好的模型参数逐个做扰动（±10%, ±20%），"
            "然后重新模拟，记录NSE的变化，输出每个参数的敏感性排序。"
            "工具名叫 sensitivity_analysis，包装 hydromodel 的 evaluate 功能。"
        ),
        "tool_name": "sensitivity_analysis",
        "description": "Parameter sensitivity analysis tool",
        "verify_schema_keys": ["calibration_dir", "perturbation_pcts"],
    },
    {
        "id": "T02",
        "query": (
            "帮我创建一个基流分离工具，名叫 baseflow_separation。"
            "它读取流域的日径流数据，用数字滤波法（Lyne-Hollick）分离基流和地表径流，"
            "返回基流指数（BFI）和分离后的时间序列。"
        ),
        "tool_name": "baseflow_separation",
        "description": "Baseflow separation using digital filter",
        "verify_schema_keys": ["basin_ids"],
    },
]


def setup_logging():
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    log_file = logs_dir / f"exp4_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )


def run_experiment() -> dict:
    """Test dynamic tool creation via HydroClaw dialogue."""
    from hydroclaw.agent import HydroClaw

    workspace = OUTPUT_DIR / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    results = []

    for scenario in TOOL_SCENARIOS:
        sid = scenario["id"]
        tool_name = scenario["tool_name"]
        logger.info(f"{'='*60}")
        logger.info(f"Scenario {sid}: Create tool '{tool_name}'")
        logger.info(f"{'='*60}")

        # Clean up any previously created tool file
        tool_file = Path("hydroclaw/tools") / f"{tool_name}.py"
        if tool_file.exists():
            tool_file.unlink()
            logger.info(f"Cleaned up existing {tool_file}")

        record = {
            "id": sid,
            "tool_name": tool_name,
            "description": scenario["description"],
            "query": scenario["query"],
            "success": False,
            "tool_created": False,
            "tool_file_exists": False,
            "schema_valid": False,
            "generated_code": None,
            "schema": None,
            "tool_calls": [],
            "response_preview": "",
            "time_s": 0,
            "error": None,
        }

        agent = HydroClaw(workspace=workspace)
        agent.memory._log.clear()

        try:
            t0 = time.time()
            response = agent.run(scenario["query"])
            record["time_s"] = round(time.time() - t0, 2)

            record["tool_calls"] = [
                entry["tool"] for entry in agent.memory._log
            ]
            record["response_preview"] = (response or "")[:500]
            record["success"] = True

            # Check if tool file was created
            record["tool_file_exists"] = tool_file.exists()
            if tool_file.exists():
                record["generated_code"] = tool_file.read_text(encoding="utf-8")
                record["tool_created"] = True

            # Check if tool is discoverable
            from hydroclaw.tools import reload_tools, fn_to_schema
            tools = reload_tools()
            if tool_name in tools:
                schema = fn_to_schema(tools[tool_name])
                record["schema"] = schema
                record["schema_valid"] = schema is not None

        except Exception as e:
            logger.error(f"Scenario {sid} failed: {e}", exc_info=True)
            record["error"] = str(e)

        results.append(record)

        # Clean up: remove the created tool file to avoid polluting the codebase
        if tool_file.exists():
            tool_file.unlink()
            logger.info(f"Cleaned up {tool_file}")

        logger.info(
            f"Scenario {sid}: created={record['tool_created']}, "
            f"schema_valid={record['schema_valid']}"
        )

    # Reload tools to clean state
    from hydroclaw.tools import reload_tools
    reload_tools()

    return {
        "experiment": "exp4_tool_creation",
        "timestamp": datetime.now().isoformat(),
        "total_scenarios": len(TOOL_SCENARIOS),
        "results": results,
        "success_rate": sum(1 for r in results if r["tool_created"]) / len(results),
    }


def save_results(results: dict):
    output_file = OUTPUT_DIR / "exp4_results.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"Results saved to {output_file}")


def print_summary(results: dict):
    print(f"\n{'='*80}")
    print(f"  Experiment 4: Dynamic Tool Creation")
    print(f"  Success: {results['success_rate']*100:.0f}%")
    print(f"{'='*80}\n")

    for r in results["results"]:
        print(f"--- {r['id']}: {r['tool_name']} ---")
        print(f"  Created: {r['tool_created']}")
        print(f"  Schema valid: {r['schema_valid']}")
        print(f"  Tool calls: {' -> '.join(r['tool_calls'])}")
        print(f"  Time: {r['time_s']}s")

        if r["schema"]:
            fn_schema = r["schema"].get("function", {})
            params = fn_schema.get("parameters", {}).get("properties", {})
            print(f"  Schema parameters: {list(params.keys())}")

        if r["generated_code"]:
            lines = r["generated_code"].split("\n")
            # Show first few lines and function signature
            print(f"  Code: {len(lines)} lines")
            for line in lines:
                if line.strip().startswith("def "):
                    print(f"    {line.strip()}")
                    break

        if r["error"]:
            print(f"  Error: {r['error']}")
        print()


def main():
    setup_logging()
    logger.info("Starting Experiment 4: Tool Creation")
    results = run_experiment()
    save_results(results)
    print_summary(results)
    logger.info("Experiment 4 complete")


if __name__ == "__main__":
    main()

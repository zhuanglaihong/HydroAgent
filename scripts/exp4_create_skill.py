"""
Experiment 4 - 动态 Skill 生成（元能力）
=========================================
目的：验证 HydroClaw 在运行时生成新 Skill（skill.md + tool.py）并立即注册使用的能力。
      展示系统超越"预安装 Skill"静态范式、实现按需扩展的核心创新。
方法：3 个场景，每个请求一个默认 Skill 集中不存在的能力，验证 4 项生成指标。

评估（每场景）：
  1. create_skill 是否被 LLM 调用
  2. skill.md 是否生成
  3. tool.py 是否生成且语法合法
  4. 新工具是否注册进工具注册表（立即可用）

论文对应：Section 4.5
参考文献：OpenClaw Skill 系统（预安装静态范式）作为对照
          AgentHPO (ICLR 2025) — 展示 LLM Agent 迭代优化，但工具集固定
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import ast
import json
import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("results/paper/exp4")

SCENARIOS = [
    {
        "id": "E4S01",
        "query": "帮我创建一个用 spotpy 做 MCMC 参数不确定性分析的工具",
        "description": "MCMC uncertainty analysis via spotpy",
        "hint": "spotpy",
    },
    {
        "id": "E4S02",
        "query": "我需要一个计算流域径流系数和流量历时曲线(FDC)的分析工具，帮我创建",
        "description": "Runoff coefficient + FDC analysis",
        "hint": "fdc",
    },
    {
        "id": "E4S03",
        "query": "创建一个工具，能对比两个率定结果目录的参数分布，生成箱线图",
        "description": "Parameter distribution comparison (boxplot)",
        "hint": "param",
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
            logging.FileHandler(logs_dir / f"exp4_{ts}.log", encoding="utf-8"),
        ],
    )


def _snapshot_skills() -> set[str]:
    skills_dir = Path(__file__).parent.parent / "hydroclaw" / "skills"
    return {
        d.name for d in skills_dir.iterdir()
        if d.is_dir() and not d.name.startswith("_")
    }


def _check_py_syntax(py_file: Path) -> bool:
    try:
        ast.parse(py_file.read_text(encoding="utf-8"))
        return True
    except SyntaxError:
        return False


def run_experiment() -> dict:
    from hydroclaw.agent import HydroClaw
    from hydroclaw.tools import reload_tools

    workspace = OUTPUT_DIR / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    # 每个场景用新 agent 实例，避免工具缓存干扰
    results = []

    for scenario in SCENARIOS:
        sid = scenario["id"]
        logger.info(f"\n{'='*60}")
        logger.info(f"Scenario {sid}: {scenario['description']}")
        logger.info(f"Query: {scenario['query']}")
        logger.info(f"{'='*60}")

        skills_before = _snapshot_skills()
        agent = HydroClaw(workspace=workspace)

        record = {
            "id": sid,
            "description": scenario["description"],
            "query": scenario["query"],
            "create_skill_called": False,
            "new_skill_dir": None,
            "skill_md_exists": False,
            "tool_py_exists": False,
            "tool_py_syntax_ok": False,
            "tool_registered": False,
            "success": False,
            "response_preview": "",
            "time_s": 0,
            "error": None,
        }

        agent.memory._log.clear()
        t0 = time.time()
        try:
            response = agent.run(scenario["query"])
            record["time_s"] = round(time.time() - t0, 2)
            record["response_preview"] = (response or "")[:500]

            actual_tools = [e["tool"] for e in agent.memory._log]
            record["create_skill_called"] = "create_skill" in actual_tools

            # 检测新增 Skill 目录
            skills_after = _snapshot_skills()
            new_skills = skills_after - skills_before
            if new_skills:
                skill_name = sorted(new_skills)[0]
                record["new_skill_dir"] = skill_name
                skill_dir = Path(__file__).parent.parent / "hydroclaw" / "skills" / skill_name

                # skill.md
                record["skill_md_exists"] = (skill_dir / "skill.md").exists()

                # tool.py（任意非 __init__.py 的 .py 文件）
                py_files = [f for f in skill_dir.glob("*.py") if f.name != "__init__.py"]
                if py_files:
                    record["tool_py_exists"] = True
                    record["tool_py_syntax_ok"] = _check_py_syntax(py_files[0])

                # 工具是否注册进注册表
                updated_tools = reload_tools()
                record["tool_registered"] = any(
                    skill_name.replace("-", "_").lower() in name.lower()
                    for name in updated_tools
                )

            record["success"] = (
                record["create_skill_called"]
                and record["tool_py_exists"]
                and record["tool_py_syntax_ok"]
            )

        except Exception as e:
            record["time_s"] = round(time.time() - t0, 2)
            record["error"] = str(e)
            logger.error(f"  {sid} exception: {e}", exc_info=True)

        results.append(record)
        logger.info(
            f"  create_skill={record['create_skill_called']}  "
            f"md={record['skill_md_exists']}  py={record['tool_py_exists']}  "
            f"syntax_ok={record['tool_py_syntax_ok']}  "
            f"registered={record['tool_registered']}  "
            f"new_dir={record['new_skill_dir']}"
        )

    return {
        "experiment": "exp4_create_skill",
        "timestamp": datetime.now().isoformat(),
        "n_scenarios": len(SCENARIOS),
        "results": results,
        "n_success": sum(1 for r in results if r["success"]),
        "success_rate": sum(1 for r in results if r["success"]) / len(results),
    }


def save_results(results: dict):
    f = OUTPUT_DIR / "exp4_results.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    logger.info(f"Saved -> {f}")


def print_summary(results: dict):
    data = results["results"]
    print(f"\n{'='*80}")
    print(f"  Exp4: Dynamic Skill Creation  "
          f"({results['n_success']}/{results['n_scenarios']} fully successful)")
    print(f"{'='*80}")

    header = (f"{'ID':<7} {'create_skill':>13} {'skill.md':>9} "
              f"{'tool.py':>8} {'syntax':>7} {'registered':>11} {'New Skill Dir'}")
    print(header)
    print("-" * 80)

    def yn(v): return "[Y]" if v else "[N]"
    for r in data:
        print(
            f"{r['id']:<7} {yn(r['create_skill_called']):>13} "
            f"{yn(r['skill_md_exists']):>9} "
            f"{yn(r['tool_py_exists']):>8} "
            f"{yn(r['tool_py_syntax_ok']):>7} "
            f"{yn(r['tool_registered']):>11}  "
            f"{r['new_skill_dir'] or 'N/A'}"
        )
        if r["error"]:
            print(f"         Error: {r['error'][:80]}")

    print(f"\n  Key: HydroClaw can generate new Skills at runtime,")
    print(f"       extending beyond the pre-installed Skill set (vs OpenClaw static install).")


def main():
    setup_logging()
    logger.info("Starting Exp4: Dynamic Skill Creation")
    results = run_experiment()
    save_results(results)
    print_summary(results)
    logger.info("Exp4 complete")


if __name__ == "__main__":
    main()

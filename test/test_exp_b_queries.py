"""
Author: Claude
Date: 2025-12-28
LastEditTime: 2025-12-28
LastEditors: Claude
Description: 逐个测试 Experiment B 的查询 (单元测试模式)
FilePath: /HydroAgent/test/test_exp_b_queries.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

用法:
    # 测试单个查询
    python test/test_exp_b_queries.py --query 1 --backend api --mock

    # 测试多个查询
    python test/test_exp_b_queries.py --query 1,2,3 --backend api --mock

    # 测试某一类查询
    python test/test_exp_b_queries.py --category simple --backend api --mock

    # 运行所有查询
    python test/test_exp_b_queries.py --all --backend api --mock
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import logging
from datetime import datetime
import json
import io

# 设置stdout编码为UTF-8（解决Windows控制台emoji显示问题）
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Setup logging
logs_dir = Path(__file__).parent.parent / "logs"
logs_dir.mkdir(exist_ok=True)

log_file = logs_dir / f"test_exp_b_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


# ============================================================================
# Experiment B 测试集: 15个查询 (按类别组织)
# ============================================================================

TEST_QUERIES = {
    # ========== Simple Mode - 简单顺序执行 ==========
    1: {
        "category": "simple",
        "query": "率定GR4J模型，流域14325000，然后评估性能",
        "expected_tools": 4,  # 工具系统: validate → calibrate → evaluate → visualize
        "expected_mode": "simple",
        "description": "基础率定+自动评估"
    },

    2: {
        "category": "simple",
        "query": "率定XAJ模型，流域11532500，完成后绘制水文过程线",
        "expected_tools": 4,  # validate → calibrate → evaluate → visualize (绘图已包含在visualize中)
        "expected_mode": "simple",
        "description": "率定+扩展分析(绘图)"
    },

    3: {
        "category": "simple",
        "query": "率定GR4J模型流域14325000，评估后生成性能报告代码",
        "expected_tools": 5,  # validate → calibrate → evaluate → visualize → code_generation
        "expected_mode": "simple",
        "description": "率定+代码生成"
    },

    4: {
        "category": "simple",
        "query": "验证流域11532500数据，然后率定GR4J模型，再评估",
        "expected_tools": 4,  # validate → calibrate → evaluate → visualize
        "expected_mode": "simple",
        "description": "数据验证+率定"
    },

    # ========== Iterative Mode - 迭代优化 ==========
    5: {
        "category": "iterative",
        "query": "率定GR4J模型流域14325000，如果NSE低于0.7则调整参数范围重新率定，直到达标",
        "expected_tools": 4,  # validate → calibrate → evaluate → visualize
        "expected_mode": "iterative",  # 内部迭代
        "description": "NSE阈值触发迭代"
    },

    6: {
        "category": "iterative",
        "query": "率定XAJ模型流域11532500，检测参数边界收敛，如果有问题则自动调整并重新率定",
        "expected_tools": 4,  # validate → calibrate → evaluate → visualize
        "expected_mode": "iterative",
        "description": "边界检测迭代"
    },

    7: {
        "category": "iterative",
        "query": "率定GR4J模型流域14325000，迭代优化直到NSE≥0.65，最多3次",
        "expected_tools": 3,  # validate → calibrate → evaluate 
        "expected_mode": "iterative",
        "description": "限定迭代次数"
    },

    8: {
        "category": "iterative",
        "query": "率定XAJ模型流域11532500，如果参数收敛到边界则调整范围重新率定，最多2次",
        "expected_tools": 4,  # validate → calibrate → evaluate → visualize
        "expected_mode": "iterative",
        "description": "边界迭代+次数限制"
    },

    # ========== Repeated Mode - 重复实验 ==========
    9: {
        "category": "repeated",
        "query": "重复率定GR4J模型流域14325000共3次，统计性能指标",
        "expected_tools": 4,  # validate → calibrate → evaluate → visualize
        "expected_mode": "repeated",  # 重复模式，n_repeats=3
        "description": "重复3次+统计"
    },

    10: {
        "category": "repeated",
        "query": "重复率定XAJ模型流域11532500共5次，分析参数稳定性",
        "expected_tools": 4,  # validate → calibrate → evaluate → visualize
        "expected_mode": "repeated",  # n_repeats=5
        "description": "重复5次+稳定性分析"
    },

    11: {
        "category": "repeated",
        "query": "对流域14325000重复执行GR4J率定2次，计算平均性能",
        "expected_tools": 4,  # validate → calibrate → evaluate → visualize
        "expected_mode": "repeated",  # n_repeats=2
        "description": "重复2次+平均"
    },

    12: {
        "category": "repeated",
        "query": "重复率定XAJ模型流域11532500共3次，评估算法收敛性",
        "expected_tools": 4,  # validate → calibrate → evaluate → visualize
        "expected_mode": "repeated",  # n_repeats=3
        "description": "重复3次+收敛性"
    },

    # ========== Parallel/Batch - 并行批量处理 ==========
    13: {
        "category": "batch",
        "query": "批量率定流域14325000,11532500,02070000，使用GR4J模型，分别评估性能",
        "expected_tools": 4,  # validate → calibrate → evaluate → visualize (批量执行)
        "expected_mode": "simple",  # 批量任务仍是simple模式
        "description": "3流域批量率定"
    },

    14: {
        "category": "batch",
        "query": "批量率定3个流域（14325000,11532500,02070000），使用XAJ模型，完成后计算各流域的径流系数",
        "expected_tools": 5,  # validate → calibrate → evaluate → visualize → custom_analysis
        "expected_mode": "simple",
        "description": "批量率定+聚合分析"
    },

    15: {
        "category": "batch",
        "query": "对流域14325000,11532500使用GR4J和XAJ两个模型分别率定并对比性能",
        "expected_tools": 4,  # validate → calibrate → evaluate → visualize
        "expected_mode": "simple",
        "description": "多流域×多模型"
    },
}


def test_single_query(query_id: int, backend: str = "api", use_mock: bool = True):
    """
    测试单个查询。

    Args:
        query_id: 查询ID (1-15)
        backend: LLM后端
        use_mock: 是否使用mock模式

    Returns:
        测试结果字典
    """
    if query_id not in TEST_QUERIES:
        logger.error(f"❌ 无效的查询ID: {query_id} (有效范围: 1-15)")
        return None

    query_info = TEST_QUERIES[query_id]
    query = query_info["query"]
    category = query_info["category"]
    expected_tools = query_info.get("expected_tools", 0)  # 工具系统：预期工具数
    expected_mode = query_info.get("expected_mode", "simple")  # 工具系统：预期执行模式
    description = query_info["description"]

    logger.info("=" * 80)
    logger.info(f"🧪 测试查询 #{query_id} ({category.upper()})")
    logger.info("=" * 80)
    logger.info(f"查询: {query}")
    logger.info(f"描述: {description}")
    logger.info(f"预期工具数: {expected_tools}")
    logger.info(f"预期执行模式: {expected_mode}")
    logger.info(f"后端: {backend}, Mock: {use_mock}")
    logger.info("=" * 80)

    try:
        # Import here to avoid circular imports
        from experiment.base_experiment import create_experiment

        # Create experiment
        exp = create_experiment(
            exp_name=f"test_query_{query_id}",
            exp_description=f"Test Query {query_id}: {description}"
        )

        # Run single query (use run_batch with single-item list)
        logger.info("\n🚀 开始执行...")
        results = exp.run_batch(
            queries=[query],
            backend=backend,
            use_mock=use_mock,
            use_tool_system=True  # expB requires tool system
        )

        # Get the single result
        result = results[0] if results else {"success": False, "error": "No result returned"}

        # Analyze result
        logger.info("\n📊 分析结果...")

        success = result.get("success", False)
        task_plan = result.get("task_plan", {})
        subtasks = task_plan.get("subtasks", []) if task_plan else []
        actual_subtasks = len(subtasks)

        # Check basin_ids format
        intent_result = result.get("intent_result", {})
        basin_ids = intent_result.get("basin_ids")
        has_basin_id = "basin_id" in intent_result  # Should not exist!

        # 🆕 Extract tool chain information (for expB validation)
        # Handle API failures where task_plan might be None
        if task_plan is None:
            logger.warning(f"⚠️ task_plan is None (likely due to API failure), skipping detailed checks")
            tool_chain_info = []
            execution_mode = "N/A (API failed)"
            tool_names = []
            actual_tool_count = 0
        else:
            tool_chain_info = task_plan.get("tool_chain", [])
            execution_mode = task_plan.get("execution_mode", "N/A")
            tool_names = [tool.get("tool") for tool in tool_chain_info if isinstance(tool, dict)]
            actual_tool_count = len(tool_names)

        logger.info(f"\n✅ 基础检查:")
        logger.info(f"  - 执行状态: {'✅ 成功' if success else '❌ 失败'}")
        logger.info(f"  - 工具数量: {actual_tool_count} (预期: {expected_tools})")
        logger.info(f"  - 子任务数: {actual_subtasks} (legacy)")
        logger.info(f"  - basin_ids: {basin_ids}")
        logger.info(f"  - ❌ basin_id存在: {has_basin_id} (应该是False)")

        # 🆕 显示工具链信息（实验B核心验证点）
        logger.info(f"\n🔧 工具链信息 (Experiment B 核心验证点):")
        logger.info(f"  - 执行模式: {execution_mode} (预期: {expected_mode})")
        logger.info(f"  - 工具数量: {actual_tool_count} (预期: {expected_tools})")
        logger.info(f"  - 工具链: {' → '.join(tool_names) if tool_names else 'N/A'}")

        # Detailed checks (工具系统验证)
        checks = {
            "execution_success": success,
            "tool_count_match": actual_tool_count >= expected_tools,  # 至少包含预期的工具数
            "execution_mode_match": execution_mode == expected_mode,  # 执行模式匹配
            "basin_ids_is_array": isinstance(basin_ids, list) if basin_ids else False,
            "no_basin_id_field": not has_basin_id,  # basin_id should NOT exist
            "has_tool_chain": len(tool_names) > 0,  # 🆕 验证工具链存在
        }

        all_passed = all(checks.values())

        logger.info(f"\n📋 详细检查:")
        for check_name, passed in checks.items():
            status = "✅" if passed else "❌"
            logger.info(f"  {status} {check_name}")

        # Show tool chain details
        if tool_chain_info:
            logger.info(f"\n🔧 工具链详情:")
            for i, tool in enumerate(tool_chain_info, 1):
                tool_name = tool.get("tool", "N/A")
                tool_desc = tool.get("description", "N/A")
                required = "✓ Required" if tool.get("required", True) else "○ Optional"
                logger.info(f"  {i}. {tool_name}: {tool_desc} [{required}]")

        # Show subtasks (legacy, may be empty for tool system)
        if subtasks:
            logger.info(f"\n📝 生成的子任务:")
            for i, subtask in enumerate(subtasks, 1):
                logger.info(f"  {i}. {subtask.get('task_type', 'N/A')}: {subtask.get('description', 'N/A')}")

        # Show errors if failed
        if not success:
            error = result.get("error", "Unknown error")
            logger.error(f"\n❌ 错误信息: {error}")

        # Final verdict
        logger.info("\n" + "=" * 80)
        if all_passed:
            logger.info(f"✅ 查询 #{query_id} 测试通过!")
        else:
            logger.warning(f"⚠️  查询 #{query_id} 测试未通过，请检查上述问题")
        logger.info("=" * 80)

        return {
            "query_id": query_id,
            "query": query,
            "category": category,
            "description": description,
            "success": success,
            "all_checks_passed": all_passed,
            "checks": checks,
            "actual_subtasks": actual_subtasks,  # legacy
            # 🆕 工具链信息 (Experiment B 核心验证数据)
            "execution_mode": execution_mode,
            "expected_mode": expected_mode,
            "tool_chain": tool_names,
            "tool_count": actual_tool_count,
            "expected_tools": expected_tools,
            "result": result
        }

    except Exception as e:
        logger.error(f"❌ 测试查询 #{query_id} 时发生异常: {str(e)}", exc_info=True)
        return {
            "query_id": query_id,
            "query": query,
            "category": category,
            "success": False,
            "all_checks_passed": False,
            "error": str(e)
        }


def test_category(category: str, backend: str = "api", use_mock: bool = True):
    """
    测试某一类别的所有查询。

    Args:
        category: 类别名 (simple/iterative/repeated/batch)
        backend: LLM后端
        use_mock: 是否使用mock模式

    Returns:
        测试结果列表
    """
    query_ids = [qid for qid, info in TEST_QUERIES.items() if info["category"] == category]

    if not query_ids:
        logger.error(f"❌ 无效的类别: {category} (有效值: simple/iterative/repeated/batch)")
        return []

    logger.info(f"\n🎯 测试类别: {category.upper()}")
    logger.info(f"包含查询: {query_ids}")

    results = []
    for query_id in query_ids:
        result = test_single_query(query_id, backend, use_mock)
        results.append(result)
        print()  # Add spacing between tests

    return results


def test_all_queries(backend: str = "api", use_mock: bool = True):
    """
    测试所有15个查询。

    Args:
        backend: LLM后端
        use_mock: 是否使用mock模式

    Returns:
        测试结果列表
    """
    logger.info("\n🎯 测试所有15个查询")

    results = []
    for query_id in sorted(TEST_QUERIES.keys()):
        result = test_single_query(query_id, backend, use_mock)
        results.append(result)
        print()  # Add spacing between tests

    return results


def print_summary(results: list):
    """打印测试总结。"""
    print("\n" + "=" * 80)
    print("📊 测试总结")
    print("=" * 80)

    total = len(results)
    passed = sum(1 for r in results if r and r.get("all_checks_passed", False))
    failed = total - passed

    print(f"\n总计: {total} 个查询")
    print(f"  ✅ 通过: {passed}")
    print(f"  ❌ 失败: {failed}")
    print(f"  成功率: {passed/total*100:.1f}%")

    # Group by category
    categories = {}
    for r in results:
        if not r:
            continue
        cat = r.get("category", "unknown")
        if cat not in categories:
            categories[cat] = {"total": 0, "passed": 0}
        categories[cat]["total"] += 1
        if r.get("all_checks_passed", False):
            categories[cat]["passed"] += 1

    print("\n按类别统计:")
    for cat, stats in categories.items():
        rate = stats["passed"] / stats["total"] * 100 if stats["total"] > 0 else 0
        print(f"  {cat.upper()}: {stats['passed']}/{stats['total']} ({rate:.1f}%)")

    # 🆕 工具链统计（Experiment B 核心数据）
    print("\n🔧 工具链编排统计:")
    execution_modes = {}
    tool_usage = {}
    for r in results:
        if not r:
            continue

        # 统计执行模式
        mode = r.get("execution_mode", "N/A")
        execution_modes[mode] = execution_modes.get(mode, 0) + 1

        # 统计工具使用
        for tool in r.get("tool_chain", []):
            tool_usage[tool] = tool_usage.get(tool, 0) + 1

    print("  执行模式分布:")
    for mode, count in sorted(execution_modes.items()):
        print(f"    - {mode}: {count} 次")

    print("  工具使用频率:")
    for tool, count in sorted(tool_usage.items(), key=lambda x: -x[1]):
        print(f"    - {tool}: {count} 次")

    # Show failed queries
    failed_queries = [r for r in results if r and not r.get("all_checks_passed", False)]
    if failed_queries:
        print("\n❌ 失败的查询:")
        for r in failed_queries:
            qid = r.get("query_id", "?")
            query = r.get("query", "N/A")[:60]
            print(f"  #{qid}: {query}...")

    print("=" * 80)
    print(f"📁 日志文件: {log_file}")
    print("=" * 80)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="逐个测试 Experiment B 的查询",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 测试单个查询
  python test/test_exp_b_queries.py --query 1 --backend api --mock

  # 测试多个查询
  python test/test_exp_b_queries.py --query 1,2,3 --backend api --mock

  # 测试某一类查询
  python test/test_exp_b_queries.py --category simple --backend api --mock

  # 运行所有查询
  python test/test_exp_b_queries.py --all --backend api --mock
        """
    )

    parser.add_argument(
        "--query",
        type=str,
        help="要测试的查询ID (1-15)，可用逗号分隔多个，如: 1,2,3"
    )
    parser.add_argument(
        "--category",
        type=str,
        choices=["simple", "iterative", "repeated", "batch"],
        help="要测试的查询类别"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="测试所有15个查询"
    )
    parser.add_argument(
        "--backend",
        type=str,
        default="api",
        choices=["api", "ollama"],
        help="LLM后端 (默认: api)"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        default=True,
        help="使用mock模式 (默认: True)"
    )
    parser.add_argument(
        "--no-mock",
        dest="mock",
        action="store_false",
        help="使用真实hydromodel执行"
    )

    args = parser.parse_args()

    # Validate arguments
    if not any([args.query, args.category, args.all]):
        parser.error("必须指定 --query, --category, 或 --all 之一")

    print("=" * 80)
    print("🧪 Experiment B 查询测试工具")
    print("=" * 80)
    print(f"配置: Backend={args.backend}, Mock={args.mock}")
    print("=" * 80)

    results = []

    # Execute tests
    if args.all:
        results = test_all_queries(args.backend, args.mock)
    elif args.category:
        results = test_category(args.category, args.backend, args.mock)
    elif args.query:
        query_ids = [int(qid.strip()) for qid in args.query.split(",")]
        for query_id in query_ids:
            result = test_single_query(query_id, args.backend, args.mock)
            results.append(result)
            if len(query_ids) > 1:
                print()  # Add spacing between tests

    # Print summary
    if len(results) > 1:
        print_summary(results)

    # Exit code
    all_passed = all(r and r.get("all_checks_passed", False) for r in results)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

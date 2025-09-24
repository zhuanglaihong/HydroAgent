"""
测试Executor可视化功能
"""

import json
import logging
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from executor.main import ExecutorEngine


def test_visualization():
    """测试可视化功能"""
    print("Executor 可视化功能测试")
    print("=" * 50)

    # 创建执行引擎
    engine = ExecutorEngine(enable_debug=True)

    # 创建测试工作流
    test_workflow = {
        "workflow_id": "test_visualization",
        "name": "可视化测试工作流",
        "mode": "react",
        "tasks": [
            {
                "task_id": "prepare",
                "name": "数据准备",
                "type": "simple",
                "tool_name": "prepare_data",
                "parameters": {
                    "data_dir": "data/test",
                    "format": "csv"
                },
                "description": "准备测试数据"
            },
            {
                "task_id": "analysis",
                "name": "数据分析",
                "type": "simple",
                "tool_name": "get_model_params",
                "parameters": {
                    "model_type": "GR4J"
                },
                "dependencies": ["prepare"],
                "description": "分析数据特征"
            }
        ],
        "target": {
            "type": "performance_goal",
            "metric": "accuracy",
            "comparison": ">=",
            "threshold": 0.8,
            "max_iterations": 2,
            "description": "准确率达到80%以上"
        },
        "global_settings": {
            "error_handling": "continue_on_error",
            "timeout": 300,
            "retry_count": 1
        }
    }

    # 执行工作流并生成可视化
    workflow_json = json.dumps(test_workflow, ensure_ascii=False, indent=2)

    print("执行工作流...")
    result, report_path = engine.execute_workflow_with_visualization(
        workflow_json,
        mode="react",
        generate_visualization=True
    )

    print(f"\n执行结果:")
    print(f"状态: {result.status}")
    print(f"任务数量: {len(result.task_results)}")
    print(f"React迭代: {len(result.react_iterations)}")
    print(f"目标达成: {result.target_achieved}")

    if report_path:
        print(f"\n[SUCCESS] 可视化报告已生成: {report_path}")

        # 检查输出目录
        output_dir = Path("output/visualizations")
        if output_dir.exists():
            files = list(output_dir.glob("*.html"))
            print(f"生成的文件数: {len(files)}")
            for file in files:
                print(f"  - {file.name}")

        print("\n[INFO] 可以在浏览器中打开生成的HTML文件查看可视化结果")
    else:
        print("\n[FAIL] 可视化报告生成失败")

    return report_path is not None


def main():
    """主函数"""
    # 设置日志级别
    logging.basicConfig(level=logging.INFO)

    # 创建数据目录
    Path("data/test").mkdir(parents=True, exist_ok=True)

    # 执行测试
    success = test_visualization()

    if success:
        print("\n[SUCCESS] 可视化功能测试通过!")
    else:
        print("\n[FAIL] 可视化功能测试失败!")

    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
"""
Executor使用示例 - 展示如何使用新架构执行工作流并生成可视化结果
"""

import json
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from executor.main import ExecutorEngine


def main():
    """主函数示例"""
    print("Executor 使用示例")
    print("=" * 50)

    # 创建执行引擎
    engine = ExecutorEngine(enable_debug=False)
    print("✓ 执行引擎初始化完成")

    # 创建水文模型率定工作流示例
    calibration_workflow = {
        "workflow_id": "hydro_calibration_example",
        "name": "水文模型率定示例",
        "mode": "react",
        "tasks": [
            {
                "task_id": "data_prep",
                "name": "数据准备",
                "type": "simple",
                "tool_name": "prepare_data",
                "parameters": {
                    "data_dir": "data/example_basin",
                    "format": "csv",
                    "variables": ["precipitation", "evaporation", "streamflow"]
                },
                "description": "准备水文模型所需的输入数据"
            },
            {
                "task_id": "model_setup",
                "name": "模型配置",
                "type": "simple",
                "tool_name": "get_model_params",
                "parameters": {
                    "model_type": "GR4J",
                    "basin_area": 1250.5
                },
                "dependencies": ["data_prep"],
                "description": "获取GR4J模型的默认参数配置"
            },
            {
                "task_id": "intelligent_calibration",
                "name": "智能率定",
                "type": "complex",
                "description": "使用先进算法对GR4J模型进行智能率定，自动选择最优参数，确保NSE指标达到0.8以上",
                "parameters": {
                    "model_type": "GR4J",
                    "data_source": "${data_prep.output.data_path}",
                    "param_config": "${model_setup.output.parameters}",
                    "optimization_method": "adaptive"
                },
                "dependencies": ["data_prep", "model_setup"],
                "knowledge_query": "GR4J模型智能率定最佳实践和高效优化策略"
            }
        ],
        "target": {
            "type": "performance_goal",
            "metric": "NSE",
            "comparison": ">=",
            "threshold": 0.8,
            "max_iterations": 3,
            "description": "NSE指标达到0.8以上"
        },
        "global_settings": {
            "error_handling": "continue_on_error",
            "timeout": 1800,  # 30分钟
            "retry_count": 1
        }
    }

    print("✓ 工作流定义创建完成")

    # 执行工作流并生成可视化
    workflow_json = json.dumps(calibration_workflow, ensure_ascii=False, indent=2)

    print("\n开始执行工作流...")
    print("注意：由于没有实际的数据和模型，任务可能会失败，但会展示完整的执行流程")

    result, report_path = engine.execute_workflow_with_visualization(
        workflow_json,
        mode="react",
        generate_visualization=True
    )

    print(f"\n执行结果汇总:")
    print(f"工作流ID: {result.workflow_id}")
    print(f"执行状态: {result.status.value}")
    print(f"任务总数: {len(result.task_results)}")

    if hasattr(result, 'metrics'):
        print(f"成功率: {result.metrics.success_rate:.1%}")

    if result.react_iterations:
        print(f"React迭代次数: {len(result.react_iterations)}")
        print(f"目标达成: {'是' if result.target_achieved else '否'}")

    print(f"\n任务执行详情:")
    for task_id, task_result in result.task_results.items():
        status_emoji = "✅" if task_result.is_successful() else "❌"
        print(f"  {status_emoji} {task_id}: {task_result.status.value}")
        if task_result.error:
            print(f"    错误: {task_result.error}")

    # 可视化结果
    if report_path:
        print(f"\n📊 可视化报告已生成: {report_path}")
        print("可以在浏览器中打开查看详细的执行结果和图表")

        # 显示可用的图表文件
        viz_dir = Path("output/visualizations")
        if viz_dir.exists():
            html_files = list(viz_dir.glob("*.html"))
            print(f"\n生成的可视化文件 ({len(html_files)} 个):")
            for file in sorted(html_files):
                print(f"  - {file.name}")
    else:
        print("\n❌ 可视化报告生成失败")

    print("\n" + "=" * 50)
    print("示例展示了 Executor 的主要功能:")
    print("✓ JSON 工作流定义和解析")
    print("✓ 简单和复杂任务的智能分发")
    print("✓ React 模式的目标导向执行")
    print("✓ 依赖关系管理和执行顺序控制")
    print("✓ LLM 集成的复杂任务解决")
    print("✓ 丰富的可视化结果展示")
    print("✓ 水文模型专业化工具支持")


if __name__ == "__main__":
    # 确保输出目录存在
    Path("data/example_basin").mkdir(parents=True, exist_ok=True)

    # 运行示例
    main()
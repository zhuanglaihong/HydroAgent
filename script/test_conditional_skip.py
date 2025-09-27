"""
简单测试条件跳过逻辑是否生效
"""

import json
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from executor.main import ExecutorEngine

def test_conditional_skip():
    """测试条件跳过逻辑"""
    print("=== 测试条件跳过逻辑 ===")

    # 检查工作流配置
    workflow_path = project_root / "workflow" / "example" / "react_hydro_optimization.json"

    with open(workflow_path, 'r', encoding='utf-8') as f:
        workflow = json.load(f)

    # 查看数据准备任务的条件配置
    for task in workflow['tasks']:
        if task['task_id'] == 'task_prepare':
            print(f"数据准备任务条件: {task.get('conditions', {})}")
            execute_iterations = task.get('conditions', {}).get('execute_iterations')
            print(f"执行迭代设置: {execute_iterations}")

            if execute_iterations == 'first_only':
                print("✅ 配置正确：数据准备任务只在第一次迭代执行")
                return True
            else:
                print("❌ 配置错误：数据准备任务条件设置不正确")
                return False

    print("❌ 未找到数据准备任务")
    return False

if __name__ == "__main__":
    success = test_conditional_skip()
    print(f"\n结果: {'通过' if success else '失败'}")
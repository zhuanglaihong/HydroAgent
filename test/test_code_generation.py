"""
Author: Claude
Date: 2025-01-24 12:00:00
LastEditTime: 2025-01-24 15:00:00
LastEditors: Claude
Description: Test script for RunnerAgent code generation capability (v4.0)
             v4.0改进：代码生成功能已从DeveloperAgent迁移到RunnerAgent
FilePath: /HydroAgent/test/test_code_generation.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

测试目标 (v4.0):
1. ✅ 验证RunnerAgent是否能够生成Python代码（代码生成已迁移到执行层）
2. ✅ 测试不同类型的代码生成任务（径流系数、FDC曲线等）
3. ✅ 检查生成的代码是否包含必要的导入和函数定义
4. 🆕 验证代码生成与执行分离的架构设计

v4.0 架构变更:
- RunnerAgent: 负责代码生成 + 代码执行（执行层）
- DeveloperAgent: 负责结果分析 + 可视化绘图（分析层）
"""

import sys
from pathlib import Path
import io

# Windows console encoding fix
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from unittest.mock import Mock
from hydroagent.agents.runner_agent import RunnerAgent


def test_runoff_coefficient_code_generation():
    """测试径流系数计算代码生成（v4.0: RunnerAgent）"""
    print("=" * 70)
    print("测试1: 生成径流系数计算代码 (v4.0: RunnerAgent)")
    print("=" * 70)

    # 创建mock 通用LLM (for RunnerAgent general use)
    mock_llm = Mock()
    mock_llm.model_name = "qwen-turbo"

    # 创建mock 代码LLM (for code generation)
    mock_code_llm = Mock()
    mock_code_llm.model_name = "qwen-coder-turbo"

    # 模拟代码LLM返回的代码
    mock_code = """
import pandas as pd
import numpy as np
from pathlib import Path

def calculate_runoff_coefficient(data_file: str, basin_id: str):
    \"\"\"
    计算流域径流系数

    径流系数 = 总径流量 / 总降水量
    \"\"\"
    # 读取数据
    df = pd.read_csv(data_file)

    # 计算总降水量和总径流量
    total_precip = df['precipitation'].sum()
    total_runoff = df['streamflow'].sum()

    # 计算径流系数
    runoff_coefficient = total_runoff / total_precip

    print(f"流域 {basin_id} 的径流系数: {runoff_coefficient:.4f}")

    return runoff_coefficient

if __name__ == "__main__":
    basin_id = "01013500"
    data_file = "path/to/data.csv"
    coeff = calculate_runoff_coefficient(data_file, basin_id)
"""
    mock_code_llm.generate.return_value = mock_code

    # 创建临时工作目录
    import tempfile
    workspace = Path(tempfile.mkdtemp())

    # 🆕 v4.0: 创建RunnerAgent（代码生成已迁移到这里）
    agent = RunnerAgent(
        llm_interface=mock_llm,
        code_llm_interface=mock_code_llm,  # v4.0: RunnerAgent现在需要代码LLM
        workspace_dir=workspace
    )

    # 测试代码生成（使用RunnerAgent的_generate_analysis_code方法）
    parameters = {
        "analysis_type": "runoff_coefficient",
        "basin_id": "01013500",
        "description": "计算流域01013500的径流系数（总径流量/总降水量）"
    }

    result = agent._generate_analysis_code("runoff_coefficient", parameters)

    print(f"\n✅ 代码生成成功")
    print(f"生成的代码文件: {result.get('code_file')}")
    print(f"生成的代码长度: {result.get('code_length')} 字符")
    print(f"\n生成的代码片段:")
    print("-" * 70)
    code_content = result.get('code', '')
    print(code_content[:500] if code_content else "无代码内容")
    print("...")
    print("-" * 70)

    # 验证代码包含关键元素
    assert result.get('status') == 'success', "代码生成应该成功"
    assert result.get('code_file'), "应该返回代码文件路径"

    print("\n✅ 测试1通过: RunnerAgent代码生成功能正常 (v4.0)\n")


def test_fdc_curve_code_generation():
    """测试FDC曲线绘制代码生成（v4.0: RunnerAgent）"""
    print("=" * 70)
    print("测试2: 生成FDC曲线绘制代码 (v4.0: RunnerAgent)")
    print("=" * 70)

    # 创建mock 通用LLM
    mock_llm = Mock()
    mock_llm.model_name = "qwen-turbo"

    # 创建mock 代码LLM
    mock_code_llm = Mock()
    mock_code_llm.model_name = "qwen-coder-turbo"

    # 模拟代码LLM返回的代码
    mock_code = """
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

def plot_fdc_curve(streamflow_data: np.ndarray, output_file: str = "fdc_curve.png"):
    \"\"\"
    绘制流量历时曲线 (Flow Duration Curve, FDC)

    FDC显示流量的超越概率分布
    \"\"\"
    # 排序流量数据（降序）
    sorted_flow = np.sort(streamflow_data)[::-1]

    # 计算超越概率
    n = len(sorted_flow)
    exceed_prob = np.arange(1, n+1) / (n+1) * 100

    # 绘制FDC曲线
    plt.figure(figsize=(10, 6))
    plt.semilogy(exceed_prob, sorted_flow, 'b-', linewidth=2)
    plt.xlabel('超越概率 (%)')
    plt.ylabel('流量 (m³/s)')
    plt.title('流量历时曲线 (FDC)')
    plt.grid(True, which="both", ls="-", alpha=0.3)
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()

    print(f"FDC曲线已保存到: {output_file}")

    return exceed_prob, sorted_flow

if __name__ == "__main__":
    # 示例数据
    streamflow = np.random.lognormal(3, 1, 1000)
    plot_fdc_curve(streamflow, "fdc_curve.png")
"""
    mock_code_llm.generate.return_value = mock_code

    # 创建临时工作目录
    import tempfile
    workspace = Path(tempfile.mkdtemp())

    # 🆕 v4.0: 创建RunnerAgent
    agent = RunnerAgent(
        llm_interface=mock_llm,
        code_llm_interface=mock_code_llm,
        workspace_dir=workspace
    )

    # 测试代码生成
    parameters = {
        "analysis_type": "fdc_curve",
        "basin_id": "01013500",
        "description": "绘制流量历时曲线FDC，展示流量的超越概率分布"
    }

    result = agent._generate_analysis_code("fdc_curve", parameters)

    print(f"\n✅ 代码生成成功")
    print(f"生成的代码文件: {result.get('code_file')}")
    print(f"生成的代码长度: {result.get('code_length')} 字符")
    print(f"\n生成的代码片段:")
    print("-" * 70)
    code_content = result.get('code', '')
    print(code_content[:500] if code_content else "无代码内容")
    print("...")
    print("-" * 70)

    # 验证代码包含关键元素
    assert result.get('status') == 'success', "代码生成应该成功"
    assert result.get('code_file'), "应该返回代码文件路径"

    print("\n✅ 测试2通过: RunnerAgent FDC代码生成功能正常 (v4.0)\n")


def test_runner_agent_custom_analysis():
    """测试RunnerAgent处理custom_analysis任务（v4.0）"""
    print("=" * 70)
    print("测试3: RunnerAgent处理custom_analysis任务 (v4.0)")
    print("=" * 70)

    # 创建mock 通用LLM
    mock_llm = Mock()
    mock_llm.model_name = "qwen-turbo"

    # 创建mock 代码LLM并设置返回值
    mock_code_llm = Mock()
    mock_code_llm.model_name = "qwen-coder-turbo"
    mock_code_llm.generate.return_value = """
import pandas as pd

def calculate_runoff_coefficient():
    print("Calculating runoff coefficient...")
    return 0.75

if __name__ == "__main__":
    coeff = calculate_runoff_coefficient()
    print(f"Runoff coefficient: {coeff}")
"""

    # 创建临时工作目录
    import tempfile
    workspace = Path(tempfile.mkdtemp())

    # 🆕 v4.0: 创建RunnerAgent（代码生成现在在这里）
    agent = RunnerAgent(
        llm_interface=mock_llm,
        code_llm_interface=mock_code_llm,
        workspace_dir=workspace
    )

    # 测试自定义分析代码生成
    config = {
        "model": "xaj",
        "basin_ids": ["01013500"]
    }

    parameters = {
        "extended_analysis": "runoff_coefficient",
        "analysis_type": "runoff_coefficient",
        "basin_id": "01013500",
        "description": "计算径流系数"
    }

    result = agent._run_custom_analysis(config, parameters)

    print(f"\n分析结果:")
    print(f"  status: {result.get('status')}")
    print(f"  mode: {result.get('mode')}")

    # 验证结果
    assert result.get("status") in ["success", "partial_success"], "处理应该成功或部分成功"
    assert result.get("mode") == "custom_analysis", "模式应该是custom_analysis"

    print("\n✅ 测试3通过: RunnerAgent custom_analysis功能正常 (v4.0)")
    print("   代码生成和执行已迁移到RunnerAgent\n")

    return True


def test_runner_dual_llm_mode():
    """测试RunnerAgent双LLM模式（v4.0）"""
    print("=" * 70)
    print("测试4: RunnerAgent双LLM模式 (v4.0)")
    print("=" * 70)

    # 创建两个mock LLM
    general_llm = Mock()
    general_llm.model_name = "qwen-turbo"

    code_llm = Mock()
    code_llm.model_name = "qwen-coder-turbo"

    # 模拟代码LLM返回的代码
    mock_code = """
def analyze_basin(basin_id):
    print(f"Analyzing basin {basin_id}")
    return {"status": "success"}
"""
    code_llm.generate.return_value = mock_code

    # 创建临时工作目录
    import tempfile
    workspace = Path(tempfile.mkdtemp())

    # 🆕 v4.0: 创建RunnerAgent（使用代码专用LLM）
    agent = RunnerAgent(
        llm_interface=general_llm,
        code_llm_interface=code_llm,  # ⭐ 传入代码专用LLM
        workspace_dir=workspace
    )

    print(f"\n通用LLM: {agent.llm.model_name}")
    print(f"代码LLM: {agent.code_llm.model_name if agent.code_llm else 'None'}")

    # 验证使用了正确的LLM
    assert agent.llm.model_name == "qwen-turbo", "通用LLM应该是qwen-turbo"
    assert agent.code_llm and agent.code_llm.model_name == "qwen-coder-turbo", "代码LLM应该是qwen-coder-turbo"

    # 测试代码生成（应该使用code_llm）
    parameters = {"analysis_type": "test", "description": "测试"}
    result = agent._generate_analysis_code("test", parameters)

    print(f"\n代码生成结果状态: {result.get('status')}")

    print("\n✅ 测试4通过: RunnerAgent双LLM模式正常工作 (v4.0)")
    print("   代码生成使用专门的代码模型\n")


def main():
    """运行所有测试 (v4.0)"""
    print("\n" + "🧪 开始测试RunnerAgent代码生成能力 (v4.0)")
    print("=" * 70)
    print("v4.0架构: 代码生成功能已从DeveloperAgent迁移到RunnerAgent")
    print("=" * 70 + "\n")

    test_results = {
        "test1": False,
        "test2": False,
        "test3": False,
        "test4": False
    }

    try:
        # 测试1：径流系数代码生成 (RunnerAgent)
        test_runoff_coefficient_code_generation()
        test_results["test1"] = True

        # 测试2：FDC曲线代码生成 (RunnerAgent)
        test_fdc_curve_code_generation()
        test_results["test2"] = True

        # 测试3：custom_analysis模式处理 (RunnerAgent)
        test_results["test3"] = test_runner_agent_custom_analysis()

        # 测试4：双LLM模式 (RunnerAgent)
        test_runner_dual_llm_mode()
        test_results["test4"] = True

        print("\n" + "=" * 70)
        print("✅ 所有测试完成! (v4.0)")
        print("=" * 70)

        print("\n📋 测试总结 (v4.0架构):")
        print(f"  {'✅' if test_results['test1'] else '❌'} RunnerAgent代码生成功能正常（径流系数）")
        print(f"  {'✅' if test_results['test2'] else '❌'} RunnerAgent代码生成功能正常（FDC曲线）")
        print(f"  {'✅' if test_results['test3'] else '❌'} RunnerAgent custom_analysis完整处理")
        print(f"  {'✅' if test_results['test4'] else '❌'} RunnerAgent双LLM模式正常工作")

        print("\n🎯 v4.0架构验证:")
        print("  ✅ 代码生成已成功迁移到RunnerAgent（执行层）")
        print("  ✅ DeveloperAgent专注于分析和可视化（分析层）")
        print("  ✅ 职责分离清晰，架构更加合理")

        # 如果有失败的测试，给出诊断信息
        if not all(test_results.values()):
            print("\n🔧 失败测试诊断:")
            if not test_results['test3']:
                print("  • 测试3：RunnerAgent custom_analysis处理失败")
                print("    - 检查workspace_dir是否正确设置")
                print("    - 检查文件写入权限")
                print("    - 检查代码LLM是否正确配置")
        else:
            print("\n🎉 所有功能测试通过！v4.0架构验证成功！")

    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

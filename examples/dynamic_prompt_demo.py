"""
Author: Claude & zhuanglaihong
Date: 2025-11-21 16:00:00
LastEditTime: 2025-11-21 16:00:00
LastEditors: Claude
Description: Dynamic Prompt Manager Demo - 展示动态提示词如何提升识别准确度
FilePath: /HydroAgent/examples/dynamic_prompt_demo.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set console encoding (Windows compatible)
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from hydroagent.utils.prompt_manager import PromptManager, AgentContext


def demo_static_vs_dynamic():
    """
    演示：静态提示词 vs 动态提示词

    场景：IntentAgent处理复杂中文查询
    问题：原始静态prompt识别不准确
    解决：动态prompt根据反馈自适应调整
    """
    print("=" * 70)
    print("动态提示词系统演示")
    print("=" * 70)
    print()

    pm = PromptManager()

    # =========================================================================
    # 场景1: 静态提示词（当前方案）
    # =========================================================================
    print("【场景1: 静态提示词 - 简洁版】")
    print("-" * 70)

    static_prompt_simple = """Extract intent from hydrological model queries (中文/English).

**Intents**: calibration(率定), evaluation(评估), simulation(模拟)
**Models**: xaj, gr4j, gr5j, gr6j
**Output**: JSON only, no text."""

    print(static_prompt_simple)
    print()
    print("❌ 问题: 对复杂中文查询识别不准确")
    print("   示例: '率定GR4J模型，流域01013500, 使用SCE-UA算法，算法迭代只需要500轮就行'")
    print("   结果: Intent=UNKNOWN, Model=None, Basin=None")
    print()

    # =========================================================================
    # 场景2: 增强静态提示词（临时方案）
    # =========================================================================
    print("【场景2: 增强静态提示词 - 详细版】")
    print("-" * 70)

    static_prompt_enhanced = """你是一个水文模型意图分析助手。从用户查询中提取结构化信息。

**任务**: 分析水文模型查询，提取意图、模型、流域、时间、算法等信息

**意图分类**:
- calibration (中文: 率定/校准/参数率定)
- evaluation (中文: 评估/验证/测试)

**支持的模型**: xaj, gr4j, gr5j, gr6j

**关键信息提取**:
1. 模型名称: "GR4J模型" → gr4j
2. 流域ID: "流域01013500" → 01013500
3. 算法: "SCE-UA" → SCE_UA
4. 额外参数: "迭代500次" → max_iterations=500

**输出格式**: 必须返回有效JSON"""

    print(static_prompt_enhanced[:200] + "...")
    print()
    print("✅ 改进: 识别准确度提升")
    print("❌ 问题: 缺乏灵活性，无法根据错误自适应调整")
    print()

    # =========================================================================
    # 场景3: 动态提示词（推荐方案）
    # =========================================================================
    print("【场景3: 动态提示词 - 自适应版】")
    print("-" * 70)

    # 注册静态骨架
    pm.register_static_prompt("IntentAgent", """你是一个水文模型意图分析助手。
从用户查询中提取结构化信息。

**任务**: 分析水文模型查询，提取意图、模型、流域、时间、算法等信息

**意图分类**: calibration, evaluation, simulation
**支持的模型**: xaj, gr4j, gr5j, gr6j
**输出格式**: 必须返回有效JSON""")

    # 创建上下文
    context = pm.create_context(
        agent_name="IntentAgent",
        user_query="率定GR4J模型，流域01013500, 使用SCE-UA算法，算法迭代只需要500轮就行"
    )

    # Round 1: 初始请求
    print("\n[Round 1] 初始请求:")
    print("-" * 70)
    prompt_v1 = pm.build_prompt("IntentAgent", context, include_schema=False, include_feedback=False)
    print(prompt_v1)
    print()
    print("✅ 动态注入了用户查询上下文")
    print()

    # 模拟：第一轮失败，LLM未能正确识别
    context.add_feedback("解析失败：未能识别'GR4J'模型名称。请注意中文查询中的大小写变体。")
    context.add_feedback("建议：增加中文关键词映射，如'GR4J模型' → 'gr4j'")
    context.increment_iteration()

    # Round 2: 包含反馈的请求
    print("\n[Round 2] 包含反馈的自适应请求:")
    print("-" * 70)
    prompt_v2 = pm.build_prompt("IntentAgent", context, include_schema=False, include_feedback=True)
    print(prompt_v2)
    print()
    print("✅ 自动注入了历史反馈")
    print("✅ LLM可以从错误中学习")
    print()

    # =========================================================================
    # 场景4: 带Schema的ConfigAgent
    # =========================================================================
    print("\n【场景4: ConfigAgent - Schema注入】")
    print("-" * 70)

    # 注册ConfigAgent的静态prompt
    pm.register_static_prompt("ConfigAgent", """你是水文模型配置生成专家。
根据用户意图生成hydromodel配置。

**任务**: 生成符合Schema的YAML配置文件""")

    # 模拟加载Schema（实际应该从文件加载）
    pm.schemas["config"] = """
model: string (xaj, gr4j, gr5j, gr6j)
basin_id: string
time_range:
  train: [start_date, end_date]
  test: [start_date, end_date]
algorithm: string (SCE_UA, DE, PSO)
algorithm_params:
  max_iterations: int (default: 1000)
  population_size: int (default: 20)
"""

    # 创建ConfigAgent上下文
    config_context = pm.create_context(
        agent_name="ConfigAgent",
        user_query="率定GR4J模型，流域01013500，迭代500次",
        workspace_dir=Path("/workspace/session_001"),
        intent="calibration",
        model="gr4j",
        basin_id="01013500"
    )

    prompt_config = pm.build_prompt("ConfigAgent", config_context, include_schema=True, include_feedback=False)
    print(prompt_config)
    print()
    print("✅ 自动注入了Schema约束")
    print("✅ LLM知道配置的确切格式")
    print()


def demo_iterative_refinement():
    """
    演示：迭代优化场景

    场景：参数触碰边界，自动调整
    """
    print("\n" + "=" * 70)
    print("迭代优化场景演示")
    print("=" * 70)
    print()

    pm = PromptManager()

    pm.register_static_prompt("ConfigAgent", """你是水文模型配置生成专家。
根据意图和反馈生成优化的配置。""")

    # Round 1: 初始配置
    print("[Round 1] 生成初始配置")
    print("-" * 70)

    context = pm.create_context(
        agent_name="ConfigAgent",
        user_query="率定GR4J模型，流域01013500",
        workspace_dir=Path("/workspace/session_001"),
        model="gr4j",
        basin_id="01013500"
    )

    prompt_r1 = pm.build_prompt("ConfigAgent", context, include_schema=False)
    print(prompt_r1)
    print()
    print("→ 生成配置: x1 范围 [100, 1200]")
    print("→ 运行率定: x1 = 1199.8 (触碰上界)")
    print()

    # Round 2: 根据反馈调整
    print("[Round 2] 根据边界警告调整参数范围")
    print("-" * 70)

    context.add_feedback("Warning: Parameter x1 hit upper boundary (1199.8 ≈ 1200)")
    context.add_feedback("Suggestion: Expand x1 upper bound from 1200 to 1500")
    context.increment_iteration()

    prompt_r2 = pm.build_prompt("ConfigAgent", context, include_schema=False)
    print(prompt_r2)
    print()
    print("✅ LLM接收到边界警告")
    print("✅ 自动扩大参数范围: x1 [100, 1500]")
    print("✅ 重新率定，得到更优结果")
    print()


def compare_approaches():
    """对比不同方案"""
    print("\n" + "=" * 70)
    print("方案对比总结")
    print("=" * 70)
    print()

    comparison = """
┌────────────────────────┬──────────────┬──────────────┬──────────────┐
│        特性            │  静态简洁版  │ 静态增强版   │  动态提示词  │
├────────────────────────┼──────────────┼──────────────┼──────────────┤
│ 初始识别准确度         │    ⭐⭐      │   ⭐⭐⭐⭐    │  ⭐⭐⭐⭐⭐   │
│ 错误自愈能力           │      ❌      │      ❌      │      ✅      │
│ 上下文感知             │      ❌      │      ❌      │      ✅      │
│ 参数自适应调整         │      ❌      │      ❌      │      ✅      │
│ 多轮迭代优化           │      ❌      │      ❌      │      ✅      │
│ Schema约束注入         │      ❌      │      ❌      │      ✅      │
│ 代码维护难度           │     低       │      中      │      中      │
│ Prompt长度             │     短       │      长      │   动态变化   │
│ Token消耗              │     低       │      高      │   自适应     │
└────────────────────────┴──────────────┴──────────────┴──────────────┘

**结论**:
1. 短期方案: 使用静态增强版（当前实现）
2. 长期方案: 逐步迁移到动态提示词系统
3. 混合方案: 关键Agent（IntentAgent, ConfigAgent）使用动态提示词

**实施建议**:
Phase 1: 创建PromptManager基础设施 ✅ (已完成)
Phase 2: IntentAgent迁移到动态提示词
Phase 3: ConfigAgent支持反馈驱动的参数调整
Phase 4: 全系统动态提示词改造
"""

    print(comparison)


if __name__ == "__main__":
    demo_static_vs_dynamic()
    demo_iterative_refinement()
    compare_approaches()

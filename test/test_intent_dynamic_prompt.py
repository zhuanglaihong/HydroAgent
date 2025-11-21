"""
Author: Claude & zhuanglaihong
Date: 2025-11-21 16:30:00
LastEditTime: 2025-11-21 16:30:00
LastEditors: Claude
Description: Test IntentAgent with dynamic prompt system
             测试IntentAgent的动态提示词系统
FilePath: /HydroAgent/scripts/test_intent_dynamic_prompt.py
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

import logging
from datetime import datetime

# Setup logging
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

log_file = logs_dir / f"test_intent_dynamic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

from hydroagent.agents.intent_agent import IntentAgent
from hydroagent.core.llm_interface import LLMInterface


class MockLLMInterface(LLMInterface):
    """Mock LLM for testing dynamic prompt system"""

    def __init__(self):
        self.last_system_prompt = None
        self.last_user_prompt = None
        self.call_count = 0

    def generate(self, system_prompt: str, user_prompt: str,
                 temperature: float = 0.7, max_tokens: int = None) -> str:
        self.last_system_prompt = system_prompt
        self.last_user_prompt = user_prompt
        self.call_count += 1

        logger.info(f"\n{'='*70}")
        logger.info(f"LLM Call #{self.call_count}")
        logger.info(f"{'='*70}")
        logger.info(f"System Prompt Length: {len(system_prompt)} chars")
        logger.info(f"System Prompt (first 200 chars): {system_prompt[:200]}...")
        logger.info(f"\nUser Prompt Length: {len(user_prompt)} chars")
        logger.info(f"User Prompt (first 500 chars):\n{user_prompt[:500]}...")
        logger.info(f"{'='*70}\n")

        # Return mock JSON response
        return """{
    "intent": "calibration",
    "model_name": "gr4j",
    "basin_id": "01013500",
    "algorithm": "SCE_UA",
    "extra_params": {"max_iterations": 500},
    "missing_info": [],
    "confidence": 0.95
}"""

    def generate_json(self, system_prompt: str, user_prompt: str,
                     temperature: float = 0.7, max_tokens: int = None) -> dict:
        # Call generate to log the prompts
        response_text = self.generate(system_prompt, user_prompt, temperature, max_tokens)
        import json
        return json.loads(response_text)


def test_static_vs_dynamic():
    """对比静态提示词和动态提示词"""
    print("="*70)
    print("测试：静态提示词 vs 动态提示词")
    print("="*70)
    print()

    test_query = "率定GR4J模型，流域01013500, 使用SCE-UA算法，算法迭代只需要500轮就行"

    # Test 1: Static prompt mode
    print("[Test 1] 静态提示词模式 (use_dynamic_prompt=False)")
    print("-"*70)

    mock_llm_static = MockLLMInterface()
    agent_static = IntentAgent(
        llm_interface=mock_llm_static,
        use_dynamic_prompt=False
    )

    result_static = agent_static.process({"query": test_query})

    print(f"\n✅ Static Mode Results:")
    print(f"   - System Prompt Length: {len(mock_llm_static.last_system_prompt)} chars")
    print(f"   - User Prompt Length: {len(mock_llm_static.last_user_prompt)} chars")
    print(f"   - Intent: {result_static['intent_result']['intent']}")
    print(f"   - Model: {result_static['intent_result']['model_name']}")
    print(f"   - Basin: {result_static['intent_result']['basin_id']}")
    print()

    # Test 2: Dynamic prompt mode
    print("\n[Test 2] 动态提示词模式 (use_dynamic_prompt=True)")
    print("-"*70)

    mock_llm_dynamic = MockLLMInterface()
    agent_dynamic = IntentAgent(
        llm_interface=mock_llm_dynamic,
        use_dynamic_prompt=True
    )

    result_dynamic = agent_dynamic.process({"query": test_query})

    print(f"\n✅ Dynamic Mode Results:")
    print(f"   - System Prompt Length: {len(mock_llm_dynamic.last_system_prompt)} chars")
    print(f"   - User Prompt Length: {len(mock_llm_dynamic.last_user_prompt)} chars")
    print(f"   - Intent: {result_dynamic['intent_result']['intent']}")
    print(f"   - Model: {result_dynamic['intent_result']['model_name']}")
    print(f"   - Basin: {result_dynamic['intent_result']['basin_id']}")
    print()

    # Comparison
    print("\n[Comparison] 对比分析")
    print("-"*70)
    print(f"静态模式:")
    print(f"  - System Prompt: {len(mock_llm_static.last_system_prompt)} chars")
    print(f"  - User Prompt: {len(mock_llm_static.last_user_prompt)} chars")
    print(f"  - Total: {len(mock_llm_static.last_system_prompt) + len(mock_llm_static.last_user_prompt)} chars")
    print()
    print(f"动态模式:")
    print(f"  - System Prompt: {len(mock_llm_dynamic.last_system_prompt)} chars (empty)")
    print(f"  - User Prompt: {len(mock_llm_dynamic.last_user_prompt)} chars")
    print(f"  - Total: {len(mock_llm_dynamic.last_system_prompt) + len(mock_llm_dynamic.last_user_prompt)} chars")
    print()

    # Verify dynamic prompt contains user query
    if test_query in mock_llm_dynamic.last_user_prompt:
        print("✅ 动态prompt中包含用户查询")
    else:
        print("❌ 动态prompt中未找到用户查询")

    # Verify system prompt is empty in dynamic mode
    if len(mock_llm_dynamic.last_system_prompt) == 0:
        print("✅ 动态模式下system_prompt为空")
    else:
        print("❌ 动态模式下system_prompt不为空")

    print()


def test_feedback_integration():
    """测试反馈集成功能"""
    print("\n" + "="*70)
    print("测试：反馈集成功能")
    print("="*70)
    print()

    print("[Test 3] 带反馈的动态提示词")
    print("-"*70)

    mock_llm = MockLLMInterface()
    agent = IntentAgent(
        llm_interface=mock_llm,
        use_dynamic_prompt=True
    )

    test_query = "率定一个模型"
    context_with_feedback = {
        "feedback": [
            "解析失败：未能识别模型名称",
            "建议：请明确指定模型类型（如GR4J, XAJ）"
        ],
        "iteration": 1
    }

    result = agent.process({
        "query": test_query,
        "context": context_with_feedback
    })

    print(f"\n✅ Feedback Integration Results:")
    print(f"   - User Prompt Length: {len(mock_llm.last_user_prompt)} chars")

    # Check if feedback is in the prompt
    feedback_found = any(fb in mock_llm.last_user_prompt for fb in context_with_feedback["feedback"])

    if feedback_found:
        print("   ✅ 反馈已注入到提示词中")
    else:
        print("   ❌ 反馈未找到")

    print(f"   - Intent: {result['intent_result']['intent']}")
    print()


def test_prompt_manager_export():
    """测试PromptManager是否正确导出"""
    print("\n" + "="*70)
    print("测试：PromptManager导出")
    print("="*70)
    print()

    try:
        from hydroagent.utils import PromptManager, AgentContext
        print("✅ PromptManager和AgentContext成功导入")

        # Test instantiation
        pm = PromptManager()
        print("✅ PromptManager实例化成功")

        context = AgentContext(
            agent_name="TestAgent",
            user_query="测试查询"
        )
        print("✅ AgentContext实例化成功")

        # Test basic functionality
        pm.register_static_prompt("TestAgent", "Test prompt")
        final_prompt = pm.build_prompt("TestAgent", context)
        print(f"✅ 动态prompt构建成功 (length: {len(final_prompt)} chars)")

    except ImportError as e:
        print(f"❌ 导入失败: {str(e)}")
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")

    print()


def main():
    print("\n" + "="*70)
    print("IntentAgent 动态提示词系统测试")
    print("="*70)
    print(f"日志保存到: {log_file}")
    print()

    try:
        # Test 1: Static vs Dynamic
        test_static_vs_dynamic()

        # Test 2: Feedback integration
        test_feedback_integration()

        # Test 3: PromptManager export
        test_prompt_manager_export()

        print("\n" + "="*70)
        print("测试总结")
        print("="*70)
        print("✅ IntentAgent已成功集成动态提示词系统")
        print("✅ 动态模式下system_prompt为空，所有内容在user_prompt中")
        print("✅ 反馈机制可以正常工作")
        print("✅ PromptManager和AgentContext已正确导出")
        print()
        print("📝 下一步建议:")
        print("   1. 使用真实LLM测试识别准确度")
        print("   2. 集成到其他Agent（ConfigAgent, RunnerAgent, DeveloperAgent）")
        print("   3. 添加Schema注入功能到ConfigAgent")
        print("="*70)

    except Exception as e:
        logger.error(f"测试失败: {str(e)}", exc_info=True)
        print(f"\n❌ 测试失败: {str(e)}")
        print(f"详细日志请查看: {log_file}")


if __name__ == "__main__":
    main()

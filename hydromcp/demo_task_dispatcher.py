"""
任务分发器演示脚本
展示如何使用任务分发器判断任务复杂性并选择执行路径
"""

import asyncio
import logging
import sys
from pathlib import Path

# 添加项目根路径
repo_path = Path(__file__).parent.parent
sys.path.append(str(repo_path))

from langchain_ollama import ChatOllama
from hydromcp import (
    TaskDispatcher, 
    MCPAgent, 
    create_mcp_agent,
    TaskComplexity,
    TaskCategory
)

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def demo_task_classification():
    """演示任务分类功能"""
    print("=" * 60)
    print("🧪 任务分发器 - 任务分类演示")
    print("=" * 60)
    
    # 初始化LLM
    llm = ChatOllama(model="granite3-dense:8b", temperature=0.1)
    
    # 创建任务分发器
    dispatcher = TaskDispatcher(llm)
    
    # 测试任务列表
    test_tasks = [
        # 简单任务
        ("获取GR4J模型的参数信息", "简单", "参数查询"),
        ("准备CAMELS数据集", "简单", "数据准备"),
        ("率定一个水文模型", "简单", "模型率定"),
        ("评估模型性能", "简单", "模型评估"),
        
        # 复杂任务
        ("绘制流量过程线图", "复杂", "可视化"),
        ("计算两个时间序列的相关性", "复杂", "分析"),
        ("分析降雨径流关系", "复杂", "分析"),
        ("创建自定义的水文指标计算工具", "复杂", "自定义计算"),
        
        # 边界情况
        ("帮我做点什么", "未知", "模糊请求"),
        ("你好！能介绍一下自己吗？", "简单", "一般对话"),
    ]
    
    print(f"测试 {len(test_tasks)} 个任务的分类...")
    print()
    
    results = []
    
    for i, (task, expected_complexity, description) in enumerate(test_tasks, 1):
        print(f"📝 任务 {i}: {task}")
        print(f"   预期复杂度: {expected_complexity}")
        
        try:
            # 分类任务
            classification, strategy = await dispatcher.dispatch_task(task)
            
            # 显示结果
            print(f"   ✅ 分类结果:")
            print(f"      - 复杂度: {classification.complexity.value}")
            print(f"      - 类别: {classification.category.value}")
            print(f"      - 置信度: {classification.confidence:.2f}")
            print(f"      - 执行策略: {strategy['execution_type']}")
            print(f"      - 处理器: {strategy['handler']}")
            print(f"      - 推理: {classification.reasoning[:100]}...")
            
            if classification.required_tools:
                print(f"      - 需要工具: {classification.required_tools}")
            if classification.missing_capabilities:
                print(f"      - 缺失能力: {classification.missing_capabilities}")
            
            # 检查预期结果
            complexity_match = (
                (expected_complexity == "简单" and classification.complexity == TaskComplexity.SIMPLE) or
                (expected_complexity == "复杂" and classification.complexity == TaskComplexity.COMPLEX) or
                (expected_complexity == "未知" and classification.complexity == TaskComplexity.UNKNOWN)
            )
            
            if complexity_match:
                print(f"      ✅ 分类正确")
            else:
                print(f"      ⚠️ 分类可能不准确")
            
            results.append({
                "task": task,
                "expected": expected_complexity,
                "actual": classification.complexity.value,
                "correct": complexity_match,
                "confidence": classification.confidence
            })
            
        except Exception as e:
            print(f"   ❌ 分类失败: {e}")
            results.append({
                "task": task,
                "expected": expected_complexity,
                "actual": "error",
                "correct": False,
                "confidence": 0.0
            })
        
        print()
    
    # 统计结果
    correct_count = sum(1 for r in results if r["correct"])
    total_count = len(results)
    accuracy = correct_count / total_count if total_count > 0 else 0
    
    print("=" * 60)
    print("📊 分类结果统计")
    print("=" * 60)
    print(f"总任务数: {total_count}")
    print(f"正确分类: {correct_count}")
    print(f"分类准确率: {accuracy:.2%}")
    
    # 显示详细结果
    print("\n详细结果:")
    for i, result in enumerate(results, 1):
        status = "✅" if result["correct"] else "❌"
        print(f"{i:2d}. {status} {result['task'][:50]:<50} | 预期: {result['expected']:<4} | 实际: {result['actual']:<7} | 置信度: {result['confidence']:.2f}")
    
    return results


async def demo_agent_with_task_dispatcher():
    """演示Agent集成任务分发器"""
    print("\n" + "=" * 60)
    print("🤖 Agent集成任务分发器演示")
    print("=" * 60)
    
    try:
        # 创建Agent
        agent = await create_mcp_agent(
            llm_model="granite3-dense:8b",
            enable_workflow=False,  # 专注于任务分发功能
            enable_debug=True
        )
        
        # 测试对话
        test_messages = [
            "获取GR4J模型有哪些参数？",  # 简单任务
            "绘制一个流量过程线图",       # 复杂任务
            "你好！"                   # 一般对话
        ]
        
        for i, message in enumerate(test_messages, 1):
            print(f"\n💬 测试对话 {i}")
            print(f"👤 用户: {message}")
            
            try:
                result = await agent.chat(message)
                
                print(f"🤖 Agent响应类型: {result.get('execution_type', 'unknown')}")
                
                if 'classification' in result:
                    classification = result['classification']
                    print(f"   📋 任务分类:")
                    print(f"      - 复杂度: {classification['complexity']}")
                    print(f"      - 类别: {classification['category']}")
                    print(f"      - 置信度: {classification['confidence']:.2f}")
                
                print(f"   💭 响应: {result['response'][:200]}...")
                
                if result.get('success'):
                    print(f"   ✅ 处理成功")
                else:
                    print(f"   ❌ 处理失败: {result.get('error', '未知错误')}")
                
            except Exception as e:
                print(f"   💥 对话异常: {e}")
        
        await agent.cleanup()
        
    except Exception as e:
        print(f"❌ Agent演示失败: {e}")


async def demo_task_handlers():
    """演示不同任务处理器"""
    print("\n" + "=" * 60)
    print("🔧 任务处理器演示")
    print("=" * 60)
    
    from hydromcp.task_handlers import SimpleTaskHandler, ComplexTaskHandler
    from hydromcp.task_dispatcher import TaskClassification, TaskComplexity, TaskCategory
    
    # 创建处理器
    simple_handler = SimpleTaskHandler(enable_debug=True)
    await simple_handler.setup()
    
    llm = ChatOllama(model="granite3-dense:8b", temperature=0.1)
    complex_handler = ComplexTaskHandler(llm, enable_debug=True)
    
    try:
        # 测试简单任务处理器
        print("\n🔧 简单任务处理器测试")
        simple_classification = TaskClassification(
            complexity=TaskComplexity.SIMPLE,
            category=TaskCategory.PARAMETER_QUERY,
            confidence=0.9,
            reasoning="获取模型参数是简单任务",
            required_tools=["get_model_params"]
        )
        
        simple_result = await simple_handler.handle_task(
            "获取GR4J模型参数",
            simple_classification
        )
        
        print(f"   结果: {'成功' if simple_result['success'] else '失败'}")
        print(f"   执行时间: {simple_result.get('execution_time', 0):.2f}s")
        print(f"   工具数量: {simple_result.get('tools_executed', 0)}")
        
        # 测试复杂任务处理器
        print("\n🔧 复杂任务处理器测试")
        complex_classification = TaskClassification(
            complexity=TaskComplexity.COMPLEX,
            category=TaskCategory.VISUALIZATION,
            confidence=0.8,
            reasoning="可视化需要生成代码",
            required_tools=[],
            missing_capabilities=["绘图功能"]
        )
        
        complex_result = await complex_handler.handle_task(
            "绘制流量过程线图",
            complex_classification
        )
        
        print(f"   结果: {'成功' if complex_result['success'] else '失败'}")
        print(f"   执行时间: {complex_result.get('execution_time', 0):.2f}s")
        if 'stages' in complex_result:
            print(f"   处理阶段: {list(complex_result['stages'].keys())}")
        if 'generated_tools' in complex_result:
            print(f"   生成工具: {complex_result['generated_tools']}")
        
    finally:
        await simple_handler.cleanup()


async def main():
    """主演示函数"""
    print("🌟 MCP任务分发器系统演示")
    print("展示任务分类、分发和处理的完整流程")
    
    try:
        # 1. 任务分类演示
        classification_results = await demo_task_classification()
        
        # 2. Agent集成演示
        await demo_agent_with_task_dispatcher()
        
        # 3. 任务处理器演示
        await demo_task_handlers()
        
        print("\n" + "=" * 60)
        print("🎉 演示完成！")
        print("=" * 60)
        print("任务分发器功能说明:")
        print("1. 🧠 智能任务分类 - 自动判断任务复杂度")
        print("2. 🚀 多路径执行 - 简单任务用MCP工具，复杂任务生成代码")
        print("3. 🤖 Agent集成 - 无缝整合到对话系统")
        print("4. 📊 详细反馈 - 提供分类依据和执行结果")
        
    except KeyboardInterrupt:
        print("\n⏹️ 演示被用户中断")
    except Exception as e:
        print(f"\n💥 演示运行异常: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

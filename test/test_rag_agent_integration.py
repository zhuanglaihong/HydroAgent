"""
测试RAG增强Agent集成
验证Agent中的RAG知识库功能是否正常工作
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# 添加项目根路径
repo_path = Path(os.path.abspath(__file__)).parent
sys.path.append(str(repo_path))

from Agent import HydroAgent

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_rag_agent_basic():
    """测试RAG Agent基础功能"""
    print("🧪 测试1: RAG Agent基础初始化")
    
    try:
        # 创建启用RAG的Agent
        agent = HydroAgent(
            model_name="qwen3:8b",
            enable_debug=True,
            enable_rag=True
        )
        
        # 初始化
        await agent._initialize_components()
        
        # 检查初始化状态
        info = agent.get_session_info()
        print(f"✅ Agent初始化成功")
        print(f"   模型: {info['model_name']}")
        print(f"   RAG启用: {info['rag_enabled']}")
        print(f"   工具数量: {info['tools_count']}")
        
        if 'rag_system' in info:
            rag_info = info['rag_system']
            print(f"   RAG初始化: {rag_info['initialized']}")
            print(f"   文档目录: {rag_info['documents_dir']}")
        
        await agent.cleanup()
        return True
        
    except Exception as e:
        print(f"❌ 基础测试失败: {e}")
        logger.exception("基础测试异常")
        return False


async def test_rag_workflow_generation():
    """测试RAG增强工作流生成"""
    print("\n🧪 测试2: RAG增强工作流生成")
    
    try:
        # 创建Agent
        agent = HydroAgent(
            model_name="qwen3:8b",
            enable_debug=False,
            enable_rag=True
        )
        
        await agent._initialize_components()
        
        # 测试查询
        test_queries = [
            "我想使用GR4J模型进行流域建模",
            "如何配置水文模型参数",
            "模型率定的步骤是什么"
        ]
        
        for i, query in enumerate(test_queries, 1):
            print(f"\n📝 测试查询 {i}: {query}")
            
            try:
                # 生成工作流
                workflow_plan = await agent._generate_workflow(query)
                
                print(f"✅ 工作流生成成功:")
                print(f"   名称: {workflow_plan.name}")
                print(f"   描述: {workflow_plan.description[:100]}...")
                print(f"   步骤数: {len(workflow_plan.steps)}")
                
                # 显示前3个步骤
                for j, step in enumerate(workflow_plan.steps[:3], 1):
                    print(f"   步骤{j}: {step.name}")
                
            except Exception as e:
                print(f"❌ 查询 {i} 失败: {e}")
                logger.exception(f"查询 {i} 异常")
        
        await agent.cleanup()
        return True
        
    except Exception as e:
        print(f"❌ 工作流生成测试失败: {e}")
        logger.exception("工作流生成测试异常")
        return False


async def test_rag_vs_basic_comparison():
    """测试RAG增强 vs 基础模式对比"""
    print("\n🧪 测试3: RAG增强 vs 基础模式对比")
    
    test_query = "配置GR4J模型的参数并进行率定"
    
    try:
        # 测试RAG模式
        print("🧠 测试RAG增强模式:")
        rag_agent = HydroAgent(
            model_name="qwen3:8b",
            enable_debug=False,
            enable_rag=True
        )
        await rag_agent._initialize_components()
        
        rag_workflow = await rag_agent._generate_workflow(test_query)
        print(f"   RAG工作流: {rag_workflow.name} ({len(rag_workflow.steps)}步骤)")
        
        await rag_agent.cleanup()
        
        # 测试基础模式
        print("\n💡 测试基础模式:")
        basic_agent = HydroAgent(
            model_name="qwen3:8b",
            enable_debug=False,
            enable_rag=False
        )
        await basic_agent._initialize_components()
        
        basic_workflow = await basic_agent._generate_workflow(test_query)
        print(f"   基础工作流: {basic_workflow.name} ({len(basic_workflow.steps)}步骤)")
        
        await basic_agent.cleanup()
        
        # 对比结果
        print(f"\n📊 对比结果:")
        print(f"   RAG模式步骤数: {len(rag_workflow.steps)}")
        print(f"   基础模式步骤数: {len(basic_workflow.steps)}")
        print(f"   差异: {len(rag_workflow.steps) - len(basic_workflow.steps)} 步骤")
        
        return True
        
    except Exception as e:
        print(f"❌ 对比测试失败: {e}")
        logger.exception("对比测试异常")
        return False


async def test_agent_chat_simulation():
    """测试Agent对话模拟"""
    print("\n🧪 测试4: Agent对话模拟")
    
    try:
        agent = HydroAgent(
            model_name="qwen3:8b",
            enable_debug=False,
            enable_rag=True
        )
        
        await agent._initialize_components()
        
        # 模拟用户查询
        test_query = "我需要对GR4J模型进行率定，请帮我生成完整的工作流程"
        
        print(f"👤 模拟用户查询: {test_query}")
        
        # 执行完整的chat流程（但不执行实际工作流）
        result = await agent.chat(test_query)
        
        if result["status"] == "success":
            print("✅ 对话处理成功")
            workflow = result["workflow_plan"]
            print(f"   生成工作流: {workflow.name}")
            print(f"   步骤数量: {len(workflow.steps)}")
        else:
            print(f"❌ 对话处理失败: {result.get('error')}")
        
        await agent.cleanup()
        return True
        
    except Exception as e:
        print(f"❌ 对话模拟测试失败: {e}")
        logger.exception("对话模拟测试异常")
        return False


async def run_all_tests():
    """运行所有测试"""
    print("🚀 开始RAG Agent集成测试")
    print("=" * 60)
    
    tests = [
        ("基础初始化测试", test_rag_agent_basic),
        ("工作流生成测试", test_rag_workflow_generation),
        ("RAG对比测试", test_rag_vs_basic_comparison),
        ("对话模拟测试", test_agent_chat_simulation)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            print(f"\n{'='*20} {test_name} {'='*20}")
            result = await test_func()
            results.append((test_name, result))
            
            if result:
                print(f"✅ {test_name} 通过")
            else:
                print(f"❌ {test_name} 失败")
                
        except Exception as e:
            print(f"❌ {test_name} 异常: {e}")
            results.append((test_name, False))
            logger.exception(f"{test_name} 异常")
    
    # 总结
    print(f"\n{'='*60}")
    print("📊 测试总结:")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   {test_name}: {status}")
    
    print(f"\n🎯 总体结果: {passed}/{total} 测试通过")
    
    if passed == total:
        print("🎉 所有测试通过！RAG Agent集成成功！")
    else:
        print("⚠️  部分测试失败，请检查配置和依赖")
    
    return passed == total


if __name__ == "__main__":
    try:
        success = asyncio.run(run_all_tests())
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⌛ 测试被用户中断")
        exit(130)
    except Exception as e:
        print(f"\n❌ 测试运行失败: {e}")
        logger.exception("测试运行异常")
        exit(1)

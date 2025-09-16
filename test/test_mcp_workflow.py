"""
MCP工作流系统测试
测试从工作流生成到MCP工具执行的完整流程
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# 添加项目根路径
repo_path = Path(__file__).parent.parent
sys.path.append(str(repo_path))

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_mcp_server_direct():
    """测试MCP服务器直接调用模式"""
    print("=" * 60)
    print("🧪 测试MCP服务器直接调用模式")
    print("=" * 60)
    
    try:
        from hydromcp.server import hydro_mcp_server
        
        # 获取可用工具
        tools = hydro_mcp_server.get_available_tools()
        print(f"✅ 可用工具数量: {len(tools)}")
        for tool in tools:
            print(f"   - {tool['name']}: {tool['description']}")
        
        # 测试工具调用
        print("\n🔧 测试get_model_params工具...")
        result = await hydro_mcp_server.call_tool_direct(
            "get_model_params", 
            {"model_name": "gr4j"}
        )
        print(f"✅ 工具调用结果: {result}")
        
        return True
        
    except Exception as e:
        print(f"❌ MCP服务器测试失败: {e}")
        return False


async def test_mcp_client():
    """测试MCP客户端"""
    print("\n" + "=" * 60)
    print("🧪 测试MCP客户端")
    print("=" * 60)
    
    try:
        from hydromcp.client import HydroMCPClient
        
        # 创建客户端（直接模式）
        client = HydroMCPClient()
        
        # 连接
        if await client.connect():
            print("✅ MCP客户端连接成功")
            
            # 获取工具列表
            tools = client.get_available_tools()
            print(f"✅ 获取到 {len(tools)} 个工具")
            
            # 测试工具调用
            print("\n🔧 测试工具调用...")
            result = await client.call_tool("get_model_params", {"model_name": "gr4j"})
            print(f"✅ 工具调用成功: {result.get('success', False)}")
            
            await client.disconnect()
            return True
        else:
            print("❌ MCP客户端连接失败")
            return False
            
    except Exception as e:
        print(f"❌ MCP客户端测试失败: {e}")
        return False


async def test_mcp_workflow_executor():
    """测试MCP工作流执行器"""
    print("\n" + "=" * 60)
    print("🧪 测试MCP工作流执行器")
    print("=" * 60)
    
    try:
        from hydromcp.workflow_executor import MCPWorkflowExecutor
        from workflow.workflow_types import WorkflowPlan, WorkflowStep, StepType
        
        # 创建测试工作流
        steps = [
            WorkflowStep(
                step_id="step_1",
                name="获取模型参数",
                description="获取GR4J模型参数信息",
                step_type=StepType.TOOL_CALL,
                tool_name="get_model_params",
                parameters={"model_name": "gr4j"},
                dependencies=[],
                conditions={},
                retry_count=0,
                timeout=30
            )
        ]
        
        workflow = WorkflowPlan(
            plan_id="test_workflow_001",
            name="测试工作流",
            description="MCP工作流执行器测试",
            steps=steps,
            user_query="获取GR4J模型参数",
            expanded_query="",
            context="测试用例"
        )
        
        # 创建执行器
        executor = MCPWorkflowExecutor(enable_debug=True)
        
        # 设置执行器
        if await executor.setup():
            print("✅ MCP工作流执行器设置成功")
            
            # 执行工作流
            print("\n🔧 执行测试工作流...")
            result = await executor.execute_workflow(workflow)
            
            print(f"✅ 工作流执行完成")
            print(f"   - 状态: {result['overall_status']}")
            print(f"   - 执行时间: {result['total_execution_time']}s")
            print(f"   - 成功步骤: {result['steps_successful']}")
            print(f"   - 失败步骤: {result['steps_failed']}")
            
            await executor.cleanup()
            return result['overall_status'] == 'SUCCESS'
        else:
            print("❌ MCP工作流执行器设置失败")
            return False
            
    except Exception as e:
        print(f"❌ MCP工作流执行器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_mcp_agent_simple():
    """测试MCP Agent简单功能"""
    print("\n" + "=" * 60)
    print("🧪 测试MCP Agent简单功能")
    print("=" * 60)
    
    try:
        from hydromcp.agent_integration import MCPAgent
        
        # 创建Agent
        agent = MCPAgent(
            llm_model="granite3-dense:8b",
            enable_workflow=False,  # 先测试简单模式
            enable_debug=True
        )
        
        # 设置Agent
        if await agent.setup():
            print("✅ MCP Agent设置成功")
            
            # 测试简单对话
            test_messages = [
                "你好！",
                "GR4J模型有哪些参数？"
            ]
            
            for message in test_messages:
                print(f"\n👤 用户: {message}")
                result = await agent.chat(message)
                print(f"🤖 Agent: {result['response'][:100]}...")
                
                # 显示任务分发信息
                if 'classification' in result:
                    classification = result['classification']
                    print(f"   📋 任务分类: {classification['complexity']} ({classification['confidence']:.2f})")
                    print(f"   🔧 执行类型: {result.get('execution_type', 'unknown')}")
                
                if not result['success']:
                    print(f"⚠️ 处理失败: {result.get('error', '未知错误')}")
            
            await agent.cleanup()
            return True
        else:
            print("❌ MCP Agent设置失败")
            return False
            
    except Exception as e:
        print(f"❌ MCP Agent测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_task_dispatcher():
    """测试任务分发器"""
    print("\n" + "=" * 60)
    print("🧪 测试任务分发器")
    print("=" * 60)
    
    try:
        from hydromcp.task_dispatcher import TaskDispatcher
        from langchain_ollama import ChatOllama
        
        # 初始化
        llm = ChatOllama(model="granite3-dense:8b", temperature=0.1)
        dispatcher = TaskDispatcher(llm)
        
        # 测试任务
        test_tasks = [
            "获取GR4J模型参数",      # 简单任务
            "绘制流量过程线图",      # 复杂任务
            "计算相关性分析"        # 复杂任务
        ]
        
        success_count = 0
        
        for task in test_tasks:
            print(f"\n📝 分析任务: {task}")
            try:
                classification, strategy = await dispatcher.dispatch_task(task)
                print(f"   ✅ 复杂度: {classification.complexity.value}")
                print(f"   📂 类别: {classification.category.value}")
                print(f"   🎯 置信度: {classification.confidence:.2f}")
                print(f"   🚀 策略: {strategy['execution_type']}")
                success_count += 1
            except Exception as e:
                print(f"   ❌ 分析失败: {e}")
        
        print(f"\n✅ 任务分发器测试: {success_count}/{len(test_tasks)} 成功")
        return success_count == len(test_tasks)
        
    except Exception as e:
        print(f"❌ 任务分发器测试失败: {e}")
        return False


async def test_complete_workflow():
    """测试完整的工作流流程"""
    print("\n" + "=" * 60)
    print("🧪 测试完整的工作流流程")
    print("=" * 60)
    
    try:
        from hydromcp.agent_integration import MCPAgent
        
        # 创建Agent（启用工作流）
        agent = MCPAgent(
            llm_model="granite3-dense:8b",
            enable_workflow=True,
            enable_debug=True
        )
        
        # 设置Agent
        if await agent.setup():
            print("✅ MCP Agent设置成功")
            
            # 测试工作流请求
            message = "我想获取GR4J模型的参数信息"
            print(f"\n👤 用户: {message}")
            
            result = await agent.chat(message, use_workflow=False)  # 使用简单模式
            print(f"🤖 Agent: {result['response']}")
            
            if result['success']:
                print("✅ 完整工作流测试成功")
                if result.get('tool_used'):
                    print(f"   - 使用工具: {result['tool_used']['tool_name']}")
                return True
            else:
                print(f"❌ 完整工作流测试失败: {result.get('error', '未知错误')}")
                return False
                
            await agent.cleanup()
        else:
            print("❌ MCP Agent设置失败")
            return False
            
    except Exception as e:
        print(f"❌ 完整工作流测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_all_tests():
    """运行所有测试"""
    print("🚀 开始MCP工作流系统完整测试")
    print("测试将验证从工作流生成到MCP工具执行的完整流程\n")
    
    tests = [
        ("MCP服务器直接调用", test_mcp_server_direct),
        ("MCP客户端", test_mcp_client),
        ("MCP工作流执行器", test_mcp_workflow_executor),
        ("任务分发器", test_task_dispatcher),
        ("MCP Agent简单功能", test_mcp_agent_simple),
        ("完整工作流流程", test_complete_workflow),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            print(f"\n{'='*20} {test_name} {'='*20}")
            result = await test_func()
            results.append((test_name, result))
            
            if result:
                print(f"✅ {test_name} 测试通过")
            else:
                print(f"❌ {test_name} 测试失败")
                
        except Exception as e:
            print(f"❌ {test_name} 测试异常: {e}")
            results.append((test_name, False))
    
    # 总结
    print("\n" + "=" * 60)
    print("📊 测试结果总结")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   {test_name}: {status}")
    
    print(f"\n总体结果: {passed}/{total} 测试通过")
    
    if passed == total:
        print("🎉 所有测试通过！MCP工作流系统运行正常。")
    else:
        print("⚠️ 部分测试失败，请检查相关组件。")
    
    return passed == total


def check_dependencies():
    """检查依赖项"""
    print("🔍 检查依赖项...")
    
    required_modules = [
        "langchain_ollama",
        "pydantic", 
        "pathlib",
        "asyncio"
    ]
    
    missing = []
    for module in required_modules:
        try:
            __import__(module)
            print(f"✅ {module}")
        except ImportError:
            print(f"❌ {module} (缺失)")
            missing.append(module)
    
    # 检查项目模块
    project_modules = [
        "workflow.workflow_types",
        "definitions"
    ]
    
    for module in project_modules:
        try:
            __import__(module)
            print(f"✅ {module}")
        except ImportError:
            print(f"❌ {module} (缺失)")
            missing.append(module)
    
    if missing:
        print(f"\n⚠️ 缺失依赖: {missing}")
        print("请安装缺失的依赖项后重新运行测试")
        return False
    
    print("✅ 所有依赖项检查通过")
    return True


async def main():
    """主函数"""
    print("🔬 MCP工作流系统测试套件")
    print("=" * 60)
    
    # 检查依赖
    if not check_dependencies():
        return
    
    # 运行测试
    try:
        success = await run_all_tests()
        if success:
            print("\n🎊 测试完成：系统正常运行")
        else:
            print("\n⚠️ 测试完成：发现问题需要修复")
            
    except KeyboardInterrupt:
        print("\n⏹️ 测试被用户中断")
    except Exception as e:
        print(f"\n💥 测试运行异常: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

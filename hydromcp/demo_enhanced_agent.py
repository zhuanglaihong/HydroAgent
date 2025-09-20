"""
增强Agent接口使用示例
演示如何使用新的统一Agent接口进行工作流生成和执行

Author: Assistant
Date: 2025-01-20
"""

import asyncio
import logging
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 检查数据集
def check_dataset():
    """检查CAMELS数据集是否可用"""
    try:
        data_path = Path("data/camels_11532500/basin_11532500.csv")
        if not data_path.exists():
            print("⚠️ CAMELS数据集不存在，请确保数据文件位于正确位置")
            print(f"  期望路径: {data_path.absolute()}")
            return False
        
        # 检查其他必要文件
        required_files = [
            "basin_11532500_monthly.csv",
            "basin_11532500_yearly.csv",
            "attributes.nc",
            "timeseries.nc"
        ]
        
        missing_files = []
        for file in required_files:
            if not (data_path.parent / file).exists():
                missing_files.append(file)
        
        if missing_files:
            print("⚠️ 以下数据文件缺失:")
            for file in missing_files:
                print(f"  - {file}")
            return False
        
        print("✅ CAMELS数据集检查通过")
        return True
        
    except Exception as e:
        print(f"⚠️ 数据集检查失败: {str(e)}")
        return False

# 检查Ollama可用性
def check_ollama():
    """检查Ollama是否可用"""
    try:
        import ollama
        client = ollama.Client()
        # 测试连接
        response = client.chat(
            model="qwen3:8b",
            messages=[{"role": "user", "content": "test connection"}]
        )
        print("✅ Ollama连接成功，qwen3:8b模型可用")
        return True
    except ImportError:
        print("⚠️ Ollama未安装，请先安装: pip install ollama")
        return False
    except Exception as e:
        print(f"⚠️ Ollama连接失败: {str(e)}")
        print("  请确保Ollama服务已启动且qwen3:8b模型已下载")
        return False

# 检查嵌入模型
def check_embeddings():
    """检查嵌入模型是否可用"""
    try:
        import ollama
        client = ollama.Client()
        # 测试嵌入
        response = client.embeddings(
            model="bge-large:335m",
            prompt="test embeddings"
        )
        print("✅ 嵌入模型bge-large:335m可用")
        return True
    except Exception as e:
        print(f"⚠️ 嵌入模型检查失败: {str(e)}")
        print("  请确保bge-large:335m模型已下载")
        return False

from hydromcp import (
    HydroAgentInterface,
    SyncHydroAgentInterface,
    create_hydro_agent_interface,
    create_sync_hydro_agent_interface
)

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def demo_async_agent_interface():
    """演示异步Agent接口的使用"""
    print("=== 异步Agent接口演示 ===")
    
    try:
        # 检查依赖
        print("1. 检查系统依赖...")
        ollama_ok = check_ollama()
        embeddings_ok = check_embeddings() if ollama_ok else False
        
        if not ollama_ok:
            raise RuntimeError("Ollama不可用，无法继续演示")
        
        # 创建并初始化Agent接口
        print("2. 初始化Agent接口...")
        agent = await create_hydro_agent_interface(
            llm_model="qwen3:8b",
            enable_rag=embeddings_ok,  # 根据嵌入模型可用性决定是否启用RAG
            enable_complex_tasks=True,
            enable_debug=True
        )
        
        # 获取系统状态
        print("2. 检查系统状态...")
        status = await agent.get_system_status()
        print(f"   初始化状态: {status['is_initialized']}")
        print(f"   RAG系统: {status['components']['rag_system']}")
        print(f"   工作流生成器: {status['components']['workflow_generator']}")
        print(f"   工作流执行器: {status['components']['workflow_executor']}")
        
        # 测试指令列表 - 使用实际的MCP工具
        test_instructions = [
            # 使用prepare_data工具
            # "将CAMELS数据集中basin_11532500的CSV数据转换为NetCDF格式并进行预处理",
            
            # # 使用get_model_params工具
            # "查看GR4J模型的参数信息和取值范围",
            
            # 使用calibrate_model工具
            "使用SCE-UA算法率定GR4J模型，使用basin_11532500数据，优化NSE指标",
            
            # 使用evaluate_model工具
            "评估已率定的GR4J模型性能，计算NSE、RMSE等评估指标"
        ]
        
        # 处理每个测试指令
        for i, instruction in enumerate(test_instructions, 1):
            print(f"\n3.{i} 处理用户请求: {instruction}")
            
            # 完整处理（生成+执行）
            result = await agent.process_user_request(instruction)
            
            if result["success"]:
                print(f"   ✅ 处理成功")
                print(f"   工作流名称: {result['workflow_generation']['workflow_name']}")
                print(f"   任务数量: {result['workflow_generation']['task_count']}")
                print(f"   生成时间: {result['workflow_generation']['generation_time']:.2f}秒")
                print(f"   执行成功率: {result['workflow_execution']['summary']['success_rate']:.1%}")
                print(f"   总耗时: {result['overall_summary']['total_time']:.2f}秒")
            else:
                print(f"   ❌ 处理失败: {result['error']}")
        
        # 测试仅生成工作流（不执行）
        print(f"\n4. 仅生成工作流示例")
        generation_result = await agent.generate_workflow_only("创建水文数据可视化图表")
        
        if generation_result["success"]:
            workflow = generation_result["workflow"]
            print(f"   ✅ 工作流生成成功")
            print(f"   工作流ID: {workflow['workflow_id']}")
            print(f"   任务数量: {len(workflow['tasks'])}")
            
            # 然后单独执行这个工作流
            print(f"   执行生成的工作流...")
            execution_result = await agent.execute_workflow_only(workflow)
            
            if execution_result["success"]:
                exec_data = execution_result["execution_result"]
                print(f"   ✅ 执行成功，成功率: {exec_data['summary']['success_rate']:.1%}")
            else:
                print(f"   ❌ 执行失败: {execution_result['error']}")
        
        # 清理资源
        await agent.cleanup()
        print("\n5. 资源清理完成")
        
    except Exception as e:
        logger.error(f"异步演示失败: {e}")


def demo_sync_agent_interface():
    """演示同步Agent接口的使用"""
    print("\n=== 同步Agent接口演示 ===")
    
    try:
        # 检查依赖
        print("1. 检查系统依赖...")
        ollama_ok = check_ollama()
        embeddings_ok = check_embeddings() if ollama_ok else False
        
        if not ollama_ok:
            raise RuntimeError("Ollama不可用，无法继续演示")
        
        # 创建同步Agent接口
        print("2. 初始化同步Agent接口...")
        sync_agent = create_sync_hydro_agent_interface(
            llm_model="qwen3:8b",
            enable_rag=embeddings_ok,  # 根据嵌入模型可用性决定是否启用RAG
            enable_complex_tasks=True,
            enable_debug=False
        )
        
        # 获取系统状态
        print("2. 检查系统状态...")
        status = sync_agent.get_system_status()
        print(f"   初始化状态: {status['is_initialized']}")
        
        # 处理简单请求
        print("3. 处理用户请求...")
        result = sync_agent.process_user_request("读取NetCDF文件并显示基本信息")
        
        if result["success"]:
            print(f"   ✅ 处理成功")
            print(f"   工作流: {result['workflow_generation']['workflow_name']}")
            print(f"   执行成功率: {result['workflow_execution']['summary']['success_rate']:.1%}")
        else:
            print(f"   ❌ 处理失败: {result['error']}")
        
    except Exception as e:
        logger.error(f"同步演示失败: {e}")


def demo_workflow_generation_types():
    """演示不同类型的工作流生成"""
    print("\n=== 不同类型工作流生成演示 ===")
    
    # 定义不同复杂度的任务 - 使用实际的水文工具
    workflow_types = [

        {
            "name": "模型率定（复杂任务）",
            "instruction": "使用SCE-UA算法率定GR4J模型，数据集为basin_11532500，使用默认的预热期和交叉验证设置",
            "expected_complexity": "complex_reasoning",
            "tools": ["prepare_data", "calibrate_model"]
        },
        {
            "name": "模型评估（复杂任务）",
            "instruction": "评估已率定的GR4J模型在训练期和测试期的性能，计算NSE、RMSE等指标",
            "expected_complexity": "complex_reasoning",
            "tools": ["evaluate_model"]
        },
        {
            "name": "完整建模流程（混合任务）",
            "instruction": "准备basin_11532500数据，查看GR4J模型参数，进行模型率定，最后评估模型性能",
            "expected_complexity": "mixed",
            "tools": ["prepare_data", "get_model_params", "calibrate_model", "evaluate_model"]
        }
    ]
    
    try:
        # 检查依赖
        print("1. 检查系统依赖...")
        ollama_ok = check_ollama()
        embeddings_ok = check_embeddings() if ollama_ok else False
        
        if not ollama_ok:
            raise RuntimeError("Ollama不可用，无法继续演示")
        
        # 创建Agent
        print("2. 初始化Agent接口...")
        sync_agent = create_sync_hydro_agent_interface(
            llm_model="qwen3:8b",
            enable_rag=embeddings_ok,  # 根据嵌入模型可用性决定是否启用RAG
            enable_debug=True,
            enable_complex_tasks=True
        )
        
        for workflow_type in workflow_types:
            print(f"\n测试 {workflow_type['name']}:")
            print(f"  指令: {workflow_type['instruction']}")
            
            # 仅生成工作流以查看结构
            result = sync_agent.generate_workflow_only(workflow_type['instruction'])
            
            if result["success"]:
                workflow = result["workflow"]
                tasks = workflow["tasks"]
                
                print(f"  ✅ 生成成功，包含 {len(tasks)} 个任务:")
                
                for i, task in enumerate(tasks, 1):
                    task_type = task.get("task_type", "unknown")
                    action = task.get("action", "unknown")
                    name = task.get("name", "未命名任务")
                    
                    complexity_icon = "🔧" if task_type == "simple_action" else "🧠"
                    print(f"    {i}. {complexity_icon} {name} ({task_type})")
                    print(f"       操作: {action}")
                
                # 统计任务类型
                simple_count = len([t for t in tasks if t.get("task_type") == "simple_action"])
                complex_count = len([t for t in tasks if t.get("task_type") == "complex_reasoning"])
                
                print(f"  📊 任务统计: {simple_count} 个简单任务, {complex_count} 个复杂任务")
                
            else:
                print(f"  ❌ 生成失败: {result['error']}")
                
    except Exception as e:
        logger.error(f"工作流类型演示失败: {e}")


async def main():
    """主函数"""
    print("🚀 HydroAgent增强接口演示")
    print("=" * 50)
    
    # 检查依赖
    print("\n=== 检查系统依赖 ===")
    
    # 1. 检查数据集
    print("\n1. 检查CAMELS数据集...")
    dataset_available = check_dataset()
    if not dataset_available:
        print("❌ 数据集不可用，演示将无法正常运行")
        print("  请确保CAMELS数据集已正确放置在data/camels_11532500/目录下")
        return
    
    # 2. 检查Ollama
    print("\n2. 检查Ollama服务...")
    ollama_available = check_ollama()
    if not ollama_available:
        print("❌ Ollama不可用，演示将无法正常运行")
        return
    
    # 3. 检查嵌入模型
    print("\n3. 检查嵌入模型...")
    embeddings_available = check_embeddings() if ollama_available else False
    if not embeddings_available:
        print("⚠️ 嵌入模型不可用，RAG功能将被禁用")
    
    print("\n系统检查完成，开始演示...")
    print("=" * 50)
    
    # 异步接口演示
    await demo_async_agent_interface()
    
    # 同步接口演示
    demo_sync_agent_interface()
    
    # 工作流类型演示
    demo_workflow_generation_types()
    
    print("\n🎉 演示完成！")


if __name__ == "__main__":
    # 运行演示
    asyncio.run(main())

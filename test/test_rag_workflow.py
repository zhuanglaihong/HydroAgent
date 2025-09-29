"""
简化的RAG+Ollama工作流生成测试
测试本地Ollama模型与RAG系统结合生成工作流的效果
"""

import sys
import json
import logging
from pathlib import Path

# 设置详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler( 'logs/test_rag_workflow.log', encoding='utf-8')
    ]
)

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent  # 获取实际的项目根目录
sys.path.insert(0, str(project_root))

def test_rag_workflow_generation():
    """测试RAG+Ollama生成工作流"""

    print("=== RAG+Ollama工作流生成测试 ===")

    try:
        # 1. 初始化RAG系统
        print("1. 初始化RAG系统...")
        from hydrorag import RAGSystem, Config

        config = Config(
            openai_api_key=None,  # 禁用API，仅使用本地
            embedding_model_name="bge-large:335m",
            local_embedding_model="bge-large:335m"
        )

        rag_system = RAGSystem(config)
        init_result = rag_system.is_initialized
        

        if not init_result:
            print("RAG系统初始化失败")
            return False

        print("RAG系统初始化成功")

        # 2. 初始化LLM客户端
        print("2. 初始化LLM客户端...")
        from builder.llm_client import LLMClient

        llm_client = LLMClient(use_api_first=False)  # 仅使用Ollama
        print("LLM客户端初始化成功")

        # 3. 创建工作流构建器
        print("3. 创建工作流构建器...")
        from builder.workflow_builder import WorkflowBuilder

        builder = WorkflowBuilder(
            rag_system=rag_system,
            llm_client=llm_client,
            enable_rag=True
        )

        # 检查就绪状态
        status = builder.is_ready()
        print("构建器状态:")
        for component, ready in status.items():
            print(f"  {component}: {'OK' if ready else 'FAIL'}")

        if not status["overall_ready"]:
            print("构建器未就绪，无法继续测试")
            return False

        # 4. 测试工作流生成
        print("\n4. 测试工作流生成...")

        test_query = "生成完整的水文建模工作流，包括数据准备、模型率定和评估"
        print(f"测试查询: {test_query}")
        print(f"查询长度: {len(test_query)} 字符")

        # 检查系统配置
        import config
        print(f"当前超时配置: {config.LLM_FALLBACK_TIMEOUT}秒")
        print(f"RAG知识块数量: {config.COT_KNOWLEDGE_CHUNKS}")
        print(f"推理温度: {config.COT_TEMPERATURE}")

        print("正在生成工作流...")
        import time
        start_time = time.time()
        result = builder.build_workflow(test_query, {"test_mode": True})
        total_time = time.time() - start_time
        print(f"工作流生成总耗时: {total_time:.2f}秒")

        if result.success:
            workflow = result.workflow
            print("\n工作流生成成功!")
            print(f"  名称: {workflow.get('name', 'Unknown')}")
            print(f"  执行模式: {workflow.get('execution_mode', 'Unknown')}")
            print(f"  任务数量: {len(workflow.get('tasks', []))}")
            print(f"  构建时间: {result.build_time:.2f}秒")

            # 显示任务列表
            tasks = workflow.get('tasks', [])
            print("\n任务列表:")
            for i, task in enumerate(tasks, 1):
                tool_name = task.get('tool_name', task.get('action', 'Unknown'))
                task_name = task.get('name', f'Task {i}')
                print(f"  {i}. {task_name} (工具: {tool_name})")

            # 保存结果
            output_file = project_root / 'workflow' / 'generated' / "rag_workflow_test_result.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "query": test_query,
                    "result": result.to_dict(),
                    "workflow": workflow
                }, f, indent=2, ensure_ascii=False)

            print(f"\n测试结果已保存到: {output_file}")

            # 5. 加载参考工作流进行比较
            print("\n5. 与参考工作流比较...")
            ref_file = project_root / "workflow" / "example" / "complete_hydro_workflow.json"

            if ref_file.exists():
                with open(ref_file, 'r', encoding='utf-8') as f:
                    reference = json.load(f)

                # 简单比较
                ref_tasks = reference.get('tasks', [])
                gen_tasks = workflow.get('tasks', [])

                ref_tools = [task.get('tool_name', task.get('action', '')) for task in ref_tasks]
                gen_tools = [task.get('tool_name', task.get('action', '')) for task in gen_tasks]

                print(f"参考工作流任务数: {len(ref_tasks)}")
                print(f"生成工作流任务数: {len(gen_tasks)}")
                print(f"参考工具: {ref_tools}")
                print(f"生成工具: {gen_tools}")

                # 计算工具匹配度
                if ref_tools:
                    matches = sum(1 for ref_tool, gen_tool in zip(ref_tools, gen_tools) if ref_tool == gen_tool)
                    similarity = matches / len(ref_tools)
                    print(f"工具匹配度: {similarity:.2f} ({matches}/{len(ref_tools)})")

                    if similarity >= 0.8:
                        print("✅ 工作流质量优秀")
                    elif similarity >= 0.6:
                        print("✅ 工作流质量良好")
                    else:
                        print("⚠️ 工作流质量需要改进")

            else:
                print("参考工作流文件不存在，跳过比较")

            return True

        else:
            print(f"工作流生成失败: {result.error_message}")
            return False

    except Exception as e:
        print(f"测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_rag_workflow_generation()
    print(f"\n测试结果: {'通过' if success else '失败'}")
    sys.exit(0 if success else 1)
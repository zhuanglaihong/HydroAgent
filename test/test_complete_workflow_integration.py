#!/usr/bin/env python3
"""
完整系统集成测试
测试从用户查询到最终执行的完整流程：
用户查询 -> 知识库检索 -> 工作流生成 -> MCP工具执行

测试场景：整理数据camels_11532500流域，用其率定GR4J模型，并评估模型
"""

import asyncio
import logging
import sys
import time
import json
from pathlib import Path
from typing import Dict, Any, List

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(project_root / 'test' / 'integration_test.log', mode='w')
    ]
)
logger = logging.getLogger(__name__)


class SystemComponentChecker:
    """系统组件检查器"""
    
    def __init__(self):
        self.check_results = {}
    
    def check_ollama_connection(self) -> bool:
        """检查Ollama连接和模型可用性"""
        try:
            import ollama
            client = ollama.Client()
            
            # 测试qwen3:8b模型
            logger.info("检查Ollama连接和qwen3:8b模型...")
            response = client.chat(
                model="qwen3:8b",
                messages=[{"role": "user", "content": "test"}]
            )
            
            # 测试bge-large:335m嵌入模型
            logger.info("检查bge-large:335m嵌入模型...")
            embeddings = client.embeddings(
                model="bge-large:335m",
                prompt="test embeddings"
            )
            
            self.check_results["ollama"] = {
                "status": "success",
                "chat_model": "qwen3:8b",
                "embedding_model": "bge-large:335m"
            }
            logger.info("✅ Ollama连接成功，模型可用")
            return True
            
        except ImportError:
            self.check_results["ollama"] = {"status": "error", "message": "ollama库未安装"}
            logger.error("❌ ollama库未安装")
            return False
        except Exception as e:
            self.check_results["ollama"] = {"status": "error", "message": str(e)}
            logger.error(f"❌ Ollama连接失败: {e}")
            return False
    
    def check_hydrorag_system(self) -> bool:
        """检查知识库系统"""
        try:
            from hydrorag import RAGSystem
            
            logger.info("初始化HydroRAG系统...")
            rag_system = RAGSystem()
            
            # 检查是否已有处理好的文档
            doc_path = project_root / "documents"
            if doc_path.exists():
                logger.info("📚 正在设置知识库...")
                # 使用setup_from_raw_documents方法
                setup_result = rag_system.setup_from_raw_documents()
                
                if setup_result.get("status") == "success":
                    logger.info("✅ 知识库设置成功")
                else:
                    logger.error(f"⚠️ 知识库设置失败: {setup_result}")
                    return False
            else:
                logger.warning("⚠️ 未找到documents文件夹，RAG系统将使用回退模式")
                return False
            
            # 测试知识库检索
            logger.info("测试知识库检索...")
            query_result = rag_system.query(
                query_text="prepare_data工具使用说明",
                top_k=3
            )
            
            results = query_result.get("results", []) if query_result.get("status") == "success" else []
            
            if len(results) > 0:
                self.check_results["hydrorag"] = {
                    "status": "success", 
                    "fragments_found": len(results),
                    "sample_content": results[0].get("content", "")[:100] + "..." if results else ""
                }
                logger.info(f"✅ HydroRAG系统正常，检索到{len(results)}个知识片段")
                return True
            else:
                self.check_results["hydrorag"] = {"status": "warning", "message": "知识库为空"}
                logger.warning("⚠️ 知识库检索结果为空")
                return False
                
        except Exception as e:
            self.check_results["hydrorag"] = {"status": "error", "message": str(e)}
            logger.error(f"❌ HydroRAG系统初始化失败: {e}")
            return False
    
    def check_workflow_generator(self, ollama_client=None) -> bool:
        """
        检查工作流生成器
        
        Args:
            ollama_client: 可选的Ollama客户端实例
        """
        try:
            from workflow import create_workflow_generator, GenerationConfig
            
            logger.info("初始化工作流生成器...")
            config = GenerationConfig(
                llm_model="qwen3:8b",
                enable_validation=True,
                enable_feedback_learning=False,
                rag_retrieval_k=8,  # 增加检索数量
                rag_score_threshold=0.2  # 降低阈值以获取更多相关知识
            )
            
            generator = create_workflow_generator(
                ollama_client=ollama_client,
                config=config
            )
            
            # 测试简单的工作流生成
            logger.info("测试工作流生成...")
            test_instruction = "查看GR4J模型的参数信息"
            
            result = generator.generate_workflow(test_instruction)
            
            if result.success and result.workflow:
                self.check_results["workflow_generator"] = {
                    "status": "success",
                    "test_workflow_tasks": len(result.workflow.tasks),
                    "generation_time": result.total_time
                }
                logger.info(f"✅ 工作流生成器正常，生成了{len(result.workflow.tasks)}个任务")
                return True
            else:
                self.check_results["workflow_generator"] = {
                    "status": "error", 
                    "message": result.error_message
                }
                logger.error(f"❌ 工作流生成失败: {result.error_message}")
                return False
                
        except Exception as e:
            self.check_results["workflow_generator"] = {"status": "error", "message": str(e)}
            logger.error(f"❌ 工作流生成器初始化失败: {e}")
            return False
    
    def check_mcp_tools(self) -> bool:
        """检查MCP工具"""
        try:
            from hydromcp.tools_dict import HYDRO_TOOLS, get_all_tool_names
            from hydromcp.tools import HydroModelMCPTools
            
            logger.info("检查MCP工具定义...")
            tool_names = get_all_tool_names()
            
            logger.info("初始化MCP工具实例...")
            mcp_tools = HydroModelMCPTools()
            
            # 测试get_model_params工具
            logger.info("测试get_model_params工具...")
            result = mcp_tools.get_model_params("gr4j")
            
            if result.get("success"):
                self.check_results["mcp_tools"] = {
                    "status": "success",
                    "available_tools": tool_names,
                    "test_result": "get_model_params工作正常"
                }
                logger.info(f"✅ MCP工具正常，可用工具: {', '.join(tool_names)}")
                return True
            else:
                self.check_results["mcp_tools"] = {
                    "status": "error",
                    "message": result.get("error", "未知错误")
                }
                logger.error(f"❌ MCP工具测试失败: {result.get('error')}")
                return False
                
        except Exception as e:
            self.check_results["mcp_tools"] = {"status": "error", "message": str(e)}
            logger.error(f"❌ MCP工具检查失败: {e}")
            return False
    
    def check_data_availability(self) -> bool:
        """检查测试数据可用性"""
        try:
            data_path = project_root / "data" / "camels_11532500"
            required_files = [
                "basin_11532500.csv",
                "basin_attributes.csv"
            ]
            
            logger.info("检查测试数据...")
            missing_files = []
            for file in required_files:
                file_path = data_path / file
                if not file_path.exists():
                    missing_files.append(str(file_path))
            
            if missing_files:
                self.check_results["test_data"] = {
                    "status": "warning",
                    "missing_files": missing_files
                }
                logger.warning(f"⚠️ 部分测试数据缺失: {missing_files}")
                return False
            else:
                self.check_results["test_data"] = {
                    "status": "success",
                    "data_path": str(data_path)
                }
                logger.info("✅ 测试数据完整")
                return True
                
        except Exception as e:
            self.check_results["test_data"] = {"status": "error", "message": str(e)}
            logger.error(f"❌ 测试数据检查失败: {e}")
            return False


class CompleteWorkflowTester:
    """完整工作流测试器"""
    
    def __init__(self):
        self.test_results = {}
        self.start_time = None
        self.end_time = None
        
    async def setup_components(self, ollama_client=None):
        """
        设置系统组件
        
        Args:
            ollama_client: 可选的Ollama客户端实例
        """
        logger.info("=== 设置系统组件 ===")
        
        # 初始化HydroRAG系统
        from hydrorag import RAGSystem
        logger.info("初始化HydroRAG系统...")
        self.rag_system = RAGSystem()
        
        # 设置知识库
        doc_path = project_root / "documents"
        if doc_path.exists():
            logger.info("📚 正在设置知识库...")
            setup_result = self.rag_system.setup_from_raw_documents()
            
            if setup_result.get("status") != "success":
                raise RuntimeError(f"RAG系统设置失败: {setup_result}")
                
            logger.info("✅ 知识库设置完成")
        else:
            logger.warning("⚠️ 未找到documents文件夹")
        logger.info("✅ HydroRAG系统初始化完成")
        
        # 初始化工作流生成器
        from workflow import create_workflow_generator, GenerationConfig
        config = GenerationConfig(
            llm_model="qwen3:8b",
            enable_validation=True,
            enable_feedback_learning=False,
            rag_retrieval_k=8,  # 增加检索数量
            rag_score_threshold=0.2  # 降低阈值以获取更多相关知识
        )
        self.workflow_generator = create_workflow_generator(
            rag_system=self.rag_system,
            ollama_client=ollama_client,
            config=config
        )
        logger.info("✅ 工作流生成器初始化完成")
        
        # 初始化MCP工具
        from hydromcp.tools import HydroModelMCPTools
        self.mcp_tools = HydroModelMCPTools()
        logger.info("✅ MCP工具初始化完成")
        
    async def test_step1_knowledge_retrieval(self, user_query: str):
        """步骤1：知识库检索测试"""
        logger.info("=== 步骤1：知识库检索 ===")
        
        step_start = time.time()
        
        # 构建检索查询
        enhanced_query = f"{user_query} | prepare_data工具 | calibrate_model工具 | evaluate_model工具"
        
        logger.info(f"用户查询: {user_query}")
        logger.info(f"增强查询: {enhanced_query}")
        
        # 执行检索
        query_result = self.rag_system.query(
            query_text=enhanced_query,
            top_k=8
        )
        
        rag_results = query_result.get("results", []) if query_result.get("status") == "success" else []
        
        step_time = time.time() - step_start
        
        self.test_results["step1_knowledge_retrieval"] = {
            "query": user_query,
            "enhanced_query": enhanced_query,
            "fragments_found": len(rag_results),
            "time_taken": step_time,
            "top_fragments": [
                {
                    "content": result.get("content", "")[:200] + "...",
                    "score": result.get("score", 0),
                    "source": result.get("metadata", {}).get("source_file", "unknown")
                }
                for result in rag_results[:3]
            ]
        }
        
        logger.info(f"✅ 知识检索完成，找到{len(rag_results)}个相关片段，耗时{step_time:.2f}秒")
        
        return rag_results
    
    async def test_step2_workflow_generation(self, user_query: str):
        """步骤2：工作流生成测试"""
        logger.info("=== 步骤2：工作流生成 ===")
        
        step_start = time.time()
        
        # 生成工作流
        logger.info(f"生成工作流: {user_query}")
        generation_result = self.workflow_generator.generate_workflow(user_query)
        
        step_time = time.time() - step_start
        
        if generation_result.success and generation_result.workflow:
            workflow = generation_result.workflow
            
            self.test_results["step2_workflow_generation"] = {
                "success": True,
                "workflow_id": workflow.workflow_id,
                "workflow_name": workflow.name,
                "task_count": len(workflow.tasks),
                "validation_issues": len(workflow.validation_issues),
                "time_taken": step_time,
                "tasks": [
                    {
                        "task_id": task.task_id,
                        "name": task.name,
                        "action": task.action,
                        "task_type": task.task_type.value,
                        "parameters": task.parameters,
                        "dependencies": task.dependencies
                    }
                    for task in workflow.tasks
                ],
                "issues": [
                    {
                        "type": issue.issue_type.value,
                        "message": issue.message,
                        "suggestion": issue.suggestion
                    }
                    for issue in workflow.validation_issues
                ]
            }
            
            logger.info(f"✅ 工作流生成成功")
            logger.info(f"   - 工作流ID: {workflow.workflow_id}")
            logger.info(f"   - 任务数量: {len(workflow.tasks)}")
            logger.info(f"   - 验证问题: {len(workflow.validation_issues)}")
            logger.info(f"   - 生成时间: {step_time:.2f}秒")
            
            # 显示任务详情
            for i, task in enumerate(workflow.tasks, 1):
                logger.info(f"   任务{i}: {task.name} (工具: {task.action})")
            
            return workflow
        else:
            self.test_results["step2_workflow_generation"] = {
                "success": False,
                "error": generation_result.error_message,
                "time_taken": step_time
            }
            
            logger.error(f"❌ 工作流生成失败: {generation_result.error_message}")
            return None
    
    async def test_step3_tool_execution(self, workflow):
        """步骤3：MCP工具执行测试"""
        logger.info("=== 步骤3：MCP工具执行 ===")
        
        step_start = time.time()
        execution_results = []
        
        # 按执行顺序处理任务
        for order_group in workflow.execution_order:
            for task_id in order_group:
                task = next((t for t in workflow.tasks if t.task_id == task_id), None)
                if not task:
                    continue
                
                logger.info(f"执行任务: {task.name} (工具: {task.action})")
                
                task_start = time.time()
                
                try:
                    # 调用对应的MCP工具
                    if task.action == "get_model_params":
                        result = self.mcp_tools.get_model_params(**task.parameters)
                    elif task.action == "prepare_data":
                        result = self.mcp_tools.prepare_data(**task.parameters)
                    elif task.action == "calibrate_model":
                        result = self.mcp_tools.calibrate_model(**task.parameters)
                    elif task.action == "evaluate_model":
                        result = self.mcp_tools.evaluate_model(**task.parameters)
                    else:
                        result = {
                            "success": False,
                            "error": f"不支持的工具: {task.action}"
                        }
                    
                    task_time = time.time() - task_start
                    
                    task_result = {
                        "task_id": task.task_id,
                        "task_name": task.name,
                        "tool": task.action,
                        "success": result.get("success", False),
                        "time_taken": task_time,
                        "result": result
                    }
                    
                    if result.get("success"):
                        logger.info(f"   ✅ 任务成功，耗时{task_time:.2f}秒")
                    else:
                        logger.error(f"   ❌ 任务失败: {result.get('error', '未知错误')}")
                    
                    execution_results.append(task_result)
                    
                except Exception as e:
                    task_time = time.time() - task_start
                    task_result = {
                        "task_id": task.task_id,
                        "task_name": task.name,
                        "tool": task.action,
                        "success": False,
                        "time_taken": task_time,
                        "error": str(e)
                    }
                    execution_results.append(task_result)
                    logger.error(f"   ❌ 任务执行异常: {e}")
        
        step_time = time.time() - step_start
        
        # 统计执行结果
        successful_tasks = len([r for r in execution_results if r["success"]])
        total_tasks = len(execution_results)
        success_rate = successful_tasks / total_tasks if total_tasks > 0 else 0
        
        self.test_results["step3_tool_execution"] = {
            "total_tasks": total_tasks,
            "successful_tasks": successful_tasks,
            "success_rate": success_rate,
            "total_time": step_time,
            "task_results": execution_results
        }
        
        logger.info(f"✅ 工具执行完成")
        logger.info(f"   - 总任务数: {total_tasks}")
        logger.info(f"   - 成功任务: {successful_tasks}")
        logger.info(f"   - 成功率: {success_rate:.1%}")
        logger.info(f"   - 总耗时: {step_time:.2f}秒")
        
        return execution_results
    
    async def run_complete_test(self, user_query: str, ollama_client=None):
        """
        运行完整测试流程
        
        Args:
            user_query: 用户查询
            ollama_client: 可选的Ollama客户端实例
        """
        logger.info("🚀 开始完整系统集成测试")
        logger.info("=" * 60)
        
        self.start_time = time.time()
        
        try:
            # 设置组件
            await self.setup_components(ollama_client=ollama_client)
            
            # 步骤1：知识库检索
            rag_results = await self.test_step1_knowledge_retrieval(user_query)
            
            # 步骤2：工作流生成
            workflow = await self.test_step2_workflow_generation(user_query)
            
            if workflow is None:
                raise Exception("工作流生成失败，无法继续测试")
            
            # 步骤3：工具执行
            execution_results = await self.test_step3_tool_execution(workflow)
            
            self.end_time = time.time()
            total_time = self.end_time - self.start_time
            
            # 生成测试总结
            self.test_results["summary"] = {
                "user_query": user_query,
                "total_time": total_time,
                "overall_success": workflow is not None and len(execution_results) > 0,
                "steps_completed": 3,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            logger.info("=" * 60)
            logger.info("🎉 完整测试流程完成")
            logger.info(f"总耗时: {total_time:.2f}秒")
            
            return True
            
        except Exception as e:
            self.end_time = time.time()
            total_time = self.end_time - self.start_time if self.start_time else 0
            
            self.test_results["summary"] = {
                "user_query": user_query,
                "total_time": total_time,
                "overall_success": False,
                "error": str(e),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            logger.error(f"❌ 测试流程失败: {e}")
            return False
    
    def save_test_results(self):
        """保存测试结果"""
        results_file = project_root / "test" / "integration_test_results.json"
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_results, f, ensure_ascii=False, indent=2, default=str)
        
        logger.info(f"测试结果已保存到: {results_file}")
    
    def print_summary(self):
        """打印测试总结"""
        print("\n" + "=" * 60)
        print("📊 测试总结")
        print("=" * 60)
        
        summary = self.test_results.get("summary", {})
        print(f"用户查询: {summary.get('user_query', 'N/A')}")
        print(f"总体成功: {'✅' if summary.get('overall_success') else '❌'}")
        print(f"总耗时: {summary.get('total_time', 0):.2f}秒")
        print(f"测试时间: {summary.get('timestamp', 'N/A')}")
        
        # 各步骤详情
        steps = [
            ("知识库检索", "step1_knowledge_retrieval"),
            ("工作流生成", "step2_workflow_generation"),
            ("工具执行", "step3_tool_execution")
        ]
        
        print(f"\n各步骤结果:")
        for step_name, step_key in steps:
            step_data = self.test_results.get(step_key, {})
            if step_key == "step1_knowledge_retrieval":
                status = "✅" if step_data.get("fragments_found", 0) > 0 else "❌"
                print(f"  {step_name}: {status} (找到{step_data.get('fragments_found', 0)}个片段)")
            elif step_key == "step2_workflow_generation":
                status = "✅" if step_data.get("success") else "❌"
                print(f"  {step_name}: {status} (生成{step_data.get('task_count', 0)}个任务)")
            elif step_key == "step3_tool_execution":
                success_rate = step_data.get("success_rate", 0)
                status = "✅" if success_rate > 0.5 else "❌"
                print(f"  {step_name}: {status} (成功率{success_rate:.1%})")


async def main(ollama_client=None):
    """
    主函数
    
    Args:
        ollama_client: Ollama客户端实例，如果为None则会尝试创建新的客户端
    """
    print("🚀 HydroAgent完整系统集成测试")
    print("=" * 60)
    
    # 测试用户查询
    user_query = "整理数据camels_11532500流域，用其率定GR4J模型，并评估模型"
    
    print(f"测试查询: {user_query}")
    print(f"测试目标: 验证 ollama + 知识库 + 工作流 + MCP工具 的完整集成")
    print()
    
    # 1. 系统组件检查
    print("=== 系统组件检查 ===")
    checker = SystemComponentChecker()
    
    # 如果提供了Ollama客户端，跳过连接检查
    checks = []
    if ollama_client is None:
        checks.append(("Ollama连接", checker.check_ollama_connection))
    else:
        print("✅ 使用已有的Ollama客户端")
        
    checks.extend([
        ("HydroRAG知识库", checker.check_hydrorag_system),
        ("工作流生成器", lambda: checker.check_workflow_generator(ollama_client)),
        ("MCP工具", checker.check_mcp_tools),
        ("测试数据", checker.check_data_availability)
    ])
    
    all_checks_passed = True
    for check_name, check_func in checks:
        print(f"检查 {check_name}...")
        if not check_func():
            all_checks_passed = False
    
    print(f"\n组件检查结果: {'✅ 全部通过' if all_checks_passed else '❌ 部分失败'}")
    
    if not all_checks_passed:
        print("⚠️ 部分组件检查失败，测试可能无法正常进行")
        print("检查结果详情:")
        for component, result in checker.check_results.items():
            status = result.get("status", "unknown")
            message = result.get("message", "")
            print(f"  {component}: {status} {message}")
        
        # 询问是否继续
        print("\n是否继续进行集成测试？(y/n)")
        # response = input().lower()
        # if response != 'y':
        #     print("测试取消")
        #     return
        print("自动继续测试...")
    
    print("\n" + "=" * 60)
    
    # 2. 完整工作流测试
    tester = CompleteWorkflowTester()
    
    try:
        success = await tester.run_complete_test(user_query, ollama_client)
        
        # 保存测试结果
        tester.save_test_results()
        
        # 打印总结
        tester.print_summary()
        
        if success:
            print(f"\n🎉 集成测试成功完成！")
        else:
            print(f"\n❌ 集成测试失败")
            
    except Exception as e:
        logger.error(f"测试过程中发生异常: {e}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    # 运行完整测试
    asyncio.run(main())

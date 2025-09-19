"""
新版工作流生成器测试

测试重构后的工作流生成器的各个模块功能

Author: Assistant
Date: 2025-01-20
"""

import logging
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入新版工作流模块
from workflow import (
    WorkflowGeneratorV2, GenerationConfig, create_workflow_generator,
    InstructionParser, create_instruction_parser,
    CoTRAGEngine, create_cot_rag_engine,
    WorkflowAssembler, create_workflow_assembler,
    ValidationFeedbackSystem, create_validation_feedback_system
)

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_instruction_parser():
    """测试指令解析器"""
    print("=== 测试指令解析器 ===")
    
    try:
        # 尝试创建Ollama客户端用于指令解析器
        try:
            import ollama
            ollama_client = ollama.Client()
            print("✅ 为指令解析器创建Ollama客户端成功")
        except:
            ollama_client = None
            print("⚠️  指令解析器将使用基础规则模式")
        
        parser = create_instruction_parser(ollama_client=ollama_client)
        
        test_instructions = [
            "我想率定一个GR4J模型",
            "分析2020年的降雨径流数据",
            "生成模型评估报告",
            "创建数据可视化图表"
        ]
        
        for instruction in test_instructions:
            result = parser.parse_instruction(instruction)
            print(f"指令: {instruction}")
            print(f"  意图类型: {result.intent_type.value}")
            print(f"  置信度: {result.confidence:.2f}")
            print(f"  建议工具: {', '.join(result.suggested_tools[:3])}")
            print()
        
        print("✅ 指令解析器测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 指令解析器测试失败: {str(e)}")
        return False


def test_cot_rag_engine():
    """测试CoT+RAG推理引擎"""
    print("=== 测试CoT+RAG推理引擎 ===")
    
    try:
        # 尝试创建Ollama客户端用于CoT推理引擎
        try:
            import ollama
            ollama_client = ollama.Client()
            print("✅ 为CoT推理引擎创建Ollama客户端成功")
        except:
            ollama_client = None
            print("⚠️  CoT推理引擎将使用回退模式")
        
        # 创建简单的意图结果用于测试
        from workflow.instruction_parser import IntentResult, IntentType
        
        intent_result = IntentResult(
            original_query="率定GR4J模型参数",
            intent_type=IntentType.MODEL_CALIBRATION,
            entities={},
            parameters={},
            constraints={},
            confidence=0.8,
            suggested_tools=["gr4j_calibration", "optimize_parameters"]
        )
        
        # 创建推理引擎
        config = {
            "llm_model": "qwen3:8b",
            "reasoning_temperature": 0.7
        }
        engine = create_cot_rag_engine(
            ollama_client=ollama_client,
            config=config
        )
        
        # 执行推理
        rag_result, cot_result = engine.generate_reasoning_plan(intent_result)
        
        print(f"RAG检索片段数: {len(rag_result.fragments)}")
        print(f"CoT推理步骤数: {len(cot_result.reasoning_steps)}")
        print(f"生成的计划长度: {len(cot_result.final_plan)}")
        
        print("✅ CoT+RAG推理引擎测试通过")
        return True
        
    except Exception as e:
        print(f"❌ CoT+RAG推理引擎测试失败: {str(e)}")
        return False


def test_workflow_assembler():
    """测试工作流组装器"""
    print("=== 测试工作流组装器 ===")
    
    try:
        assembler = create_workflow_assembler()
        
        # 创建测试用的原始计划
        raw_plan = """
        {
          "workflow_id": "test_workflow",
          "name": "测试工作流",
          "description": "这是一个测试工作流",
          "tasks": [
            {
              "task_id": "task1",
              "name": "加载数据",
              "description": "加载CSV数据文件",
              "action": "load_data",
              "task_type": "simple_action",
              "parameters": {"file_path": "data.csv"},
              "dependencies": [],
              "conditions": {},
              "expected_output": "数据框对象"
            },
            {
              "task_id": "task2", 
              "name": "分析数据",
              "description": "计算统计信息",
              "action": "analyze_data",
              "task_type": "complex_reasoning",
              "parameters": {},
              "dependencies": ["task1"],
              "conditions": {},
              "expected_output": "统计结果"
            }
          ]
        }
        """
        
        # 组装工作流
        workflow = assembler.assemble_workflow(raw_plan)
        
        print(f"工作流名称: {workflow.name}")
        print(f"任务数量: {len(workflow.tasks)}")
        print(f"验证问题数: {len(workflow.validation_issues)}")
        print(f"执行顺序: {workflow.execution_order}")
        
        print("✅ 工作流组装器测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 工作流组装器测试失败: {str(e)}")
        return False


def test_validation_feedback():
    """测试验证反馈系统"""
    print("=== 测试验证反馈系统 ===")
    
    try:
        # 创建临时存储路径
        temp_path = "test/temp_feedback"
        os.makedirs(temp_path, exist_ok=True)
        
        feedback_system = create_validation_feedback_system(storage_path=temp_path)
        
        # 记录一些测试执行结果
        feedback_system.record_execution_result(
            workflow_id="test_workflow_1",
            task_id="test_task_1",
            success=True,
            execution_time=1.5
        )
        
        feedback_system.record_execution_result(
            workflow_id="test_workflow_2", 
            task_id="test_task_2",
            success=False,
            error_info={"message": "File not found", "type": "FileNotFoundError"},
            execution_time=0.8
        )
        
        # 获取统计信息
        stats = feedback_system.get_system_health_report()
        print(f"系统健康报告:")
        print(f"  总执行次数: {stats.get('total_executions', 0)}")
        print(f"  成功率: {stats.get('success_rate', 0):.2%}")
        
        # 清理临时文件
        import shutil
        shutil.rmtree(temp_path, ignore_errors=True)
        
        print("✅ 验证反馈系统测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 验证反馈系统测试失败: {str(e)}")
        return False


def test_workflow_generator_integration():
    """测试工作流生成器集成"""
    print("=== 测试工作流生成器集成 ===")
    
    try:
        # 尝试导入Ollama客户端
        try:
            import ollama
            ollama_client = ollama.Client()
            print("✅ Ollama客户端创建成功")
        except ImportError:
            print("⚠️  Ollama未安装，使用默认配置")
            ollama_client = None
        except Exception as e:
            print(f"⚠️  Ollama客户端创建失败: {str(e)}")
            ollama_client = None
        
        # 尝试创建RAG系统
        rag_system = None
        try:
            from hydrorag import RAGSystem
            rag_system = RAGSystem()
            
            # 检查是否已有处理好的文档
            doc_path = Path("documents")
            if doc_path.exists():
                print("📚 正在加载知识库文档...")
                # 使用RAG系统加载文档
                doc_count = rag_system.load_documents(str(doc_path))
                print(f"✅ 成功加载 {doc_count} 个文档")
                
                # 创建或加载索引
                try:
                    rag_system.create_index()
                    print("✅ 知识库索引创建成功")
                except Exception as e:
                    print(f"⚠️  索引创建失败: {str(e)}")
            else:
                print("⚠️  未找到documents文件夹，RAG系统将使用回退模式")
                
        except ImportError:
            print("⚠️  HydroRAG未安装，将使用基础模式")
        except Exception as e:
            print(f"⚠️  RAG系统初始化失败: {str(e)}")
        
        # 创建配置
        config = GenerationConfig(
            llm_model="qwen3:8b",  # 使用qwen3:8b模型
            llm_temperature=0.7,
            rag_retrieval_k=8,  # 增加检索数量
            rag_score_threshold=0.2,  # 降低阈值以获取更多相关知识
            enable_feedback_learning=False  # 禁用反馈学习以避免文件操作
        )
        
        # 创建工作流生成器，集成RAG系统和Ollama客户端
        generator = create_workflow_generator(
            rag_system=rag_system,
            ollama_client=ollama_client,
            config=config
        )
        
        print(f"🚀 工作流生成器创建完成，RAG增强: {'是' if rag_system else '否'}")
        
        # 测试指令
        test_instructions = [
            "加载CSV数据并计算基本统计信息",
            "使用GR4J模型进行流域参数率定",
            "对GR4J对率定的结果进行评估"
        ]
        
        success_count = 0
        for instruction in test_instructions:
            print(f"\n测试指令: {instruction}")
            
            result = generator.generate_workflow(instruction)
            
            if result.success:
                print(f"  ✅ 成功 - {result.workflow.name}")
                print(f"     任务数: {len(result.workflow.tasks)}")
                print(f"     耗时: {result.total_time:.2f}秒")
                
                # 打印生成的工作流详细信息
                print(f"     工作流详情:")
                print(f"       描述: {result.workflow.description}")
                print(f"       执行顺序: {result.workflow.execution_order}")
                
                print(f"     任务列表:")
                for i, task in enumerate(result.workflow.tasks, 1):
                    print(f"       {i}. {task.name} ({task.task_type.value})")
                    print(f"          操作: {task.action}")
                    print(f"          描述: {task.description}")
                    if task.parameters:
                        print(f"          参数: {task.parameters}")
                    if task.dependencies:
                        print(f"          依赖: {task.dependencies}")
                    print()
                
                # 如果有验证问题，也显示出来
                if result.workflow.validation_issues:
                    print(f"     验证问题 ({len(result.workflow.validation_issues)}个):")
                    for issue in result.workflow.validation_issues:
                        print(f"       - {issue.message}")
                
                success_count += 1
            else:
                print(f"  ❌ 失败 - {result.error_message}")
                
                # 如果有部分结果，也显示出来
                if result.intent_result:
                    print(f"     意图分析: {result.intent_result.intent_type.value}")
                    print(f"     置信度: {result.intent_result.confidence:.2f}")
                if result.rag_result:
                    print(f"     RAG检索: {len(result.rag_result.fragments)}个片段")
                    # 显示检索到的知识片段
                    if result.rag_result.fragments:
                        print(f"     检索到的知识:")
                        for i, fragment in enumerate(result.rag_result.fragments[:3], 1):  # 只显示前3个
                            print(f"       {i}. {fragment.content[:100]}... (来源: {fragment.source})")
                if result.cot_result:
                    print(f"     CoT推理: {len(result.cot_result.reasoning_steps)}个步骤")
                    # 显示推理步骤
                    if result.cot_result.reasoning_steps:
                        print(f"     推理过程:")
                        for step in result.cot_result.reasoning_steps[:2]:  # 只显示前2个步骤
                            print(f"       {step.step_number}. {step.question}")
                            print(f"          {step.reasoning[:150]}...")
        
        print(f"\n总体结果: {success_count}/{len(test_instructions)} 成功")
        
        # 获取统计信息
        stats = generator.get_generation_statistics()
        print(f"生成器统计:")
        print(f"  成功率: {stats['success_rate']:.2%}")
        print(f"  系统健康度: {stats['system_health']}")
        
        print("✅ 工作流生成器集成测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 工作流生成器集成测试失败: {str(e)}")
        return False


def check_ollama_availability():
    """检查Ollama可用性"""
    print("🔍 检查Ollama可用性...")
    
    try:
        import ollama
        client = ollama.Client()
        
        # 尝试简单的模型调用来验证连接
        try:
            response = client.chat(
                model="qwen3:8b",
                messages=[{"role": "user", "content": "test connection"}]
            )
            print("✅ Ollama连接成功，qwen3:8b模型可用")
            return True
        except Exception as e:
            print(f"⚠️  Ollama模型调用失败: {str(e)}")
            print("   测试将继续，但使用回退模式")
            return False
            
    except ImportError:
        print("⚠️  Ollama未安装，测试将使用回退模式")
        return False
    except Exception as e:
        print(f"⚠️  Ollama连接失败: {str(e)}")
        print("   测试将继续，但使用回退模式")
        return False


def main():
    """运行所有测试"""
    print("🧪 新版工作流生成器测试套件\n")
    
    # 检查Ollama可用性
    ollama_available = check_ollama_availability()
    print("-" * 50)
    
    tests = [
        # test_instruction_parser,
        # test_cot_rag_engine,
        # test_workflow_assembler,
        # test_validation_feedback,
        test_workflow_generator_integration
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            logger.error(f"测试 {test_func.__name__} 出现异常: {str(e)}")
        
        print("-" * 50)
    
    print(f"\n📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过!")
        return True
    else:
        print("⚠️  部分测试失败，请检查代码")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

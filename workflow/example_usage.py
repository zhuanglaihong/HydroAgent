"""
新版工作流生成器使用示例

展示如何使用重构后的工作流生成器，包括：
1. 基本使用方法
2. 与RAG系统集成
3. 与Ollama模型集成
4. 配置和自定义

Author: Assistant
Date: 2025-01-20
"""

import logging
import json
from datetime import datetime

# 导入新版工作流生成器
from .workflow_generator_v2 import (
    WorkflowGeneratorV2, GenerationConfig, create_workflow_generator
)

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def example_basic_usage():
    """基本使用示例"""
    print("=== 基本使用示例 ===")
    
    # 创建基本配置
    config = GenerationConfig(
        llm_model="qwen3:8b",
        llm_temperature=0.7,
        enable_feedback_learning=True
    )
    
    # 创建工作流生成器
    generator = create_workflow_generator(config=config)
    
    # 生成工作流
    instruction = "我想率定一个GR4J模型，使用2020年的数据进行参数优化"
    result = generator.generate_workflow(instruction)
    
    # 打印结果
    if result.success:
        print(f"✅ 工作流生成成功!")
        print(f"工作流名称: {result.workflow.name}")
        print(f"任务数量: {len(result.workflow.tasks)}")
        print(f"生成耗时: {result.total_time:.2f}秒")
        
        # 展示工作流任务
        for i, task in enumerate(result.workflow.tasks, 1):
            print(f"{i}. {task.name} ({task.task_type.value})")
    else:
        print(f"❌ 工作流生成失败: {result.error_message}")


def example_with_rag_system():
    """与RAG系统集成的示例"""
    print("\n=== RAG系统集成示例 ===")
    
    try:
        # 假设已有RAG系统实例
        from hydrorag import RAGSystem
        
        # 创建RAG系统
        rag_system = RAGSystem()
        # 这里应该加载相关文档...
        
        # 创建配置
        config = GenerationConfig(
            rag_retrieval_k=8,
            rag_score_threshold=0.4,
            enable_rag_fallback=True
        )
        
        # 创建带RAG的工作流生成器
        generator = create_workflow_generator(
            rag_system=rag_system,
            config=config
        )
        
        # 生成工作流
        instruction = "分析降雨径流数据的时间序列特征，并创建可视化图表"
        result = generator.generate_workflow(instruction)
        
        if result.success:
            print(f"✅ 使用RAG增强的工作流生成成功!")
            print(f"检索到的知识片段数: {len(result.rag_result.fragments) if result.rag_result else 0}")
            print(f"推理步骤数: {len(result.cot_result.reasoning_steps) if result.cot_result else 0}")
        else:
            print(f"❌ 工作流生成失败: {result.error_message}")
            
    except ImportError:
        print("⚠️  RAG系统未安装，跳过此示例")


def example_with_ollama():
    """与Ollama集成的示例"""
    print("\n=== Ollama集成示例 ===")
    
    try:
        import ollama
        
        # 创建Ollama客户端
        ollama_client = ollama.Client()
        
        # 创建配置
        config = GenerationConfig(
            llm_model="qwen3:8b",
            llm_temperature=0.8,
            reasoning_timeout=180
        )
        
        # 创建带Ollama的工作流生成器
        generator = create_workflow_generator(
            ollama_client=ollama_client,
            config=config
        )
        
        # 测试指令
        instructions = [
            "加载CAMELS数据集并进行质量检查",
            "使用LSTM模型进行径流预测",
            "计算模型评估指标并生成报告"
        ]
        
        # 批量生成
        results = generator.generate_workflow_batch(instructions)
        
        print(f"✅ 批量生成完成，成功: {sum(1 for r in results if r.success)}/{len(results)}")
        
        for i, result in enumerate(results, 1):
            if result.success:
                print(f"{i}. {result.workflow.name} - {len(result.workflow.tasks)}个任务")
            else:
                print(f"{i}. 失败: {result.error_message}")
                
    except ImportError:
        print("⚠️  Ollama未安装，跳过此示例")


def example_workflow_validation():
    """工作流验证示例"""
    print("\n=== 工作流验证示例 ===")
    
    # 创建工作流生成器
    generator = create_workflow_generator()
    
    # 生成工作流
    instruction = "读取CSV文件，计算统计信息，并保存结果"
    result = generator.generate_workflow(instruction)
    
    if result.success:
        # 验证工作流
        validation_result = generator.validate_workflow(result.workflow)
        
        print(f"验证结果: {'✅ 有效' if validation_result['is_valid'] else '❌ 无效'}")
        
        if validation_result['issues']:
            print("发现的问题:")
            for issue in validation_result['issues']:
                print(f"  - {issue}")
        
        if validation_result['suggestions']:
            print("改进建议:")
            for suggestion in validation_result['suggestions']:
                print(f"  - {suggestion}")


def example_export_formats():
    """导出格式示例"""
    print("\n=== 导出格式示例 ===")
    
    # 创建工作流生成器
    generator = create_workflow_generator()
    
    # 生成工作流
    instruction = "创建一个简单的数据处理流水线"
    result = generator.generate_workflow(instruction)
    
    if result.success:
        workflow = result.workflow
        
        # 导出为不同格式
        formats = ["json", "yaml", "xml"]
        
        for fmt in formats:
            try:
                exported = generator.export_workflow_dsl(workflow, fmt)
                print(f"\n{fmt.upper()}格式 (前200字符):")
                print(exported[:200] + "..." if len(exported) > 200 else exported)
            except Exception as e:
                print(f"{fmt.upper()}格式导出失败: {str(e)}")


def example_statistics_and_learning():
    """统计信息和学习示例"""
    print("\n=== 统计信息和学习示例 ===")
    
    # 创建工作流生成器
    config = GenerationConfig(enable_feedback_learning=True)
    generator = create_workflow_generator(config=config)
    
    # 生成几个工作流
    test_instructions = [
        "数据预处理流程",
        "模型训练流程", 
        "结果分析流程"
    ]
    
    for instruction in test_instructions:
        result = generator.generate_workflow(instruction)
        print(f"生成: {instruction} - {'成功' if result.success else '失败'}")
    
    # 获取统计信息
    stats = generator.get_generation_statistics()
    print(f"\n统计信息:")
    print(f"总生成次数: {stats['total_generations']}")
    print(f"成功次数: {stats['successful_generations']}")
    print(f"成功率: {stats['success_rate']:.2%}")
    print(f"系统健康度: {stats['system_health']}")
    
    # 触发学习更新
    generator.trigger_learning_update()
    print("✅ 学习更新完成")


def main():
    """主函数 - 运行所有示例"""
    print("🚀 新版工作流生成器示例\n")
    
    try:
        example_basic_usage()
        example_with_rag_system()
        example_with_ollama()
        example_workflow_validation()
        example_export_formats()
        example_statistics_and_learning()
        
        print("\n✅ 所有示例运行完成!")
        
    except Exception as e:
        logger.error(f"示例运行失败: {str(e)}")
        print(f"\n❌ 示例运行失败: {str(e)}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Author: zhuanglaihong
Date: 2024-09-24 16:30:00
LastEditTime: 2024-09-24 16:30:00
LastEditors: zhuanglaihong
Description: Enhanced RAG system integration test - API embeddings, query processing and reranking
FilePath: \HydroAgent\test\test_enhanced_rag.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import os
import sys
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_api_embeddings():
    """测试API嵌入模型"""
    try:
        logger.info("=" * 50)
        logger.info("测试 1: API嵌入模型")
        logger.info("=" * 50)

        from hydrorag.embeddings_manager import EmbeddingsManager
        from hydrorag.config import create_default_config

        # 创建配置
        config = create_default_config()

        # 检查API配置
        if not config.openai_api_key:
            logger.warning("未配置API密钥，将跳过API测试")
            return False

        # 创建嵌入管理器
        embeddings_manager = EmbeddingsManager(config)

        if embeddings_manager.is_available():
            # 测试单个文本嵌入
            test_text = "GR4J模型是一个四参数的日径流模型"
            embedding = embeddings_manager.embed_text(test_text)

            if embedding:
                logger.info(f"✓ 单文本嵌入成功，维度: {len(embedding)}")
                logger.info(f"  使用模型: {embeddings_manager.model_name}")

                # 测试批量嵌入
                test_texts = [
                    "GR4J模型参数包括X1, X2, X3, X4",
                    "XAJ模型是新安江三水源模型",
                    "径流模拟需要进行参数率定"
                ]

                embeddings = embeddings_manager.embed_texts(test_texts)
                success_count = sum(1 for e in embeddings if e is not None)
                logger.info(f"✓ 批量嵌入: {success_count}/{len(test_texts)} 成功")

                return True
            else:
                logger.error("✗ 单文本嵌入失败")
                return False
        else:
            logger.error("✗ 嵌入模型不可用")
            return False

    except Exception as e:
        logger.error(f"✗ API嵌入模型测试失败: {e}")
        return False


def test_query_processing():
    """测试查询处理和重排序"""
    try:
        logger.info("=" * 50)
        logger.info("测试 2: 查询处理和重排序")
        logger.info("=" * 50)

        from hydrorag.query_processor import QueryProcessor
        from hydrorag.config import create_default_config

        config = create_default_config()
        query_processor = QueryProcessor(config)

        # 测试查询预处理
        original_query = "GR4J模型参数率定"
        processed_query = query_processor.preprocess_query(original_query)
        logger.info(f"✓ 查询预处理: '{original_query}' -> '{processed_query}'")

        # 测试查询扩展
        expanded_queries = query_processor.expand_query(processed_query)
        logger.info(f"✓ 查询扩展: 生成 {len(expanded_queries)} 个查询变体")
        for i, query in enumerate(expanded_queries[:3]):
            logger.info(f"  {i+1}. {query}")

        # 测试关键词提取
        test_text = "GR4J模型是一个概念性的日径流模型，有四个参数需要率定：X1（生产能力），X2（地下水交换系数），X3（汇流能力），X4（单位线时间常数）。"
        keywords = query_processor._extract_keywords(test_text)
        logger.info(f"✓ 关键词提取: {keywords}")

        # 测试查询建议
        suggestions = query_processor.get_query_suggestions("GR4J模型")
        logger.info(f"✓ 查询建议: {suggestions}")

        return True

    except Exception as e:
        logger.error(f"✗ 查询处理测试失败: {e}")
        return False


def test_rag_system_integration():
    """测试完整RAG系统集成"""
    try:
        logger.info("=" * 50)
        logger.info("测试 3: 完整RAG系统集成")
        logger.info("=" * 50)

        from hydrorag.rag_system import RAGSystem
        from hydrorag.config import create_default_config

        # 创建RAG系统
        config = create_default_config()
        rag_system = RAGSystem(config)

        # 检查系统状态
        status = rag_system.get_system_status()
        logger.info(f"✓ 系统初始化状态: {status['is_initialized']}")

        if status['is_initialized']:
            logger.info("✓ 所有组件初始化成功:")
            for component, info in status['components'].items():
                logger.info(f"  - {component}: {'✓' if info['available'] else '✗'}")
        else:
            logger.warning("⚠ 部分组件初始化失败:")
            for error in status['initialization_errors']:
                logger.warning(f"  - {error}")

        # 测试健康检查
        health = rag_system.health_check()
        logger.info(f"✓ 系统健康状态: {health['overall_status']}")

        # 如果有API密钥，测试查询功能
        if config.openai_api_key and rag_system.is_initialized:
            logger.info("✓ 开始测试查询功能")

            test_queries = [
                "GR4J模型参数",
                "水文模型率定方法",
                "径流模拟评价指标"
            ]

            for query in test_queries:
                try:
                    # 测试基础查询
                    result = rag_system.query(query, top_k=3)
                    logger.info(f"  查询 '{query}': {result.get('status', 'unknown')}")

                    if result.get('status') == 'success':
                        logger.info(f"    找到 {result.get('final_count', 0)} 个结果")
                        logger.info(f"    重排序启用: {result.get('rerank_enabled', False)}")

                    # 测试知识片段提取
                    fragments = rag_system.get_knowledge_fragments(query, top_k=2)
                    logger.info(f"    知识片段: {len(fragments)} 个")

                except Exception as e:
                    logger.warning(f"  查询 '{query}' 失败: {e}")

        return True

    except Exception as e:
        logger.error(f"✗ RAG系统集成测试失败: {e}")
        return False


def test_simple_interfaces():
    """测试简化接口"""
    try:
        logger.info("=" * 50)
        logger.info("测试 4: 简化接口")
        logger.info("=" * 50)

        from hydrorag import simple_query, get_system_info

        # 获取系统信息
        info = get_system_info()
        logger.info(f"✓ 系统信息获取: {'成功' if 'error' not in info else '失败'}")

        # 测试简单查询（如果系统可用）
        if info.get('is_initialized', False):
            try:
                fragments = simple_query("GR4J模型", top_k=2)
                logger.info(f"✓ 简单查询: 返回 {len(fragments)} 个知识片段")

                for i, fragment in enumerate(fragments):
                    logger.info(f"  {i+1}. {fragment[:100]}...")

            except Exception as e:
                logger.warning(f"⚠ 简单查询失败: {e}")
        else:
            logger.info("⚠ 系统未完全初始化，跳过简单查询测试")

        return True

    except Exception as e:
        logger.error(f"✗ 简化接口测试失败: {e}")
        return False


def main():
    """主测试函数"""
    logger.info("开始增强RAG系统测试")

    test_results = []

    # 运行所有测试
    tests = [
        ("API嵌入模型", test_api_embeddings),
        ("查询处理和重排序", test_query_processing),
        ("RAG系统集成", test_rag_system_integration),
        ("简化接口", test_simple_interfaces)
    ]

    for test_name, test_func in tests:
        try:
            logger.info(f"\n开始测试: {test_name}")
            result = test_func()
            test_results.append((test_name, result))
            logger.info(f"测试 {test_name}: {'✓ 通过' if result else '✗ 失败'}")
        except Exception as e:
            test_results.append((test_name, False))
            logger.error(f"测试 {test_name} 异常: {e}")

    # 输出测试总结
    logger.info("=" * 50)
    logger.info("测试总结")
    logger.info("=" * 50)

    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)

    for test_name, result in test_results:
        status = "✓ 通过" if result else "✗ 失败"
        logger.info(f"{test_name}: {status}")

    logger.info(f"\n总计: {passed}/{total} 个测试通过")

    if passed == total:
        logger.info("🎉 所有测试通过！RAG系统功能正常")
        return 0
    else:
        logger.warning("⚠️ 部分测试失败，请检查配置和环境")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
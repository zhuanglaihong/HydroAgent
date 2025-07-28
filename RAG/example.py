"""
Author: zhuanglaihong
Date: 2025-07-24 15:03:46
LastEditTime: 2025-07-24 15:03:46
LastEditors: zhuanglaihong
Description: RAG系统使用示例 - 展示如何在实际场景中使用RAG系统
FilePath: RAG/example.py
Copyright: Copyright (c) 2021-2024 zhuanglaihong. All rights reserved.
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

# 添加项目根目录到路径
repo_path = Path(os.path.abspath(__file__)).parent.parent
sys.path.append(str(repo_path))

import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_sample_documents():
    """创建示例文档"""
    temp_dir = tempfile.mkdtemp()

    # 创建多个示例文档
    documents = {
        "machine_learning.txt": """
        机器学习是人工智能的一个重要分支。
        它通过算法和统计模型使计算机系统能够自动学习和改进。
        机器学习的主要类型包括监督学习、无监督学习和强化学习。
        常见的机器学习算法包括线性回归、决策树、随机森林、支持向量机等。
        深度学习是机器学习的一个子领域，使用多层神经网络进行学习。
        """,
        "deep_learning.txt": """
        深度学习是机器学习的一个子领域，使用多层神经网络。
        深度学习模型可以自动学习特征，无需手动特征工程。
        常见的深度学习架构包括卷积神经网络(CNN)、循环神经网络(RNN)、Transformer等。
        深度学习在计算机视觉、自然语言处理、语音识别等领域取得了突破性进展。
        深度学习需要大量的训练数据和计算资源。
        """,
        "natural_language_processing.txt": """
        自然语言处理(NLP)是人工智能的一个重要应用领域。
        NLP致力于让计算机理解、解释和生成人类语言。
        主要任务包括文本分类、命名实体识别、机器翻译、问答系统等。
        近年来，基于Transformer的模型如BERT、GPT等在NLP领域取得了巨大成功。
        NLP技术广泛应用于搜索引擎、聊天机器人、语音助手等产品中。
        """,
        "computer_vision.txt": """
        计算机视觉是人工智能的另一个重要分支。
        它致力于让计算机理解和分析视觉信息，如图像和视频。
        主要任务包括图像分类、目标检测、图像分割、人脸识别等。
        深度学习在计算机视觉领域取得了革命性进展。
        计算机视觉技术广泛应用于自动驾驶、医疗诊断、安防监控等领域。
        """,
    }

    # 写入文件
    for filename, content in documents.items():
        filepath = os.path.join(temp_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content.strip())

    return temp_dir


def create_mock_models():
    """创建模拟的嵌入模型和语言模型"""

    # 模拟嵌入模型
    class MockEmbeddings:
        def __init__(self):
            self.dimension = 384

        def embed_documents(self, texts):
            """为文档生成嵌入向量"""
            embeddings = []
            for text in texts:
                # 简单的模拟嵌入：基于文本长度和内容生成向量
                import hashlib

                hash_obj = hashlib.md5(text.encode())
                hash_hex = hash_obj.hexdigest()

                # 将哈希值转换为向量
                vector = []
                for i in range(0, len(hash_hex), 2):
                    if len(vector) >= self.dimension:
                        break
                    hex_pair = hash_hex[i : i + 2]
                    vector.append(int(hex_pair, 16) / 255.0)

                # 补齐到指定维度
                while len(vector) < self.dimension:
                    vector.append(0.1)

                embeddings.append(vector[: self.dimension])

            return embeddings

        def embed_query(self, text):
            """为查询生成嵌入向量"""
            return self.embed_documents([text])[0]

    # 模拟语言模型
    class MockLLM:
        def __init__(self):
            self.conversation_history = []

        def __call__(self, prompt):
            """生成回答"""
            # 简单的模拟回答生成
            if "机器学习" in prompt:
                return "机器学习是人工智能的一个分支，通过算法使计算机能够自动学习。"
            elif "深度学习" in prompt:
                return "深度学习使用多层神经网络进行学习，能够自动学习特征。"
            elif "自然语言处理" in prompt:
                return "自然语言处理致力于让计算机理解和生成人类语言。"
            elif "计算机视觉" in prompt:
                return "计算机视觉让计算机理解和分析视觉信息。"
            else:
                return "基于提供的上下文信息，我可以回答您的问题。请提供更具体的问题。"

        def generate(self, prompts):
            """批量生成回答"""
            return [self(prompt) for prompt in prompts]

    return MockEmbeddings(), MockLLM()


def example_basic_usage():
    """基本使用示例"""
    print("=== RAG系统基本使用示例 ===")

    try:
        from RAG import RAGSystem

        # 创建模拟模型
        embeddings, llm = create_mock_models()

        # 创建临时目录
        temp_dir = create_sample_documents()
        index_path = os.path.join(temp_dir, "example_index")

        # 初始化RAG系统
        rag_system = RAGSystem(
            embeddings=embeddings,
            llm=llm,
            index_path=index_path,
            chunk_size=200,
            chunk_overlap=50,
        )

        print("1. 加载文档...")
        doc_count = rag_system.load_documents(temp_dir)
        print(f"   加载了 {doc_count} 个文档块")

        print("2. 创建向量索引...")
        success = rag_system.create_index()
        print(f"   索引创建{'成功' if success else '失败'}")

        print("3. 执行查询...")
        queries = [
            "什么是机器学习？",
            "深度学习有什么特点？",
            "自然语言处理的主要任务有哪些？",
            "计算机视觉的应用领域有哪些？",
        ]

        for i, query in enumerate(queries, 1):
            print(f"\n   查询 {i}: {query}")
            result = rag_system.query(query, k=2)

            if result["success"]:
                print(f"   回答: {result['answer']}")
                print(f"   检索到 {result['retrieved_documents']} 个相关文档")
            else:
                print(f"   错误: {result['error']}")

        print("\n4. 获取系统信息...")
        info = rag_system.get_system_info()
        print(f"   文档数量: {info['documents_loaded']}")
        print(f"   索引状态: {'已创建' if info['index_created'] else '未创建'}")
        print(f"   可用检索器: {info['available_retrievers']}")
        print(f"   可用生成器: {info['available_generators']}")

        # 清理
        shutil.rmtree(temp_dir)

        print("\n✅ 基本使用示例完成")
        return True

    except Exception as e:
        print(f"❌ 基本使用示例失败: {e}")
        return False


def example_advanced_usage():
    """高级使用示例"""
    print("\n=== RAG系统高级使用示例 ===")

    try:
        from RAG import RAGSystem

        # 创建模拟模型
        embeddings, llm = create_mock_models()

        # 创建临时目录
        temp_dir = create_sample_documents()
        index_path = os.path.join(temp_dir, "advanced_index")

        # 初始化RAG系统
        rag_system = RAGSystem(embeddings=embeddings, llm=llm, index_path=index_path)

        print("1. 加载文档并添加元数据...")
        doc_count = rag_system.load_documents(
            source=temp_dir,
            add_metadata={"source": "example_docs", "category": "AI_technology"},
            filter_min_length=30,
            filter_max_length=500,
        )
        print(f"   加载了 {doc_count} 个文档块")

        print("2. 创建索引...")
        success = rag_system.create_index()
        print(f"   索引创建{'成功' if success else '失败'}")

        print("3. 测试不同的检索器...")
        retrievers = ["vector", "bm25", "ensemble"]

        for retriever_name in retrievers:
            if retriever_name in rag_system.get_available_retrievers():
                print(f"\n   使用检索器: {retriever_name}")
                result = rag_system.query(
                    query="什么是深度学习？",
                    retriever_name=retriever_name,
                    k=3,
                    score_threshold=0.1,
                )

                if result["success"]:
                    print(f"   回答: {result['answer']}")
                    print(f"   相似度分数: {result['scores']}")
                else:
                    print(f"   错误: {result['error']}")

        print("4. 测试不同的生成器...")
        generators = ["qa", "summarize", "conversational"]

        for generator_name in generators:
            if generator_name in rag_system.get_available_generators():
                print(f"\n   使用生成器: {generator_name}")
                result = rag_system.query(
                    query="总结人工智能的主要分支", generator_name=generator_name, k=4
                )

                if result["success"]:
                    print(f"   结果: {result['answer']}")
                else:
                    print(f"   错误: {result['error']}")

        print("5. 批量查询...")
        batch_queries = [
            "机器学习有哪些类型？",
            "深度学习与传统机器学习的区别？",
            "NLP的主要应用场景？",
        ]

        batch_results = rag_system.batch_query(
            queries=batch_queries, retriever_name="vector", generator_name="qa", k=2
        )

        for i, result in enumerate(batch_results):
            print(f"\n   批量查询 {i+1}: {result['query']}")
            if result["success"]:
                print(f"   回答: {result['answer']}")
            else:
                print(f"   错误: {result['error']}")

        # 清理
        shutil.rmtree(temp_dir)

        print("\n✅ 高级使用示例完成")
        return True

    except Exception as e:
        print(f"❌ 高级使用示例失败: {e}")
        return False


def example_custom_prompts():
    """自定义提示模板示例"""
    print("\n=== 自定义提示模板示例 ===")

    try:
        from RAG.generator import QAChainGenerator
        from langchain.prompts import PromptTemplate

        # 创建模拟语言模型
        class CustomLLM:
            def __call__(self, prompt):
                return "基于自定义提示模板生成的回答。"

        llm = CustomLLM()

        # 自定义提示模板
        custom_prompt = PromptTemplate(
            template="""
            基于以下上下文信息回答问题：
            
            上下文：{context}
            
            问题：{question}
            
            请提供详细、准确的回答：
            """,
            input_variables=["context", "question"],
        )

        # 创建自定义生成器
        custom_generator = QAChainGenerator(
            llm=llm, chain_type="stuff", prompt_template=custom_prompt.template
        )

        # 测试自定义生成器
        from langchain.schema import Document

        test_docs = [Document(page_content="这是一个测试文档，包含一些示例内容。")]

        result = custom_generator.generate(query="请总结文档内容", context=test_docs)

        print(f"自定义提示模板结果: {result}")
        print("✅ 自定义提示模板示例完成")
        return True

    except Exception as e:
        print(f"❌ 自定义提示模板示例失败: {e}")
        return False


def example_system_management():
    """系统管理示例"""
    print("\n=== 系统管理示例 ===")

    try:
        from RAG import RAGSystem

        # 创建模拟模型
        embeddings, llm = create_mock_models()

        # 创建临时目录
        temp_dir = create_sample_documents()
        index_path = os.path.join(temp_dir, "management_index")
        save_path = os.path.join(temp_dir, "saved_system")

        # 初始化RAG系统
        rag_system = RAGSystem(embeddings=embeddings, llm=llm, index_path=index_path)

        print("1. 加载文档和创建索引...")
        rag_system.load_documents(temp_dir)
        rag_system.create_index()

        print("2. 保存系统状态...")
        save_success = rag_system.save_system(save_path)
        print(f"   保存{'成功' if save_success else '失败'}")

        print("3. 清除系统状态...")
        rag_system.clear_system()
        info_after_clear = rag_system.get_system_info()
        print(f"   清除后文档数量: {info_after_clear['documents_loaded']}")

        print("4. 重新加载系统状态...")
        load_success = rag_system.load_system(save_path)
        print(f"   加载{'成功' if load_success else '失败'}")

        if load_success:
            info_after_load = rag_system.get_system_info()
            print(f"   加载后文档数量: {info_after_load['documents_loaded']}")

            # 测试查询
            result = rag_system.query("什么是机器学习？")
            if result["success"]:
                print(f"   查询测试: {result['answer']}")

        # 清理
        shutil.rmtree(temp_dir)

        print("✅ 系统管理示例完成")
        return True

    except Exception as e:
        print(f"❌ 系统管理示例失败: {e}")
        return False


def main():
    """主函数"""
    print("开始RAG系统使用示例...")

    # 运行各种示例
    examples = [
        ("基本使用", example_basic_usage),
        ("高级使用", example_advanced_usage),
        ("自定义提示", example_custom_prompts),
        ("系统管理", example_system_management),
    ]

    results = []

    for name, example_func in examples:
        print(f"\n{'='*50}")
        print(f"运行示例: {name}")
        print("=" * 50)

        try:
            success = example_func()
            results.append((name, success))
        except Exception as e:
            print(f"示例 {name} 执行失败: {e}")
            results.append((name, False))

    # 总结结果
    print(f"\n{'='*50}")
    print("示例执行总结")
    print("=" * 50)

    for name, success in results:
        status = "✅ 成功" if success else "❌ 失败"
        print(f"{name}: {status}")

    success_count = sum(1 for _, success in results if success)
    total_count = len(results)

    print(f"\n总体结果: {success_count}/{total_count} 个示例成功")

    if success_count == total_count:
        print("🎉 所有示例都成功执行！")
    else:
        print("⚠️  部分示例失败，请检查错误信息")


if __name__ == "__main__":
    main()

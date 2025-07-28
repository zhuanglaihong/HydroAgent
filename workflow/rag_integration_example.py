"""
Author: zhuanglaihong
Date: 2025-01-21
Description: RAG系统与Workflow集成示例
"""

import sys
import os
from pathlib import Path

# 添加项目根路径
repo_path = Path(os.path.abspath(__file__)).parent.parent
sys.path.append(str(repo_path))

import logging
from langchain_ollama import ChatOllama
from langchain_community.embeddings import HuggingFaceEmbeddings

# 设置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def setup_rag_system():
    """设置RAG系统"""
    print("🔧 设置RAG系统...")

    try:
        # 1. 初始化模型
        print("  初始化模型...")
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        llm = ChatOllama(model="granite3-dense:8b", temperature=0.1)

        # 2. 创建RAG系统
        print("  创建RAG系统...")
        from RAG import RAGSystem

        rag_system = RAGSystem(embeddings=embeddings, llm=llm, index_path="./faiss_db")

        # 3. 检查是否有现有知识库
        if os.path.exists("./faiss_db"):
            print("  ✅ 发现现有知识库索引")
            return rag_system
        else:
            print("  ⚠️ 未发现现有索引，将创建新的知识库")
            return rag_system

    except Exception as e:
        print(f"  ❌ RAG系统设置失败: {e}")
        return None


def build_knowledge_base(rag_system):
    """构建知识库"""
    print("\n📚 构建知识库...")

    try:
        # 检查是否有文档目录
        documents_path = "./documents"
        if not os.path.exists(documents_path):
            print(f"  ⚠️ 文档目录 {documents_path} 不存在，创建示例文档...")
            create_sample_documents(documents_path)

        # 加载文档
        print("  加载文档...")
        doc_count = rag_system.load_documents(
            source=documents_path, file_extensions=[".txt", ".md", ".pdf"]
        )

        if doc_count > 0:
            print(f"  ✅ 成功加载 {doc_count} 个文档")

            # 创建索引
            print("  创建向量索引...")
            success = rag_system.create_index()

            if success:
                print("  ✅ 知识库构建完成")
                return True
            else:
                print("  ❌ 索引创建失败")
                return False
        else:
            print("  ⚠️ 未加载到任何文档")
            return False

    except Exception as e:
        print(f"  ❌ 知识库构建失败: {e}")
        return False


def create_sample_documents(documents_path):
    """创建示例文档"""
    try:
        os.makedirs(documents_path, exist_ok=True)

        # 创建水文模型相关文档
        documents = {
            "gr4j_model_introduction.txt": """
GR4J模型介绍

GR4J（Génie Rural à 4 paramètres Journalier）是一个四参数的日径流概念性水文模型，由法国CEMAGREF研究所开发。

模型参数：
1. X1 - 土壤蓄水容量（Soil moisture capacity）：100-1200mm
2. X2 - 地下水交换系数（Groundwater exchange coefficient）：-5到3mm
3. X3 - 最大地下水蓄水容量（Maximum groundwater storage）：20-300mm
4. X4 - 单位线时间参数（Unit hydrograph time parameter）：1.1-2.9天

模型特点：
- 结构简单，参数少，易于率定
- 适用于中小流域的日径流模拟
- 在全球范围内得到广泛应用
- 计算效率高，适合长期模拟

应用场景：
- 流域径流模拟
- 水文预报
- 气候变化影响评估
- 水资源管理
""",
            "model_calibration_guide.txt": """
水文模型率定指南

模型率定是水文建模的核心步骤，目标是通过调整模型参数使模型输出与观测数据最匹配。

率定流程：
1. 数据准备
   - 收集高质量的观测数据
   - 数据质量检查和预处理
   - 划分率定期和验证期

2. 目标函数选择
   - Nash-Sutcliffe效率系数（NSE）
   - 均方根误差（RMSE）
   - 平均绝对误差（MAE）
   - 相关系数（R²）

3. 优化算法
   - SCE-UA（Shuffled Complex Evolution）
   - 遗传算法（Genetic Algorithm）
   - 粒子群优化（PSO）
   - 贝叶斯优化

4. 参数约束
   - 物理意义约束
   - 经验范围约束
   - 敏感性分析

5. 结果验证
   - 交叉验证
   - 独立验证
   - 不确定性分析
""",
            "model_evaluation_standards.txt": """
模型评估标准

模型性能评估是验证模型精度和可靠性的重要步骤。

主要评估指标：

1. Nash-Sutcliffe效率系数（NSE）
   - 范围：-∞ 到 1
   - NSE > 0.5：可接受
   - NSE > 0.7：良好
   - NSE > 0.8：优秀

2. 决定系数（R²）
   - 范围：0 到 1
   - 反映模型解释观测数据变异的能力

3. 均方根误差（RMSE）
   - 单位与观测值相同
   - 越小越好

4. 平均绝对误差（MAE）
   - 对异常值不敏感
   - 易于解释

5. 相对误差指标
   - 相对偏差（RB）
   - 相对均方根误差（RRMSE）

评估建议：
- 使用多个指标综合评估
- 考虑不同时间尺度的性能
- 进行统计显著性检验
- 分析残差特征
""",
            "data_preprocessing_manual.txt": """
数据预处理手册

数据预处理是水文建模的基础，直接影响模型性能。

预处理步骤：

1. 数据收集
   - 气象数据：降水、温度、湿度、风速等
   - 水文数据：流量、水位等
   - 地理数据：流域边界、DEM等

2. 数据质量检查
   - 缺失值检测和处理
   - 异常值识别和修正
   - 数据一致性检查
   - 时间序列完整性验证

3. 数据格式转换
   - 时间格式统一
   - 单位转换
   - 数据对齐
   - 格式标准化

4. 数据插补
   - 线性插值
   - 样条插值
   - 基于相关性的插补
   - 多重插补方法

5. 数据验证
   - 物理合理性检查
   - 统计特性分析
   - 与历史数据对比
   - 专家知识验证
""",
            "camels_dataset_info.txt": """
CAMELS数据集介绍

CAMELS（Catchment Attributes and MEteorology for Large-sample Studies）是一个大规模的水文数据集，包含美国671个流域的详细数据。

数据集特点：
- 流域数量：671个
- 时间范围：1980-2014年
- 时间尺度：日尺度
- 数据质量：经过严格质量控制

包含数据：
1. 气象数据
   - 日降水量
   - 日最高/最低温度
   - 日平均温度
   - 相对湿度
   - 风速
   - 太阳辐射

2. 水文数据
   - 日流量
   - 流量质量指标

3. 流域属性
   - 地形特征
   - 土地利用
   - 土壤类型
   - 气候特征
   - 地质特征

应用价值：
- 大规模水文建模
- 模型比较研究
- 机器学习应用
- 气候变化研究
- 水资源管理
""",
        }

        # 写入文件
        for filename, content in documents.items():
            filepath = os.path.join(documents_path, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content.strip())

        print(f"  ✅ 创建了 {len(documents)} 个示例文档")

    except Exception as e:
        print(f"  ❌ 创建示例文档失败: {e}")


def test_rag_integration():
    """测试RAG集成"""
    print("\n🧪 测试RAG集成...")

    try:
        # 1. 设置RAG系统
        rag_system = setup_rag_system()
        if not rag_system:
            print("❌ RAG系统设置失败")
            return

        # 2. 构建知识库
        if not build_knowledge_base(rag_system):
            print("❌ 知识库构建失败")
            return

        # 3. 测试知识检索器
        print("\n🔍 测试知识检索器...")
        from workflow import KnowledgeRetriever

        knowledge_retriever = KnowledgeRetriever(
            rag_system=rag_system, faiss_index_path="./faiss_db", enable_fallback=True
        )

        # 测试检索
        test_queries = [
            "GR4J模型的参数有哪些？",
            "如何进行模型率定？",
            "模型评估的标准是什么？",
            "CAMELS数据集包含什么信息？",
        ]

        for query in test_queries:
            print(f"\n  查询: {query}")
            fragments = knowledge_retriever.retrieve_knowledge(query, k=3)

            print(f"    检索到 {len(fragments)} 个片段:")
            for i, fragment in enumerate(fragments, 1):
                print(
                    f"    {i}. {fragment.content[:100]}... (分数: {fragment.score:.2f})"
                )

        # 4. 测试完整工作流
        print("\n⚙️ 测试完整工作流...")
        from workflow import WorkflowOrchestrator
        from tool.langchain_tool import get_hydromodel_tools

        orchestrator = WorkflowOrchestrator(
            llm=ChatOllama(model="granite3-dense:8b"),
            rag_system=rag_system,
            tools=get_hydromodel_tools(),
            enable_debug=True,
        )

        # 测试工作流生成
        test_query = "我想了解GR4J模型的参数并进行率定"
        workflow_plan = orchestrator.process_query(test_query)

        print(f"  生成工作流: {workflow_plan.name}")
        print(f"  步骤数量: {len(workflow_plan.steps)}")

        for step in workflow_plan.steps:
            print(f"    - {step.name}: {step.tool_name}")

        print("\n✅ RAG集成测试完成！")

    except Exception as e:
        print(f"❌ RAG集成测试失败: {e}")
        import traceback

        traceback.print_exc()


def test_knowledge_retriever_standalone():
    """单独测试知识检索器"""
    print("\n🔍 单独测试知识检索器...")

    try:
        from workflow import KnowledgeRetriever

        # 创建知识检索器
        retriever = KnowledgeRetriever(
            faiss_index_path="./faiss_db", enable_fallback=True
        )

        # 测试检索功能
        test_result = retriever.test_retrieval("GR4J模型参数")

        print(f"测试查询: {test_result['test_query']}")
        print(f"原始片段数: {test_result['raw_fragments_count']}")
        print(f"处理后片段数: {test_result['processed_fragments_count']}")
        print(f"系统信息: {test_result['system_info']}")

        if "summary" in test_result:
            print(f"总结: {test_result['summary']}")

        print("✅ 知识检索器测试完成")

    except Exception as e:
        print(f"❌ 知识检索器测试失败: {e}")


def main():
    """主函数"""
    print("🌟 RAG系统与Workflow集成示例")
    print("=" * 60)

    # 检查前置条件
    try:
        from RAG import RAGSystem

        print("✅ RAG系统模块可用")
    except ImportError as e:
        print(f"❌ 无法导入RAG系统: {e}")
        print("请确保RAG模块已正确安装")
        return

    try:
        from workflow import KnowledgeRetriever

        print("✅ Workflow模块可用")
    except ImportError as e:
        print(f"❌ 无法导入Workflow模块: {e}")
        return

    # 运行测试
    try:
        test_rag_integration()
        test_knowledge_retriever_standalone()

        print("\n🎉 所有测试完成！")
        print("\n💡 使用提示:")
        print("1. 确保Ollama服务正在运行")
        print("2. 确保已安装必要的依赖包")
        print("3. 可以修改documents目录添加更多文档")
        print("4. 可以调整检索参数优化性能")

    except KeyboardInterrupt:
        print("\n👋 测试已取消")
    except Exception as e:
        print(f"\n❌ 测试执行出错: {e}")


if __name__ == "__main__":
    main()

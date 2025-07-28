"""
Author: zhuanglaihong
Date: 2025-01-21
Description: Dify知识库构建器使用示例
"""

import os
import logging
from pathlib import Path

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_sample_documents():
    """创建示例文档"""
    documents_dir = "./sample_documents"
    os.makedirs(documents_dir, exist_ok=True)
    
    # 创建水文模型相关文档
    documents = {
        "gr4j_model_detailed.txt": """
GR4J模型详细说明

GR4J（Génie Rural à 4 paramètres Journalier）是一个四参数的日径流概念性水文模型，由法国CEMAGREF研究所开发。

模型结构：
GR4J模型包含两个串联的储水单元：土壤储水单元和地下水储水单元。模型通过四个参数来描述流域的水文特性。

参数详解：
1. X1 - 土壤蓄水容量（Soil moisture capacity）
   - 取值范围：100-1200mm
   - 物理意义：描述土壤层的最大蓄水能力
   - 影响：控制地表径流的产生

2. X2 - 地下水交换系数（Groundwater exchange coefficient）
   - 取值范围：-5到3mm
   - 物理意义：描述地下水与地表水的交换强度
   - 影响：控制基流的生成

3. X3 - 最大地下水蓄水容量（Maximum groundwater storage）
   - 取值范围：20-300mm
   - 物理意义：描述地下水储层的最大容量
   - 影响：控制地下径流的延迟

4. X4 - 单位线时间参数（Unit hydrograph time parameter）
   - 取值范围：1.1-2.9天
   - 物理意义：描述流域的汇流时间
   - 影响：控制径流的时序特征

模型优势：
- 结构简单，参数少，易于率定
- 计算效率高，适合长期模拟
- 在全球范围内得到广泛应用
- 适用于中小流域的日径流模拟

应用场景：
- 流域径流模拟和预报
- 气候变化影响评估
- 水资源管理和规划
- 水文科学研究

率定建议：
- 使用NSE作为主要目标函数
- 结合RMSE和MAE进行综合评估
- 考虑不同时间尺度的性能
- 进行交叉验证确保稳定性
""",
        
        "calibration_methods.txt": """
水文模型率定方法详解

模型率定是水文建模的核心步骤，目标是通过调整模型参数使模型输出与观测数据最匹配。

率定流程：

1. 数据准备阶段
   - 收集高质量的观测数据（降水、流量等）
   - 数据质量检查和预处理
   - 缺失值处理和异常值检测
   - 划分率定期和验证期（通常7:3或8:2）

2. 目标函数选择
   - Nash-Sutcliffe效率系数（NSE）：主要指标
   - 均方根误差（RMSE）：误差大小
   - 平均绝对误差（MAE）：误差分布
   - 相关系数（R²）：线性相关性
   - 相对误差指标：标准化比较

3. 优化算法选择
   - SCE-UA（Shuffled Complex Evolution）：全局优化
   - 遗传算法（Genetic Algorithm）：启发式搜索
   - 粒子群优化（PSO）：群体智能
   - 贝叶斯优化：概率方法
   - 梯度下降：局部优化

4. 参数约束设置
   - 物理意义约束：参数合理性
   - 经验范围约束：文献参考值
   - 敏感性分析：识别重要参数
   - 相关性分析：避免参数冗余

5. 结果验证
   - 交叉验证：时间分割验证
   - 独立验证：空间分割验证
   - 不确定性分析：参数不确定性
   - 残差分析：模型误差特征

率定技巧：
- 从粗到细的逐步优化
- 多目标函数综合优化
- 考虑不同时间尺度的性能
- 结合专家知识进行约束
- 使用多种算法交叉验证
""",
        
        "model_evaluation_comprehensive.txt": """
模型评估综合指南

模型性能评估是验证模型精度和可靠性的重要步骤，需要从多个维度进行综合评估。

评估指标体系：

1. 统计指标
   - Nash-Sutcliffe效率系数（NSE）
     * 范围：-∞ 到 1
     * NSE > 0.5：可接受
     * NSE > 0.7：良好
     * NSE > 0.8：优秀
     * NSE > 0.9：极好
   
   - 决定系数（R²）
     * 范围：0 到 1
     * 反映模型解释观测数据变异的能力
     * R² > 0.6：可接受
     * R² > 0.8：良好
   
   - 均方根误差（RMSE）
     * 单位与观测值相同
     * 越小越好
     * 对异常值敏感
   
   - 平均绝对误差（MAE）
     * 对异常值不敏感
     * 易于解释
     * 反映平均误差水平

2. 相对误差指标
   - 相对偏差（RB）：系统性偏差
   - 相对均方根误差（RRMSE）：标准化误差
   - 相对平均绝对误差（RMAE）：标准化绝对误差

3. 图形评估
   - 时间序列图：直观显示拟合效果
   - 散点图：观测值与模拟值对比
   - Q-Q图：残差分布检验
   - 自相关图：残差独立性检验

4. 水文特征评估
   - 流量过程线拟合：整体趋势
   - 峰值流量：洪水模拟能力
   - 低流量：枯水期模拟能力
   - 流量历时曲线：统计特征

评估建议：
- 使用多个指标综合评估
- 考虑不同时间尺度的性能
- 进行统计显著性检验
- 分析残差特征和分布
- 结合水文专业知识判断
- 考虑模型应用目的

常见问题：
- 过拟合：训练期表现好，验证期差
- 欠拟合：训练期和验证期都差
- 参数不确定性：参数敏感性高
- 数据质量问题：观测数据误差
- 模型结构问题：物理过程描述不当
""",
        
        "data_preprocessing_advanced.txt": """
数据预处理高级指南

数据预处理是水文建模的基础，直接影响模型性能。高质量的预处理可以显著提高模型精度。

预处理步骤详解：

1. 数据收集与整理
   - 气象数据：降水、温度、湿度、风速、太阳辐射
   - 水文数据：流量、水位、水质
   - 地理数据：流域边界、DEM、土地利用、土壤类型
   - 时间范围：确保数据时间一致性
   - 空间范围：确保空间覆盖完整性

2. 数据质量检查
   - 缺失值检测：识别数据缺失模式
   - 异常值识别：统计方法和物理方法
   - 数据一致性：时间格式、单位统一
   - 数据完整性：时间序列连续性
   - 数据合理性：物理约束检查

3. 数据清洗技术
   - 缺失值处理：
     * 线性插值：短期缺失
     * 样条插值：平滑插值
     * 基于相关性的插补：利用其他变量
     * 多重插补：考虑不确定性
   
   - 异常值处理：
     * 统计方法：3σ原则、IQR方法
     * 物理方法：基于水文规律
     * 平滑处理：移动平均、滤波
     * 专家判断：结合专业知识

4. 数据格式转换
   - 时间格式统一：标准化时间戳
   - 单位转换：统一计量单位
   - 数据对齐：时间序列同步
   - 格式标准化：数据结构统一
   - 编码处理：字符编码统一

5. 数据验证
   - 物理合理性检查：符合水文规律
   - 统计特性分析：分布特征检验
   - 与历史数据对比：一致性验证
   - 专家知识验证：专业判断
   - 交叉验证：多源数据对比

6. 数据增强
   - 特征工程：构造新变量
   - 数据标准化：消除量纲影响
   - 数据平滑：减少噪声影响
   - 数据插值：填补缺失值
   - 数据重构：时间尺度转换

质量控制标准：
- 数据完整性 > 95%
- 异常值比例 < 5%
- 时间一致性 100%
- 物理合理性 100%
- 统计特性合理

常见问题及解决方案：
- 数据缺失：多源数据融合
- 数据异常：物理约束检查
- 时间不一致：时间同步处理
- 单位不统一：标准化转换
- 数据噪声：滤波平滑处理
"""
    }
    
    # 写入文件
    for filename, content in documents.items():
        filepath = os.path.join(documents_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content.strip())
    
    print(f"✅ 创建了 {len(documents)} 个示例文档在 {documents_dir} 目录")
    return documents_dir


def test_dify_knowledge_builder():
    """测试Dify知识库构建器"""
    print("\n🧪 测试Dify知识库构建器...")
    
    # 配置参数（需要根据实际情况修改）
    DIFY_URL = "http://localhost:5001"  # 替换为你的Dify服务器地址
    DIFY_KEY = "your_dify_api_key"      # 替换为你的API密钥
    
    try:
        from dify_knowledge_builder import DifyKnowledgeBuilder
        
        # 创建构建器
        builder = DifyKnowledgeBuilder(
            dify_api_url=DIFY_URL,
            dify_api_key=DIFY_KEY,
            embeddings_model="sentence-transformers/all-MiniLM-L6-v2",
            chunk_size=1000,
            chunk_overlap=200
        )
        
        # 测试连接
        print("🔗 测试Dify服务器连接...")
        if builder.test_dify_connection():
            print("✅ 连接成功")
        else:
            print("❌ 连接失败，请检查配置")
            return
        
        # 创建示例文档
        print("\n📝 创建示例文档...")
        docs_dir = create_sample_documents()
        
        # 构建知识库
        print("\n🏗️ 构建知识库...")
        success = builder.build_knowledge_base(
            source_path=docs_dir,
            index_name="dify_hydrology_knowledge"
        )
        
        if success:
            print("✅ 知识库构建成功！")
            
            # 显示知识库信息
            print("\n📊 知识库信息:")
            info = builder.get_knowledge_base_info()
            for key, value in info.items():
                print(f"  {key}: {value}")
            
            # 测试查询
            print("\n🔍 测试查询功能...")
            test_queries = [
                "GR4J模型的参数有哪些？",
                "如何进行模型率定？",
                "模型评估的标准是什么？",
                "数据预处理包括哪些步骤？"
            ]
            
            for query in test_queries:
                print(f"\n查询: {query}")
                results = builder.query_knowledge_base(query, k=3)
                
                for i, result in enumerate(results, 1):
                    print(f"  结果{i}: {result['content'][:100]}... (分数: {result['score']:.4f})")
        
        else:
            print("❌ 知识库构建失败")
            
    except ImportError:
        print("❌ 无法导入DifyKnowledgeBuilder，请确保脚本存在")
    except Exception as e:
        print(f"❌ 测试失败: {e}")


def demonstrate_usage():
    """演示使用方法"""
    print("\n📖 使用演示...")
    
    print("""
使用方法：

1. 基本使用：
   python dify_knowledge_builder.py \\
     --dify_url "http://your-dify-server:5001" \\
     --dify_key "your-api-key" \\
     --source "./documents" \\
     --index_name "my_knowledge_base"

2. 自定义参数：
   python dify_knowledge_builder.py \\
     --dify_url "http://localhost:5001" \\
     --dify_key "your-key" \\
     --source "./sample_documents" \\
     --chunk_size 800 \\
     --chunk_overlap 150 \\
     --embeddings_model "sentence-transformers/all-MiniLM-L6-v2" \\
     --test_query "GR4J模型参数"

3. 编程接口：
   from dify_knowledge_builder import DifyKnowledgeBuilder
   
   builder = DifyKnowledgeBuilder(
       dify_api_url="http://localhost:5001",
       dify_api_key="your-key"
   )
   
   # 构建知识库
   success = builder.build_knowledge_base("./documents")
   
   # 查询知识库
   results = builder.query_knowledge_base("查询内容")
""")


def main():
    """主函数"""
    print("🌟 Dify知识库构建器示例")
    print("=" * 50)
    
    # 检查前置条件
    try:
        import requests
        print("✅ requests库可用")
    except ImportError:
        print("❌ 需要安装requests库: pip install requests")
        return
    
    try:
        from langchain_community.embeddings import HuggingFaceEmbeddings
        print("✅ langchain库可用")
    except ImportError:
        print("❌ 需要安装langchain库: pip install langchain")
        return
    
    # 运行示例
    try:
        test_dify_knowledge_builder()
        demonstrate_usage()
        
        print("\n🎉 示例执行完成！")
        print("\n💡 提示:")
        print("1. 请确保Dify服务器正在运行")
        print("2. 请配置正确的API地址和密钥")
        print("3. 可以根据需要调整分块参数")
        print("4. 支持多种文档格式")
        
    except KeyboardInterrupt:
        print("\n👋 示例执行已取消")
    except Exception as e:
        print(f"\n❌ 示例执行出错: {e}")


if __name__ == "__main__":
    main() 
"""
HydroRAG系统使用示例
演示如何使用HydroRAG系统进行文档处理、索引构建和知识检索
"""

import os
import logging
from pathlib import Path

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 导入HydroRAG组件
from hydrorag import RAGSystem, Config, create_rag_system, quick_setup


def example_1_basic_usage():
    """示例1: 基础使用"""
    print("\\n" + "="*60)
    print("示例1: HydroRAG基础使用")
    print("="*60)
    
    try:
        # 创建临时目录用于演示
        demo_dir = "./demo_hydrorag"
        
        # 创建演示用的原始文档
        setup_demo_documents(demo_dir)
        
        # 使用默认配置创建RAG系统
        config = Config(
            documents_dir=demo_dir,
            raw_documents_dir=f"{demo_dir}/raw",
            processed_documents_dir=f"{demo_dir}/processed",
            vector_db_dir=f"{demo_dir}/vector_db",
            chunk_size=300,
            chunk_overlap=30,
            top_k=5
        )
        
        print(f"创建RAG系统，文档目录: {demo_dir}")
        rag_system = RAGSystem(config)
        
        # 检查系统状态
        status = rag_system.get_system_status()
        print(f"系统初始化状态: {status['is_initialized']}")
        
        if status['is_initialized']:
            print("✅ RAG系统初始化成功")
        else:
            print("❌ RAG系统初始化失败")
            print(f"错误: {status['initialization_errors']}")
            return
        
        # 从原始文档设置系统
        print("\\n开始完整设置流程...")
        setup_result = rag_system.setup_from_raw_documents()
        
        if setup_result['status'] == 'success':
            print("✅ 系统设置成功!")
            
            # 显示处理结果
            doc_result = setup_result['steps']['document_processing']
            print(f"   📄 处理文档: {doc_result['processed']} 成功, {doc_result['failed']} 失败")
            
            index_result = setup_result['steps']['index_building']
            print(f"   🔍 构建索引: {index_result['total_chunks_added']} 个文本块")
            
            # 测试查询
            print("\\n🔍 测试查询...")
            test_queries = [
                "GR4J模型有哪些参数？",
                "模型率定的方法",
                "NSE评估指标"
            ]
            
            for query in test_queries:
                print(f"\\n查询: {query}")
                result = rag_system.query(query, top_k=3, score_threshold=0.3)
                
                if result['status'] == 'success' and result['total_found'] > 0:
                    print(f"   找到 {result['total_found']} 个相关文档:")
                    for i, doc in enumerate(result['results'][:2]):  # 显示前2个结果
                        print(f"   {i+1}. 分数: {doc['score']:.3f}")
                        print(f"      内容: {doc['content'][:100]}...")
                else:
                    print("   未找到相关文档")
        
        else:
            print(f"❌ 系统设置失败: {setup_result['error']}")
    
    except Exception as e:
        print(f"❌ 示例执行失败: {e}")
        import traceback
        traceback.print_exc()


def example_2_step_by_step():
    """示例2: 分步骤设置"""
    print("\\n" + "="*60)
    print("示例2: 分步骤设置RAG系统")
    print("="*60)
    
    try:
        demo_dir = "./demo_hydrorag_step"
        setup_demo_documents(demo_dir)
        
        config = Config(
            documents_dir=demo_dir,
            raw_documents_dir=f"{demo_dir}/raw",
            processed_documents_dir=f"{demo_dir}/processed",
            vector_db_dir=f"{demo_dir}/vector_db"
        )
        
        rag_system = RAGSystem(config)
        
        if not rag_system.is_initialized:
            print("❌ 系统初始化失败，跳过后续步骤")
            return
        
        # 步骤1: 处理文档
        print("\\n步骤1: 处理原始文档")
        process_result = rag_system.process_documents(force_reprocess=True)
        print(f"处理结果: {process_result['status']}")
        if process_result['status'] == 'completed':
            print(f"   成功: {process_result['processed']}, 失败: {process_result['failed']}")
        
        # 步骤2: 构建索引
        print("\\n步骤2: 构建向量索引")
        index_result = rag_system.build_vector_index(rebuild=True)
        print(f"索引构建: {index_result['status']}")
        if index_result['status'] == 'success':
            print(f"   文本块数量: {index_result['total_chunks_added']}")
            print(f"   向量数据库文档总数: {index_result['final_document_count']}")
        
        # 步骤3: 测试查询
        print("\\n步骤3: 测试查询功能")
        query_result = rag_system.query("水文模型参数", top_k=5)
        print(f"查询结果: {query_result['status']}")
        if query_result['status'] == 'success':
            print(f"   找到 {query_result['total_found']} 个相关文档")
        
        # 获取系统统计信息
        print("\\n📊 系统统计信息:")
        if rag_system.vector_store:
            stats = rag_system.vector_store.get_statistics()
            print(f"   向量数据库文档数量: {stats.get('total_documents', 0)}")
            print(f"   集合名称: {stats.get('collection_name', 'N/A')}")
            print(f"   距离函数: {stats.get('distance_function', 'N/A')}")
    
    except Exception as e:
        print(f"❌ 示例执行失败: {e}")


def example_3_advanced_features():
    """示例3: 高级功能演示"""
    print("\\n" + "="*60)
    print("示例3: 高级功能演示")
    print("="*60)
    
    try:
        demo_dir = "./demo_hydrorag_advanced"
        setup_demo_documents(demo_dir)
        
        # 使用快速设置
        print("使用快速设置创建RAG系统...")
        rag_system = quick_setup(demo_dir)
        
        if not rag_system.is_initialized:
            print("❌ 快速设置失败")
            return
        
        print("✅ 快速设置完成")
        
        # 健康检查
        print("\\n🏥 系统健康检查:")
        health = rag_system.health_check()
        print(f"   总体状态: {health['overall_status']}")
        
        for check_name, check_result in health['checks'].items():
            status = check_result['status']
            emoji = "✅" if status == "passed" else "❌"
            print(f"   {emoji} {check_name}: {status}")
        
        if health['overall_status'] != 'healthy':
            print(f"   问题: {health.get('issues', [])}")
        
        # 演示高级查询
        print("\\n🔍 高级查询演示:")
        
        # 查询1: 高阈值查询
        print("\\n1. 高阈值查询（只返回高相关性结果）:")
        result = rag_system.query("GR4J参数", top_k=10, score_threshold=0.7)
        print(f"   找到 {result.get('total_found', 0)} 个高相关性文档")
        
        # 查询2: 低阈值查询
        print("\\n2. 低阈值查询（返回更多候选结果）:")
        result = rag_system.query("水文", top_k=10, score_threshold=0.2)
        print(f"   找到 {result.get('total_found', 0)} 个候选文档")
        
        # 查询3: 多个查询比较
        print("\\n3. 多查询比较:")
        queries = ["模型参数", "率定方法", "评估指标"]
        for query in queries:
            result = rag_system.query(query, top_k=3)
            count = result.get('total_found', 0)
            print(f"   '{query}': {count} 个结果")
        
        # 备份演示
        print("\\n💾 备份功能演示:")
        backup_dir = f"{demo_dir}/backups"
        backup_result = rag_system.backup_system(backup_dir)
        
        if backup_result['status'] == 'success':
            print(f"   ✅ 备份成功: {backup_result['backup_dir']}")
            print(f"   备份文件: {list(backup_result['backups'].keys())}")
        else:
            print(f"   ❌ 备份失败: {backup_result.get('error', '未知错误')}")
        
        # 显示详细统计
        print("\\n📈 详细统计信息:")
        system_status = rag_system.get_system_status()
        
        # 文档处理统计
        doc_stats = system_status['components']['document_processor']['stats']
        if doc_stats:
            print(f"   原始文档: {doc_stats.get('raw_documents_count', 0)}")
            print(f"   已处理文档: {doc_stats.get('processed_documents_count', 0)}")
            print(f"   文本块总数: {doc_stats.get('total_chunks', 0)}")
            print(f"   平均块大小: {doc_stats.get('average_chunk_size', 0):.0f} 字符")
        
        # 向量数据库统计
        vector_stats = system_status['components']['vector_store']['stats']
        if vector_stats:
            print(f"   向量数据库文档: {vector_stats.get('total_documents', 0)}")
            print(f"   唯一源文件: {vector_stats.get('unique_source_files', 0)}")
    
    except Exception as e:
        print(f"❌ 示例执行失败: {e}")


def example_4_knowledge_retriever_integration():
    """示例4: 与knowledge_retriever集成"""
    print("\\n" + "="*60)
    print("示例4: 与knowledge_retriever集成")
    print("="*60)
    
    try:
        # 模拟与workflow中knowledge_retriever的集成
        class MockKnowledgeFragment:
            def __init__(self, content, source, score, metadata):
                self.content = content
                self.source = source
                self.score = score
                self.metadata = metadata
            
            def to_dict(self):
                return {
                    "content": self.content,
                    "source": self.source,
                    "score": self.score,
                    "metadata": self.metadata
                }
        
        class HydroRAGKnowledgeRetriever:
            """集成HydroRAG的知识检索器"""
            
            def __init__(self, documents_dir="./demo_hydrorag_integration"):
                self.documents_dir = documents_dir
                setup_demo_documents(documents_dir)
                
                # 初始化HydroRAG系统
                self.hydrorag = quick_setup(documents_dir)
            
            def retrieve_knowledge(self, expanded_query, k=5, score_threshold=0.3):
                """检索知识片段"""
                if not self.hydrorag.is_initialized:
                    print("⚠️  HydroRAG系统未初始化，使用默认知识")
                    return self._get_default_knowledge(expanded_query, k)
                
                # 使用HydroRAG进行检索
                result = self.hydrorag.query(
                    query_text=expanded_query,
                    top_k=k,
                    score_threshold=score_threshold
                )
                
                # 转换为KnowledgeFragment格式
                fragments = []
                if result["status"] == "success":
                    for item in result["results"]:
                        fragment = MockKnowledgeFragment(
                            content=item["content"],
                            source=item.get("metadata", {}).get("source_file", "HydroRAG"),
                            score=item["score"],
                            metadata=item.get("metadata", {})
                        )
                        fragments.append(fragment)
                
                return fragments
            
            def _get_default_knowledge(self, query, k):
                """回退到默认知识"""
                default_fragments = [
                    MockKnowledgeFragment(
                        content="GR4J模型是一个概念性水文模型，包含4个参数：X1（土壤蓄水容量）、X2（地下水交换系数）、X3（最大地下水蓄水容量）、X4（单位线时间参数）。",
                        source="默认知识库",
                        score=0.8,
                        metadata={"category": "model_parameters"}
                    )
                ]
                return default_fragments[:k]
        
        # 演示集成使用
        print("创建集成的知识检索器...")
        retriever = HydroRAGKnowledgeRetriever()
        
        print("\\n🔍 测试知识检索:")
        queries = [
            "GR4J模型的参数说明",
            "模型率定的优化算法",
            "模型评估的指标类型"
        ]
        
        for query in queries:
            print(f"\\n查询: {query}")
            fragments = retriever.retrieve_knowledge(query, k=3, score_threshold=0.3)
            
            if fragments:
                print(f"   找到 {len(fragments)} 个知识片段:")
                for i, fragment in enumerate(fragments):
                    print(f"   {i+1}. 分数: {fragment.score:.3f}")
                    print(f"      来源: {fragment.source}")
                    print(f"      内容: {fragment.content[:100]}...")
            else:
                print("   未找到相关知识片段")
        
        print("\\n✅ 集成演示完成")
    
    except Exception as e:
        print(f"❌ 集成演示失败: {e}")


def setup_demo_documents(demo_dir):
    """设置演示文档"""
    
    raw_dir = Path(demo_dir) / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建演示文档
    documents = {
        "gr4j_model.md": """# GR4J水文模型

## 模型简介

GR4J是一个概念性日尺度水文模型，由法国CEMAGREF（现INRAE）开发。该模型具有简单的结构和良好的性能。

## 模型参数

GR4J模型包含4个参数：

1. **X1**: 土壤蓄水容量参数（mm），控制产流过程
2. **X2**: 地下水交换系数（mm），控制地下水与河道的交换
3. **X3**: 最大地下水蓄水容量参数（mm），控制地下水库容量
4. **X4**: 单位线时间参数（day），控制汇流过程的时间常数

## 模型结构

模型包含两个蓄水库：
- 土壤蓄水库：控制蒸发和产流
- 地下水蓄水库：控制基流生成

## 应用范围

GR4J模型适用于：
- 温带气候区域
- 日尺度流量模拟
- 洪水预报
- 水资源评估
""",

        "model_calibration.md": """# 水文模型率定

## 率定概述

模型率定是通过优化算法调整模型参数，使模型输出与观测数据最佳匹配的过程。

## 优化算法

常用的优化算法包括：

### 1. SCE-UA算法
- Shuffled Complex Evolution算法
- 全局优化算法
- 适用于多峰值目标函数

### 2. 遗传算法(GA)
- 基于生物进化原理
- 并行搜索能力强
- 容易跳出局部最优

### 3. 粒子群算法(PSO)
- 基于群体智能
- 收敛速度快
- 参数设置简单

## 率定策略

### 多目标率定
- 同时考虑多个评估指标
- 平衡不同水文过程的模拟精度

### 分期率定
- 丰水期和枯水期分别率定
- 提高模型在不同时期的表现

### 区域化率定
- 利用相似流域信息
- 解决无资料流域建模问题
""",

        "evaluation_metrics.md": """# 水文模型评估指标

## 评估指标概述

模型评估是检验模型性能的重要环节，通过定量指标评价模型的模拟精度。

## 主要评估指标

### 1. NSE (Nash-Sutcliffe效率系数)
- 范围: (-∞, 1]
- NSE = 1: 完美模拟
- NSE = 0: 模型性能等同于均值
- NSE < 0: 模型性能差于均值

计算公式：
```
NSE = 1 - Σ(Qo - Qm)² / Σ(Qo - Q̄o)²
```

### 2. RMSE (均方根误差)
- 单位与观测值相同
- 值越小表示模型精度越高
- 对极值敏感

### 3. MAE (平均绝对误差)
- 单位与观测值相同
- 对异常值不敏感
- 直观反映平均误差大小

### 4. 相关系数(R)
- 范围: [-1, 1]
- 反映线性相关程度
- 不反映系统性偏差

### 5. KGE (Kling-Gupta效率)
- 改进的综合指标
- 考虑相关性、偏差和变异性
- 范围: (-∞, 1]

## 评估准则

### NSE分级标准
- NSE > 0.8: 优秀
- 0.6 < NSE ≤ 0.8: 良好  
- 0.4 < NSE ≤ 0.6: 可接受
- NSE ≤ 0.4: 不可接受

### 建议
- 综合使用多个指标
- 考虑不同水文过程
- 注意极值事件的表现
""",

        "camels_dataset.txt": """CAMELS数据集介绍

CAMELS (Catchment Attributes and MEteorology for Large-sample Studies) 是一个大样本流域数据集，为水文建模研究提供了丰富的数据资源。

数据集特点：
- 包含美国671个流域
- 时间序列长度不等，多数超过20年
- 提供日尺度的水文气象数据
- 包含丰富的流域属性信息

数据内容：
1. 时间序列数据
   - 降水量 (precipitation)
   - 温度 (temperature) 
   - 潜在蒸发量 (potential evapotranspiration)
   - 径流量 (streamflow)

2. 流域属性
   - 地形特征：面积、坡度、高程等
   - 气候特征：年均降水、温度等
   - 土地利用：森林、农业、城市等比例
   - 土壤特征：土壤类型、渗透性等
   - 地质特征：地质年代、岩性等

应用领域：
- 水文模型评估
- 区域化研究
- 机器学习建模
- 气候变化影响评估

数据格式：
- CSV格式的时间序列数据
- NetCDF格式的属性数据
- 标准化的变量命名规范
""",
        
        "data_preprocessing.py": '''"""
数据预处理示例代码
演示CAMELS数据的预处理流程
"""

import pandas as pd
import numpy as np
from pathlib import Path

def load_camels_data(basin_id, data_dir):
    """
    加载CAMELS流域数据
    
    Args:
        basin_id: 流域编号
        data_dir: 数据目录路径
    
    Returns:
        DataFrame: 包含时间序列数据的DataFrame
    """
    # 构建文件路径
    file_path = Path(data_dir) / f"basin_{basin_id}.csv"
    
    # 读取数据
    df = pd.read_csv(file_path, parse_dates=['date'])
    df.set_index('date', inplace=True)
    
    return df

def check_data_quality(df):
    """
    检查数据质量
    
    Args:
        df: 输入数据框
        
    Returns:
        dict: 数据质量报告
    """
    report = {
        'total_days': len(df),
        'missing_values': df.isnull().sum().to_dict(),
        'data_range': {
            'start_date': df.index.min(),
            'end_date': df.index.max()
        }
    }
    
    return report

def fill_missing_values(df, method='interpolate'):
    """
    填充缺失值
    
    Args:
        df: 输入数据框
        method: 填充方法
        
    Returns:
        DataFrame: 处理后的数据框
    """
    df_filled = df.copy()
    
    if method == 'interpolate':
        # 线性插值
        df_filled = df_filled.interpolate(method='linear')
    elif method == 'forward_fill':
        # 前向填充
        df_filled = df_filled.fillna(method='ffill')
    elif method == 'mean':
        # 均值填充
        df_filled = df_filled.fillna(df.mean())
    
    return df_filled

def split_data(df, train_ratio=0.7, val_ratio=0.15):
    """
    分割训练、验证和测试数据
    
    Args:
        df: 输入数据框
        train_ratio: 训练集比例
        val_ratio: 验证集比例
        
    Returns:
        tuple: (训练集, 验证集, 测试集)
    """
    n = len(df)
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)
    
    train_data = df.iloc[:n_train]
    val_data = df.iloc[n_train:n_train+n_val]
    test_data = df.iloc[n_train+n_val:]
    
    return train_data, val_data, test_data
'''
    }
    
    # 写入文档文件
    for filename, content in documents.items():
        file_path = raw_dir / filename
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
    
    print(f"📁 演示文档已创建在: {raw_dir}")
    print(f"   包含 {len(documents)} 个文档文件")


def main():
    """主函数 - 运行所有示例"""
    print("🚀 HydroRAG系统使用示例")
    print("本示例将演示HydroRAG系统的各种功能")
    
    try:
        # 示例1: 基础使用
        example_1_basic_usage()
        
        # 示例2: 分步骤设置
        example_2_step_by_step()
        
        # 示例3: 高级功能
        example_3_advanced_features()
        
        # 示例4: 集成演示
        example_4_knowledge_retriever_integration()
        
        print("\\n" + "="*60)
        print("🎉 所有示例执行完成!")
        print("="*60)
        
        print("\\n📝 说明:")
        print("- 如果某些示例失败，可能是因为缺少依赖包")
        print("- 请确保安装了chromadb、sentence-transformers等依赖")
        print("- 首次运行时会下载嵌入模型，需要网络连接")
        print("- 生成的演示文件可以安全删除")
        
    except Exception as e:
        print(f"\\n❌ 示例执行出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

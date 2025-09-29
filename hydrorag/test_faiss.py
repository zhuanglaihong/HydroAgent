import numpy as np
import faiss
import time
import requests
import json
import os
from pathlib import Path
import traceback

def get_embedding(text, model_name="bge-large:335m", ollama_host="http://localhost:11434"):
    """
    使用本地Ollama服务获取文本的嵌入向量
    """
    url = f"{ollama_host}/api/embeddings"
    payload = {
        "model": model_name,
        "prompt": text
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        
        if response.status_code != 200:
            print(f"Ollama返回非200状态码: {response.status_code}")
            return None
            
        data = response.json()
        embedding = data.get("embedding")
        
        if not embedding:
            print(f"未从Ollama响应中获取到嵌入向量: {data}")
            return None
            
        return np.array(embedding, dtype='float32')
    except requests.exceptions.Timeout:
        print("请求Ollama超时，请确保服务正在运行")
        return None
    except requests.exceptions.ConnectionError:
        print(f"无法连接到Ollama服务: {ollama_host}")
        print("请确保Ollama已启动并监听正确端口")
        return None
    except Exception as e:
        print(f"获取嵌入向量时出错: {str(e)}")
        return None

def process_documents(doc_dir, chunk_size=500):
    """
    处理文档目录，将文档分块并生成嵌入向量
    """
    print(f"处理文档目录: {doc_dir}")
    
    if not os.path.exists(doc_dir):
        print(f"错误: 目录 '{doc_dir}' 不存在")
        return None, None
        
    if not os.path.isdir(doc_dir):
        print(f"错误: '{doc_dir}' 不是目录")
        return None, None
        
    documents = []
    embeddings = []
    processed_files = 0
    
    # 遍历目录中的所有文本文件
    for file_path in Path(doc_dir).glob("*.txt"):
        print(f"处理文件: {file_path.name}")
        processed_files += 1
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
                
                # 简单分块处理
                chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
                
                for chunk in chunks:
                    if not chunk.strip():  # 跳过空块
                        continue
                        
                    # 获取嵌入向量
                    embedding = get_embedding(chunk)
                    if embedding is not None:
                        documents.append({
                            "file": file_path.name,
                            "chunk": chunk[:50] + "..." if len(chunk) > 50 else chunk,
                            "full_chunk": chunk,  # 保存完整文本用于调试
                            "embedding": embedding
                        })
                        embeddings.append(embedding)
        except Exception as e:
            print(f"处理文件 {file_path.name} 时出错: {str(e)}")
            continue
    
    if not processed_files:
        print(f"警告: 目录 '{doc_dir}' 中没有找到.txt文件")
        return None, None
        
    if not embeddings:
        print("错误: 未能生成任何嵌入向量")
        return None, None
        
    # 转换为numpy数组
    try:
        embeddings = np.vstack(embeddings)
        print(f"成功处理 {len(documents)} 个文本块")
        return documents, embeddings
    except Exception as e:
        print(f"创建嵌入矩阵时出错: {str(e)}")
        return None, None

def create_faiss_index(embeddings, index_type="Flat"):
    """
    创建FAISS索引
    """
    if embeddings is None or embeddings.size == 0:
        print("错误: 无效的嵌入向量输入")
        return None
        
    dimension = embeddings.shape[1]
    
    try:
        if index_type == "Flat":
            # 使用精确搜索的平面索引
            index = faiss.IndexFlatL2(dimension)
        elif index_type == "IVF":
            # 使用倒排文件索引（适合大型数据集）
            nlist = min(100, len(embeddings) // 10)  # 自适应聚类中心数量
            quantizer = faiss.IndexFlatL2(dimension)
            index = faiss.IndexIVFFlat(quantizer, dimension, nlist)
            
            # IVF索引需要训练
            print("训练IVF索引...")
            index.train(embeddings)
        else:
            raise ValueError(f"不支持的索引类型: {index_type}")
        
        # 添加向量到索引
        print("添加向量到索引...")
        index.add(embeddings)
        print(f"索引创建完成，包含 {index.ntotal} 个向量")
        
        return index
    except Exception as e:
        print(f"创建FAISS索引时出错: {str(e)}")
        return None

def search_index(index, query_text, k=3):
    """
    在索引中搜索相似的文本块
    """
    # 获取查询文本的嵌入向量
    query_embedding = get_embedding(query_text)
    if query_embedding is None:
        print("无法获取查询文本的嵌入向量")
        return None, None
    
    try:
        # 确保是2D数组
        query_embedding = query_embedding.reshape(1, -1)
        
        # 执行搜索
        distances, indices = index.search(query_embedding, k)
        
        return distances[0], indices[0]
    except Exception as e:
        print(f"搜索索引时出错: {str(e)}")
        return None, None

def save_index(index, file_path):
    """保存索引到文件"""
    try:
        faiss.write_index(index, file_path)
        print(f"索引已保存到: {file_path}")
        return True
    except Exception as e:
        print(f"保存索引时出错: {str(e)}")
        return False

def load_index(file_path):
    """从文件加载索引"""
    try:
        if not os.path.exists(file_path):
            print(f"索引文件不存在: {file_path}")
            return None
            
        index = faiss.read_index(file_path)
        print(f"成功加载索引，包含 {index.ntotal} 个向量")
        return index
    except Exception as e:
        print(f"加载索引时出错: {str(e)}")
        return None

def main():
    # 配置参数
    DOC_DIR = "documents"  # 存放文档的目录
    INDEX_FILE = "faiss_index.index"
    INDEX_TYPE = "Flat"  # 可选: "Flat" 或 "IVF"
    
    print("="*50)
    print("FAISS与Ollama集成测试")
    print("="*50)
    
    # 步骤1: 处理文档并生成嵌入向量
    print("\n[步骤1] 处理文档并生成嵌入向量")
    documents, embeddings = process_documents(DOC_DIR)
    if documents is None or embeddings is None:
        print("文档处理失败，无法继续")
        return
    
    # 步骤2: 创建或加载FAISS索引
    print("\n[步骤2] 创建/加载FAISS索引")
    index = None
    
    if Path(INDEX_FILE).exists():
        print(f"尝试加载现有索引: {INDEX_FILE}")
        index = load_index(INDEX_FILE)
    
    if index is None:
        print("创建新索引...")
        index = create_faiss_index(embeddings, INDEX_TYPE)
        if index is None:
            print("索引创建失败，无法继续")
            return
            
        if not save_index(index, INDEX_FILE):
            print("索引保存失败")
    
    # 步骤3: 测试查询
    print("\n[步骤3] 交互式查询")
    while True:
        print("\n" + "="*50)
        query_text = input("请输入查询内容 (输入 'exit' 退出): ")
        
        if query_text.lower() == 'exit':
            break
        
        start_time = time.time()
        distances, indices = search_index(index, query_text)
        search_time = (time.time() - start_time) * 1000
        
        if distances is None or indices is None:
            print("搜索失败，请检查错误信息")
            continue
        
        print(f"\n搜索耗时: {search_time:.2f} ms")
        print(f"找到 {len(indices)} 个相关结果:")
        
        for i, (dist, idx) in enumerate(zip(distances, indices)):
            if idx < 0 or idx >= len(documents):  # 检查索引是否有效
                print(f"\n结果 #{i+1}: 无效索引 {idx}")
                continue
                
            doc = documents[idx]
            print(f"\n结果 #{i+1} (距离: {dist:.4f})")
            print(f"来源文件: {doc['file']}")
            print(f"文本摘要: {doc['chunk']}")
            # 调试时查看完整文本
            # print(f"完整文本: {doc['full_chunk']}")

if __name__ == "__main__":
    try:
        main()
        print("\n程序执行完成")
    except Exception as e:
        print(f"\n程序发生未捕获的异常: {str(e)}")
        print("="*50)
        print("异常详细信息:")
        traceback.print_exc()
        print("="*50)
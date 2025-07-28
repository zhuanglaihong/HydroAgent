"""
Author: zhuanglaihong
Date: 2025-01-21
Description: Dify知识库构建器 - 使用Dify服务器的分词模型构建知识库
"""

import os
import json
import logging
import requests
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime
import time

from langchain.schema import Document
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

logger = logging.getLogger(__name__)


class DifyKnowledgeBuilder:
    """Dify知识库构建器 - 使用Dify服务器的分词模型"""
    
    def __init__(self, 
                 dify_api_url: str,
                 dify_api_key: str,
                 embeddings_model: str = "sentence-transformers/all-MiniLM-L6-v2",
                 chunk_size: int = 1000,
                 chunk_overlap: int = 200,
                 index_path: str = "./faiss_db"):
        """
        初始化Dify知识库构建器
        
        Args:
            dify_api_url: Dify服务器API地址
            dify_api_key: Dify API密钥
            embeddings_model: 嵌入模型名称
            chunk_size: 文档分块大小
            chunk_overlap: 分块重叠大小
            index_path: 向量索引保存路径
        """
        self.dify_api_url = dify_api_url.rstrip('/')
        self.dify_api_key = dify_api_key
        self.embeddings_model = embeddings_model
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.index_path = index_path
        
        # 初始化嵌入模型
        self.embeddings = HuggingFaceEmbeddings(model_name=embeddings_model)
        
        # 创建索引目录
        os.makedirs(self.index_path, exist_ok=True)
        
        logger.info("Dify知识库构建器初始化完成")
    
    def test_dify_connection(self) -> bool:
        """测试Dify服务器连接"""
        try:
            # 测试API连接
            headers = {
                "Authorization": f"Bearer {self.dify_api_key}",
                "Content-Type": "application/json"
            }
            
            # 尝试获取服务器信息
            response = requests.get(
                f"{self.dify_api_url}/api/v1/workspaces/current",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("✅ Dify服务器连接成功")
                return True
            else:
                logger.error(f"❌ Dify服务器连接失败: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Dify服务器连接异常: {e}")
            return False
    
    def call_dify_tokenization(self, text: str) -> List[str]:
        """
        调用Dify服务器的分词服务
        
        Args:
            text: 要分词的文本
            
        Returns:
            List[str]: 分词结果
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.dify_api_key}",
                "Content-Type": "application/json"
            }
            
            # 构建请求数据
            payload = {
                "text": text,
                "model": "tokenization",  # 分词模型
                "parameters": {
                    "chunk_size": self.chunk_size,
                    "chunk_overlap": self.chunk_overlap,
                    "language": "zh"  # 中文分词
                }
            }
            
            # 调用Dify API
            response = requests.post(
                f"{self.dify_api_url}/api/v1/tokenization",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                tokens = result.get("tokens", [])
                logger.info(f"分词成功，文本长度: {len(text)}, 分词数量: {len(tokens)}")
                return tokens
            else:
                logger.error(f"分词失败: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"调用Dify分词服务异常: {e}")
            return []
    
    def process_document_with_dify(self, file_path: str) -> List[Document]:
        """
        使用Dify分词处理文档
        
        Args:
            file_path: 文档路径
            
        Returns:
            List[Document]: 处理后的文档列表
        """
        try:
            file_path = Path(file_path)
            
            if not file_path.exists():
                raise FileNotFoundError(f"文件不存在: {file_path}")
            
            # 读取文档内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            logger.info(f"开始处理文档: {file_path}")
            logger.info(f"文档长度: {len(content)} 字符")
            
            # 使用Dify分词
            tokens = self.call_dify_tokenization(content)
            
            if not tokens:
                logger.warning(f"分词失败，使用默认分块: {file_path}")
                return self._fallback_split(content, file_path)
            
            # 将分词结果转换为文档
            documents = []
            for i, token in enumerate(tokens):
                if len(token.strip()) > 10:  # 过滤太短的片段
                    doc = Document(
                        page_content=token.strip(),
                        metadata={
                            "source": str(file_path),
                            "chunk_id": i,
                            "processed_by": "dify_tokenization",
                            "timestamp": datetime.now().isoformat()
                        }
                    )
                    documents.append(doc)
            
            logger.info(f"文档处理完成: {file_path}, 生成 {len(documents)} 个片段")
            return documents
            
        except Exception as e:
            logger.error(f"处理文档失败: {file_path}, 错误: {e}")
            return []
    
    def _fallback_split(self, content: str, file_path: Path) -> List[Document]:
        """回退分块方法"""
        try:
            from langchain.text_splitter import RecursiveCharacterTextSplitter
            
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                length_function=len,
                separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""]
            )
            
            chunks = splitter.split_text(content)
            documents = []
            
            for i, chunk in enumerate(chunks):
                doc = Document(
                    page_content=chunk,
                    metadata={
                        "source": str(file_path),
                        "chunk_id": i,
                        "processed_by": "fallback_splitter",
                        "timestamp": datetime.now().isoformat()
                    }
                )
                documents.append(doc)
            
            return documents
            
        except Exception as e:
            logger.error(f"回退分块失败: {e}")
            return []
    
    def process_directory(self, directory_path: str, 
                         file_extensions: Optional[List[str]] = None) -> List[Document]:
        """
        处理目录中的所有文档
        
        Args:
            directory_path: 目录路径
            file_extensions: 文件扩展名列表
            
        Returns:
            List[Document]: 所有文档的列表
        """
        try:
            directory_path = Path(directory_path)
            
            if not directory_path.exists():
                raise FileNotFoundError(f"目录不存在: {directory_path}")
            
            # 确定文件扩展名
            if file_extensions is None:
                file_extensions = [".txt", ".md", ".pdf", ".docx", ".csv"]
            
            all_documents = []
            
            # 遍历目录
            for file_path in directory_path.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in file_extensions:
                    logger.info(f"发现文件: {file_path}")
                    
                    # 处理文档
                    documents = self.process_document_with_dify(str(file_path))
                    all_documents.extend(documents)
                    
                    # 添加延迟避免API限制
                    time.sleep(0.5)
            
            logger.info(f"目录处理完成: {directory_path}, 总文档数: {len(all_documents)}")
            return all_documents
            
        except Exception as e:
            logger.error(f"处理目录失败: {directory_path}, 错误: {e}")
            return []
    
    def create_vector_index(self, documents: List[Document], 
                           index_name: str = "dify_knowledge_index") -> bool:
        """
        创建向量索引
        
        Args:
            documents: 文档列表
            index_name: 索引名称
            
        Returns:
            bool: 是否成功
        """
        try:
            if not documents:
                logger.warning("没有文档可以创建索引")
                return False
            
            logger.info(f"开始创建向量索引，文档数量: {len(documents)}")
            
            # 创建FAISS向量存储
            vector_store = FAISS.from_documents(
                documents=documents,
                embedding=self.embeddings
            )
            
            # 保存索引
            index_path = os.path.join(self.index_path, index_name)
            vector_store.save_local(index_path)
            
            logger.info(f"✅ 向量索引创建成功: {index_path}")
            logger.info(f"索引包含 {len(documents)} 个文档片段")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 创建向量索引失败: {e}")
            return False
    
    def build_knowledge_base(self, 
                            source_path: str,
                            file_extensions: Optional[List[str]] = None,
                            index_name: str = "dify_knowledge_index") -> bool:
        """
        构建完整的知识库
        
        Args:
            source_path: 源路径（文件或目录）
            file_extensions: 文件扩展名列表
            index_name: 索引名称
            
        Returns:
            bool: 是否成功
        """
        try:
            logger.info("🚀 开始构建Dify知识库...")
            
            # 1. 测试连接
            if not self.test_dify_connection():
                logger.error("无法连接到Dify服务器，构建失败")
                return False
            
            # 2. 处理文档
            source_path = Path(source_path)
            
            if source_path.is_file():
                documents = self.process_document_with_dify(str(source_path))
            elif source_path.is_dir():
                documents = self.process_directory(str(source_path), file_extensions)
            else:
                logger.error(f"源路径不存在: {source_path}")
                return False
            
            if not documents:
                logger.error("没有处理到任何文档")
                return False
            
            # 3. 创建向量索引
            success = self.create_vector_index(documents, index_name)
            
            if success:
                logger.info("🎉 Dify知识库构建完成！")
                return True
            else:
                logger.error("❌ 知识库构建失败")
                return False
                
        except Exception as e:
            logger.error(f"构建知识库过程中发生错误: {e}")
            return False
    
    def query_knowledge_base(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        查询知识库
        
        Args:
            query: 查询文本
            k: 返回结果数量
            
        Returns:
            List[Dict]: 查询结果
        """
        try:
            # 加载向量存储
            index_path = os.path.join(self.index_path, "dify_knowledge_index")
            
            if not os.path.exists(index_path):
                logger.error("知识库索引不存在")
                return []
            
            vector_store = FAISS.load_local(index_path, self.embeddings)
            
            # 执行查询
            results = vector_store.similarity_search_with_score(query, k=k)
            
            # 格式化结果
            formatted_results = []
            for doc, score in results:
                formatted_results.append({
                    "content": doc.page_content,
                    "score": float(score),
                    "metadata": doc.metadata
                })
            
            logger.info(f"查询完成，返回 {len(formatted_results)} 个结果")
            return formatted_results
            
        except Exception as e:
            logger.error(f"查询知识库失败: {e}")
            return []
    
    def get_knowledge_base_info(self) -> Dict[str, Any]:
        """获取知识库信息"""
        try:
            index_path = os.path.join(self.index_path, "dify_knowledge_index")
            
            info = {
                "index_exists": os.path.exists(index_path),
                "index_path": index_path,
                "embeddings_model": self.embeddings_model,
                "chunk_size": self.chunk_size,
                "chunk_overlap": self.chunk_overlap,
                "dify_api_url": self.dify_api_url,
                "dify_connection": self.test_dify_connection()
            }
            
            if os.path.exists(index_path):
                # 尝试加载索引获取更多信息
                try:
                    vector_store = FAISS.load_local(index_path, self.embeddings)
                    info["index_size"] = vector_store.index.ntotal
                    info["index_dimension"] = vector_store.index.d
                except Exception as e:
                    logger.warning(f"无法获取索引详细信息: {e}")
            
            return info
            
        except Exception as e:
            logger.error(f"获取知识库信息失败: {e}")
            return {"error": str(e)}


def main():
    """主函数 - 演示Dify知识库构建"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Dify知识库构建器")
    parser.add_argument("--dify_url", required=True, help="Dify服务器URL")
    parser.add_argument("--dify_key", required=True, help="Dify API密钥")
    parser.add_argument("--source", required=True, help="源文档路径")
    parser.add_argument("--index_name", default="dify_knowledge_index", help="索引名称")
    parser.add_argument("--chunk_size", type=int, default=1000, help="分块大小")
    parser.add_argument("--chunk_overlap", type=int, default=200, help="分块重叠")
    parser.add_argument("--embeddings_model", default="sentence-transformers/all-MiniLM-L6-v2", help="嵌入模型")
    parser.add_argument("--test_query", help="测试查询")
    
    args = parser.parse_args()
    
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🌟 Dify知识库构建器")
    print("=" * 50)
    
    try:
        # 创建构建器
        builder = DifyKnowledgeBuilder(
            dify_api_url=args.dify_url,
            dify_api_key=args.dify_key,
            embeddings_model=args.embeddings_model,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap
        )
        
        # 构建知识库
        success = builder.build_knowledge_base(
            source_path=args.source,
            index_name=args.index_name
        )
        
        if success:
            print("✅ 知识库构建成功！")
            
            # 显示知识库信息
            info = builder.get_knowledge_base_info()
            print(f"\n📊 知识库信息:")
            for key, value in info.items():
                print(f"  {key}: {value}")
            
            # 测试查询
            if args.test_query:
                print(f"\n🔍 测试查询: {args.test_query}")
                results = builder.query_knowledge_base(args.test_query)
                
                for i, result in enumerate(results, 1):
                    print(f"\n结果 {i}:")
                    print(f"  内容: {result['content'][:200]}...")
                    print(f"  分数: {result['score']:.4f}")
                    print(f"  来源: {result['metadata'].get('source', 'unknown')}")
        
        else:
            print("❌ 知识库构建失败")
            
    except Exception as e:
        print(f"❌ 程序执行出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 
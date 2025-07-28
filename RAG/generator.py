"""
Author: zhuanglaihong
Date: 2025-07-24 15:03:46
LastEditTime: 2025-07-24 15:03:46
LastEditors: zhuanglaihong
Description: 生成器模块 - 负责基于检索结果生成最终答案
FilePath: RAG/generator.py
Copyright: Copyright (c) 2021-2024 zhuanglaihong. All rights reserved.
"""

from typing import List, Dict, Any, Optional, Tuple
import logging
from abc import ABC, abstractmethod

from langchain.schema import Document
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.chains.question_answering import load_qa_chain
from langchain.chains.summarize import load_summarize_chain
from langchain.chains.retrieval_qa import RetrievalQA
from langchain.chains.conversation.memory import ConversationBufferMemory
from langchain.chains.conversation import ConversationChain

logger = logging.getLogger(__name__)


class BaseGenerator(ABC):
    """生成器基类"""

    @abstractmethod
    def generate(self, query: str, context: List[Document], **kwargs) -> str:
        """
        生成答案

        Args:
            query: 查询文本
            context: 上下文文档列表
            **kwargs: 其他参数

        Returns:
            生成的答案
        """
        pass


class QAChainGenerator(BaseGenerator):
    """问答链生成器"""

    def __init__(
        self, llm, chain_type: str = "stuff", prompt_template: Optional[str] = None
    ):
        """
        初始化问答链生成器

        Args:
            llm: 语言模型
            chain_type: 链类型 ("stuff", "map_reduce", "refine")
            prompt_template: 自定义提示模板
        """
        self.llm = llm
        self.chain_type = chain_type

        if prompt_template:
            self.prompt = PromptTemplate(
                template=prompt_template, input_variables=["context", "question"]
            )
        else:
            self.prompt = None

        self.chain = load_qa_chain(llm=llm, chain_type=chain_type, prompt=self.prompt)

    def generate(self, query: str, context: List[Document], **kwargs) -> str:
        """
        生成答案

        Args:
            query: 查询文本
            context: 上下文文档列表
            **kwargs: 其他参数

        Returns:
            生成的答案
        """
        try:
            if not context:
                return "抱歉，没有找到相关的上下文信息来回答您的问题。"

            # 准备输入
            inputs = {
                "question": query,
                "context": "\n\n".join([doc.page_content for doc in context]),
            }

            # 生成答案
            result = self.chain.run(inputs)

            logger.info(f"问答链生成完成，查询: {query[:50]}...")
            return result

        except Exception as e:
            logger.error(f"问答链生成失败: {str(e)}")
            return f"生成答案时出现错误: {str(e)}"


class SummarizeGenerator(BaseGenerator):
    """总结生成器"""

    def __init__(self, llm, chain_type: str = "map_reduce"):
        """
        初始化总结生成器

        Args:
            llm: 语言模型
            chain_type: 链类型 ("stuff", "map_reduce", "refine")
        """
        self.llm = llm
        self.chain_type = chain_type
        self.chain = load_summarize_chain(llm=llm, chain_type=chain_type)

    def generate(self, query: str, context: List[Document], **kwargs) -> str:
        """
        生成总结

        Args:
            query: 查询文本（作为总结的指导）
            context: 要总结的文档列表
            **kwargs: 其他参数

        Returns:
            生成的总结
        """
        try:
            if not context:
                return "没有内容可以总结。"

            # 准备输入
            inputs = {"input_documents": context, "question": query}  # 作为总结的指导

            # 生成总结
            result = self.chain.run(inputs)

            logger.info(f"总结生成完成，文档数量: {len(context)}")
            return result

        except Exception as e:
            logger.error(f"总结生成失败: {str(e)}")
            return f"生成总结时出现错误: {str(e)}"


class ConversationalGenerator(BaseGenerator):
    """对话生成器"""

    def __init__(self, llm, memory_key: str = "chat_history"):
        """
        初始化对话生成器

        Args:
            llm: 语言模型
            memory_key: 记忆键名
        """
        self.llm = llm
        self.memory_key = memory_key
        self.memory = ConversationBufferMemory(
            memory_key=memory_key, return_messages=True
        )

        # 创建对话链
        self.chain = ConversationChain(llm=llm, memory=self.memory, verbose=False)

    def generate(self, query: str, context: List[Document] = None, **kwargs) -> str:
        """
        生成对话回复

        Args:
            query: 用户输入
            context: 上下文文档列表（可选）
            **kwargs: 其他参数

        Returns:
            生成的回复
        """
        try:
            # 如果有上下文，将其添加到查询中
            if context:
                context_text = "\n\n".join([doc.page_content for doc in context])
                enhanced_query = (
                    f"基于以下信息回答问题：\n{context_text}\n\n问题：{query}"
                )
            else:
                enhanced_query = query

            # 生成回复
            result = self.chain.run(enhanced_query)

            logger.info(f"对话生成完成，输入: {query[:50]}...")
            return result

        except Exception as e:
            logger.error(f"对话生成失败: {str(e)}")
            return f"生成回复时出现错误: {str(e)}"

    def clear_memory(self):
        """清除对话记忆"""
        self.memory.clear()


class RetrievalQAGenerator(BaseGenerator):
    """检索问答生成器"""

    def __init__(self, llm, retriever, chain_type: str = "stuff"):
        """
        初始化检索问答生成器

        Args:
            llm: 语言模型
            retriever: 检索器
            chain_type: 链类型
        """
        self.llm = llm
        self.retriever = retriever
        self.chain_type = chain_type

        self.qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type=chain_type,
            retriever=retriever,
            return_source_documents=True,
        )

    def generate(self, query: str, context: List[Document] = None, **kwargs) -> str:
        """
        生成答案

        Args:
            query: 查询文本
            context: 上下文文档列表（在此生成器中不使用）
            **kwargs: 其他参数

        Returns:
            生成的答案
        """
        try:
            # 使用检索问答链
            result = self.qa_chain({"query": query})

            answer = result.get("result", "无法生成答案")
            source_docs = result.get("source_documents", [])

            # 添加来源信息
            if source_docs:
                sources = [
                    doc.metadata.get("source", "未知来源") for doc in source_docs
                ]
                answer += f"\n\n来源: {', '.join(sources)}"

            logger.info(f"检索问答生成完成，查询: {query[:50]}...")
            return answer

        except Exception as e:
            logger.error(f"检索问答生成失败: {str(e)}")
            return f"生成答案时出现错误: {str(e)}"


class Generator:
    """生成器主类"""

    def __init__(self, llm):
        """
        初始化生成器

        Args:
            llm: 语言模型
        """
        self.llm = llm
        self.generators = {}

        # 初始化默认生成器
        self._initialize_generators()

    def _initialize_generators(self):
        """初始化默认生成器"""
        try:
            self.generators["qa"] = QAChainGenerator(self.llm)
            self.generators["summarize"] = SummarizeGenerator(self.llm)
            self.generators["conversational"] = ConversationalGenerator(self.llm)

        except Exception as e:
            logger.warning(f"初始化默认生成器失败: {str(e)}")

    def add_generator(self, name: str, generator: BaseGenerator):
        """
        添加生成器

        Args:
            name: 生成器名称
            generator: 生成器对象
        """
        self.generators[name] = generator

    def add_retrieval_qa_generator(self, name: str, retriever):
        """
        添加检索问答生成器

        Args:
            name: 生成器名称
            retriever: 检索器对象
        """
        try:
            self.generators[name] = RetrievalQAGenerator(self.llm, retriever)
        except Exception as e:
            logger.error(f"添加检索问答生成器失败: {str(e)}")

    def generate(
        self, query: str, context: List[Document], generator_name: str = "qa", **kwargs
    ) -> str:
        """
        生成答案

        Args:
            query: 查询文本
            context: 上下文文档列表
            generator_name: 生成器名称
            **kwargs: 其他参数

        Returns:
            生成的答案
        """
        if generator_name not in self.generators:
            logger.warning(f"生成器 {generator_name} 不可用，使用默认生成器")
            generator_name = (
                list(self.generators.keys())[0] if self.generators else None
            )

        if not generator_name:
            logger.error("没有可用的生成器")
            return "无法生成答案，没有可用的生成器。"

        try:
            generator = self.generators[generator_name]
            result = generator.generate(query, context, **kwargs)

            return result

        except Exception as e:
            logger.error(f"生成失败: {str(e)}")
            return f"生成答案时出现错误: {str(e)}"

    def get_available_generators(self) -> List[str]:
        """
        获取可用的生成器列表

        Returns:
            生成器名称列表
        """
        return list(self.generators.keys())

    def get_generator_info(self, generator_name: str) -> Dict[str, Any]:
        """
        获取生成器信息

        Args:
            generator_name: 生成器名称

        Returns:
            生成器信息字典
        """
        if generator_name not in self.generators:
            return {"error": f"生成器 {generator_name} 不存在"}

        generator = self.generators[generator_name]
        info = {
            "name": generator_name,
            "type": type(generator).__name__,
            "available": True,
        }

        return info

    def clear_conversation_memory(self):
        """清除对话记忆"""
        for name, generator in self.generators.items():
            if isinstance(generator, ConversationalGenerator):
                generator.clear_memory()
                logger.info(f"已清除生成器 {name} 的对话记忆")

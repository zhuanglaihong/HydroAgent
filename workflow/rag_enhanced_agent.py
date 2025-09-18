"""
RAG增强的Agent模块
整合HydroRAG知识库与工作流系统，为Agent提供知识增强的工作流生成能力
"""

import logging
import os
import hashlib
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
import asyncio
from datetime import datetime

# 项目导入
from .workflow_types import WorkflowPlan, IntentAnalysis, WorkflowRequest
from .intent_processor import IntentProcessor
from .query_expander import QueryExpander
from .context_builder import ContextBuilder
from .workflow_generator import WorkflowGenerator

logger = logging.getLogger(__name__)


class RAGEnhancedWorkflowManager:
    """RAG增强的工作流管理器"""
    
    def __init__(self, llm, enable_rag: bool = True, documents_dir: str = None, rebuild_vector_db: bool = False):
        """
        初始化RAG增强工作流管理器
        
        Args:
            llm: 语言模型实例
            enable_rag: 是否启用RAG功能
            documents_dir: 文档目录路径
            rebuild_vector_db: 是否重建向量数据库
        """
        self.llm = llm
        self.enable_rag = enable_rag
        self.rebuild_vector_db = rebuild_vector_db
        self.documents_dir = documents_dir or self._get_default_documents_dir()
        
        # RAG组件
        self.rag_system = None
        self.knowledge_retriever = None
        
        # 工作流组件
        self.intent_processor = None
        self.query_expander = None
        self.context_builder = None
        self.workflow_generator = None
        
        # 状态
        self.is_initialized = False
        self.initialization_errors = []
        
        # 配置
        self.rag_config = {
            "knowledge_top_k": 5,
            "knowledge_threshold": 0.3,
            "enable_fallback": True,
            "use_knowledge_cache": True,
            "auto_update_vectordb": False,  # 默认不自动更新向量库
            "document_check_interval": 300  # 5分钟检查一次
        }
        
        # 文档监控相关
        self.raw_documents_dir = os.path.join(self.documents_dir, "raw")
        self.document_hash_file = os.path.join(self.documents_dir, ".document_hashes.json")
        self.last_document_check = None
        self.document_hashes = {}
    
    def _get_default_documents_dir(self) -> str:
        """获取默认文档目录"""
        repo_path = Path(__file__).parent.parent
        return os.path.join(repo_path, "documents")
    
    async def initialize(self):
        """异步初始化所有组件"""
        try:
            logger.info("开始初始化RAG增强工作流管理器")
            
            # 1. 初始化基础工作流组件
            await self._initialize_workflow_components()
            
            # 2. 初始化RAG系统（如果启用）
            if self.enable_rag:
                await self._initialize_rag_system()
            else:
                logger.info("RAG功能已禁用，使用基础工作流模式")
            
            # 3. 验证初始化状态
            self.is_initialized = self._validate_initialization()
            
            if self.is_initialized:
                logger.info("RAG增强工作流管理器初始化成功")
            else:
                logger.warning(f"初始化部分失败: {self.initialization_errors}")
                
        except Exception as e:
            error_msg = f"RAG增强工作流管理器初始化失败: {e}"
            self.initialization_errors.append(error_msg)
            logger.error(error_msg)
            self.is_initialized = False
    
    async def _initialize_workflow_components(self):
        """初始化工作流组件"""
        try:
            logger.debug("初始化基础工作流组件")
            
            # 初始化意图处理器
            self.intent_processor = IntentProcessor(self.llm)
            
            # 初始化查询扩展器
            self.query_expander = QueryExpander(self.llm)
            
            # 初始化上下文构建器
            self.context_builder = ContextBuilder()
            
            # 初始化工作流生成器
            self.workflow_generator = WorkflowGenerator(self.llm)
            
            logger.debug("基础工作流组件初始化完成")
            
        except Exception as e:
            error_msg = f"工作流组件初始化失败: {e}"
            self.initialization_errors.append(error_msg)
            logger.error(error_msg)
            raise
    
    async def _initialize_rag_system(self):
        """初始化RAG系统"""
        try:
            logger.debug("初始化RAG系统")
            
            # 动态导入RAG模块
            try:
                from hydrorag.rag_system import quick_setup
                from .knowledge_retriever import KnowledgeRetriever
                
                # 检查文档变更并可能重建向量库
                await self._check_and_update_documents()
                
                # 初始化RAG系统
                self.rag_system = quick_setup(self.documents_dir)
                
                if not self.rag_system or not self.rag_system.is_initialized:
                    error_msg = "RAG系统初始化失败"
                    self.initialization_errors.append(error_msg)
                    logger.error(error_msg)
                    return
                
                # 初始化知识检索器
                self.knowledge_retriever = KnowledgeRetriever(
                    rag_system=self.rag_system,
                    enable_fallback=self.rag_config["enable_fallback"]
                )
                
                logger.info("RAG系统初始化成功")
                
            except ImportError as e:
                error_msg = f"RAG模块导入失败: {e}"
                self.initialization_errors.append(error_msg)
                logger.warning(error_msg + "，将使用基础工作流模式")
                self.enable_rag = False
                
        except Exception as e:
            error_msg = f"RAG系统初始化失败: {e}"
            self.initialization_errors.append(error_msg)
            logger.error(error_msg)
            self.enable_rag = False
    
    def _validate_initialization(self) -> bool:
        """验证初始化状态"""
        # 基础组件必须存在
        basic_components_ready = all([
            self.intent_processor is not None,
            self.query_expander is not None,
            self.context_builder is not None,
            self.workflow_generator is not None
        ])
        
        if not basic_components_ready:
            return False
        
        # 如果启用RAG，检查RAG组件
        if self.enable_rag:
            rag_components_ready = all([
                self.rag_system is not None,
                self.knowledge_retriever is not None
            ])
            return rag_components_ready
        
        return True
    
    async def generate_enhanced_workflow(
        self, 
        user_query: str,
        use_knowledge: Optional[bool] = None,
        knowledge_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        生成RAG增强的工作流
        
        Args:
            user_query: 用户查询
            use_knowledge: 是否使用知识库（None时自动决定）
            knowledge_config: 知识检索配置
            
        Returns:
            Dict包含工作流和相关信息
        """
        try:
            if not self.is_initialized:
                return {
                    "status": "error",
                    "error": "RAG增强工作流管理器未初始化",
                    "initialization_errors": self.initialization_errors
                }
            
            logger.info(f"开始生成RAG增强工作流: {user_query}")
            
            # 1. 处理用户意图
            intent_analysis = await self._process_intent(user_query)
            
            # 2. 决定是否使用知识库
            use_rag = self._should_use_knowledge(use_knowledge, intent_analysis)
            
            # 3. 知识检索（如果启用）
            knowledge_fragments = []
            knowledge_stats = {}
            if use_rag and self.knowledge_retriever:
                knowledge_result = await self._retrieve_knowledge(user_query, intent_analysis, knowledge_config)
                knowledge_fragments = knowledge_result.get("fragments", [])
                knowledge_stats = knowledge_result.get("stats", {})
            
            # 4. 查询扩展
            expanded_query = await self._expand_query(intent_analysis, knowledge_fragments)
            
            # 5. 构建上下文
            context = await self._build_context(
                user_query, intent_analysis, knowledge_fragments, expanded_query
            )
            
            # 6. 生成工作流
            workflow_plan = await self._generate_workflow(
                context, user_query, expanded_query, intent_analysis
            )
            
            # 7. 构建结果
            result = {
                "status": "success",
                "workflow_plan": workflow_plan,
                "knowledge_enhanced": use_rag,
                "knowledge_fragments": knowledge_fragments,
                "knowledge_stats": knowledge_stats,
                "intent_analysis": intent_analysis,
                "expanded_query": expanded_query,
                "generation_metadata": {
                    "rag_enabled": self.enable_rag,
                    "knowledge_used": use_rag,
                    "fragments_count": len(knowledge_fragments),
                    "query_expansion_length": len(expanded_query.split()) if expanded_query else 0
                }
            }
            
            logger.info(f"RAG增强工作流生成完成: {workflow_plan.name}")
            return result
            
        except Exception as e:
            error_msg = f"RAG增强工作流生成失败: {e}"
            logger.error(error_msg)
            return {
                "status": "error",
                "error": error_msg,
                "query": user_query,
                "knowledge_enhanced": use_rag if 'use_rag' in locals() else False
            }
    
    async def _process_intent(self, user_query: str) -> IntentAnalysis:
        """处理用户意图"""
        try:
            return self.intent_processor.process_intent(user_query)
        except Exception as e:
            logger.error(f"意图处理失败: {e}")
            # 返回基础意图分析
            return IntentAnalysis(
                clarified_intent=user_query,
                task_type="general_query",
                entities={},
                suggested_tools=[],
                confidence=0.5
            )
    
    def _should_use_knowledge(self, use_knowledge: Optional[bool], intent_analysis: IntentAnalysis) -> bool:
        """决定是否使用知识库"""
        # 如果明确指定，则使用指定值
        if use_knowledge is not None:
            return use_knowledge and self.enable_rag
        
        # 如果RAG未启用，则不使用
        if not self.enable_rag:
            return False
        
        # 根据任务类型自动决定
        knowledge_beneficial_tasks = [
            "model_configuration",
            "parameter_query",
            "model_calibration",
            "model_evaluation",
            "data_preparation"
        ]
        
        return intent_analysis.task_type in knowledge_beneficial_tasks
    
    async def _retrieve_knowledge(
        self, 
        user_query: str, 
        intent_analysis: IntentAnalysis,
        knowledge_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """检索相关知识"""
        try:
            # 合并配置
            config = {**self.rag_config}
            if knowledge_config:
                config.update(knowledge_config)
            
            # 执行知识检索
            fragments = await asyncio.get_event_loop().run_in_executor(
                None,
                self.knowledge_retriever.retrieve_knowledge,
                user_query,
                intent_analysis,
                config["knowledge_top_k"],
                config["knowledge_threshold"]
            )
            
            # 获取检索统计信息
            stats = {}
            if hasattr(self.knowledge_retriever, "get_last_retrieval_stats"):
                stats = self.knowledge_retriever.get_last_retrieval_stats()
            
            return {
                "fragments": fragments,
                "stats": stats
            }
            
        except Exception as e:
            logger.error(f"知识检索失败: {e}")
            return {"fragments": [], "stats": {}}
    
    async def _expand_query(self, intent_analysis: IntentAnalysis, knowledge_fragments: List) -> str:
        """扩展查询"""
        try:
            return self.query_expander.expand_query(intent_analysis)
        except Exception as e:
            logger.error(f"查询扩展失败: {e}")
            return intent_analysis.clarified_intent
    
    async def _build_context(
        self, 
        user_query: str, 
        intent_analysis: IntentAnalysis,
        knowledge_fragments: List,
        expanded_query: str
    ) -> Dict[str, Any]:
        """构建执行上下文"""
        try:
            return self.context_builder.build_context(
                user_query=user_query,
                intent_analysis=intent_analysis,
                knowledge_fragments=knowledge_fragments,
                expanded_query=expanded_query
            )
        except Exception as e:
            logger.error(f"上下文构建失败: {e}")
            return {
                "user_query": user_query,
                "intent_analysis": intent_analysis,
                "knowledge_fragments": knowledge_fragments,
                "expanded_query": expanded_query
            }
    
    async def _generate_workflow(
        self,
        context: Dict[str, Any],
        user_query: str,
        expanded_query: str,
        intent_analysis: IntentAnalysis
    ) -> WorkflowPlan:
        """生成工作流计划"""
        try:
            return self.workflow_generator.generate_workflow(
                context=context,
                user_query=user_query,
                expanded_query=expanded_query,
                intent_analysis=intent_analysis
            )
        except Exception as e:
            logger.error(f"工作流生成失败: {e}")
            # 返回基础工作流
            from .workflow_types import WorkflowStep
            
            import uuid
            from datetime import datetime
            
            workflow_id = f"fallback_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
            
            return WorkflowPlan(
                workflow_id=workflow_id,
                name="基础任务执行",
                description=f"执行用户请求: {user_query}",
                steps=[
                    WorkflowStep(
                        step_id="step_1",
                        name="任务执行",
                        description="执行用户指定的任务",
                        tool_name="execute_query",
                        parameters={"query": user_query}
                    )
                ],
                user_query=user_query,
                expanded_query=user_query,
                context=""
            )
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        return {
            "is_initialized": self.is_initialized,
            "rag_enabled": self.enable_rag,
            "initialization_errors": self.initialization_errors,
            "components": {
                "intent_processor": self.intent_processor is not None,
                "query_expander": self.query_expander is not None,
                "context_builder": self.context_builder is not None,
                "workflow_generator": self.workflow_generator is not None,
                "rag_system": self.rag_system is not None,
                "knowledge_retriever": self.knowledge_retriever is not None
            },
            "rag_config": self.rag_config,
            "documents_directory": self.documents_dir
        }
    
    def update_rag_config(self, new_config: Dict[str, Any]):
        """更新RAG配置"""
        self.rag_config.update(new_config)
        logger.info(f"RAG配置已更新: {self.rag_config}")
    
    async def _check_and_update_documents(self):
        """检查文档变更并处理文档"""
        try:
            if not os.path.exists(self.raw_documents_dir):
                logger.warning(f"原始文档目录不存在: {self.raw_documents_dir}")
                return
            
            # 总是处理raw文档到processed
            await self._process_raw_documents()
            
            # 根据参数决定是否重建向量库
            if self.rebuild_vector_db:
                logger.info("用户要求重建向量数据库...")
                await self._rebuild_vector_database()
                
                # 更新文档哈希
                current_hashes = self._calculate_document_hashes()
                self.document_hashes = current_hashes
                self._save_document_hashes()
                
                logger.info("向量库重建完成")
            else:
                # 检查是否需要自动更新
                if self.rag_config.get("auto_update_vectordb", False):
                    # 加载历史文档哈希
                    self._load_document_hashes()
                    
                    # 计算当前文档哈希
                    current_hashes = self._calculate_document_hashes()
                    
                    # 检查是否有变更
                    documents_changed = self._detect_document_changes(current_hashes)
                    
                    if documents_changed:
                        logger.info("检测到文档变更，开始重建向量库...")
                        await self._rebuild_vector_database()
                        
                        # 保存新的文档哈希
                        self.document_hashes = current_hashes
                        self._save_document_hashes()
                        
                        logger.info("向量库重建完成")
                    else:
                        logger.debug("未检测到文档变更，无需更新向量库")
                else:
                    logger.debug("自动向量库更新已禁用，仅处理文档")
            
            # 更新检查时间
            self.last_document_check = datetime.now()
            
        except Exception as e:
            logger.error(f"文档检查和更新失败: {e}")
            # 不中断初始化流程
    
    def _load_document_hashes(self):
        """加载文档哈希记录"""
        try:
            if os.path.exists(self.document_hash_file):
                with open(self.document_hash_file, 'r', encoding='utf-8') as f:
                    self.document_hashes = json.load(f)
                logger.debug(f"加载了 {len(self.document_hashes)} 个文档哈希记录")
            else:
                self.document_hashes = {}
                logger.debug("没有找到文档哈希文件，初始化为空")
        except Exception as e:
            logger.error(f"加载文档哈希失败: {e}")
            self.document_hashes = {}
    
    def _save_document_hashes(self):
        """保存文档哈希记录"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.document_hash_file), exist_ok=True)
            
            with open(self.document_hash_file, 'w', encoding='utf-8') as f:
                json.dump(self.document_hashes, f, indent=2, ensure_ascii=False)
            logger.debug(f"保存了 {len(self.document_hashes)} 个文档哈希记录")
        except Exception as e:
            logger.error(f"保存文档哈希失败: {e}")
    
    def _calculate_document_hashes(self) -> Dict[str, str]:
        """计算当前文档的哈希值"""
        current_hashes = {}
        
        try:
            if not os.path.exists(self.raw_documents_dir):
                return current_hashes
            
            # 遍历raw目录中的所有文档
            for file_path in Path(self.raw_documents_dir).rglob("*"):
                if file_path.is_file():
                    # 支持的文档格式
                    supported_extensions = {'.txt', '.md', '.json', '.yaml', '.yml'}
                    if file_path.suffix.lower() in supported_extensions:
                        try:
                            # 计算文件内容的MD5哈希
                            with open(file_path, 'rb') as f:
                                file_hash = hashlib.md5(f.read()).hexdigest()
                            
                            # 使用相对路径作为键
                            relative_path = str(file_path.relative_to(self.raw_documents_dir))
                            current_hashes[relative_path] = file_hash
                            
                        except Exception as e:
                            logger.warning(f"计算文件哈希失败 {file_path}: {e}")
            
            logger.debug(f"计算了 {len(current_hashes)} 个文档的哈希值")
            
        except Exception as e:
            logger.error(f"计算文档哈希失败: {e}")
        
        return current_hashes
    
    def _detect_document_changes(self, current_hashes: Dict[str, str]) -> bool:
        """检测文档是否有变更"""
        try:
            # 检查新增文件
            new_files = set(current_hashes.keys()) - set(self.document_hashes.keys())
            if new_files:
                logger.info(f"检测到新增文档: {new_files}")
                return True
            
            # 检查删除文件
            deleted_files = set(self.document_hashes.keys()) - set(current_hashes.keys())
            if deleted_files:
                logger.info(f"检测到删除文档: {deleted_files}")
                return True
            
            # 检查修改文件
            modified_files = []
            for file_path in current_hashes:
                if file_path in self.document_hashes:
                    if current_hashes[file_path] != self.document_hashes[file_path]:
                        modified_files.append(file_path)
            
            if modified_files:
                logger.info(f"检测到修改文档: {modified_files}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"检测文档变更失败: {e}")
            # 如果检测失败，保守起见返回True以触发重建
            return True
    
    async def _process_raw_documents(self):
        """处理raw目录下的文档到processed目录"""
        try:
            logger.info("开始处理raw文档...")
            
            # 动态导入相关组件
            from hydrorag.document_processor import DocumentProcessor
            from hydrorag.config import Config
            
            # 创建配置对象
            config = Config(
                documents_dir=self.documents_dir,
                raw_documents_dir=self.raw_documents_dir,
                processed_documents_dir=os.path.join(self.documents_dir, "processed"),
                chunk_size=500,
                chunk_overlap=50
            )
            
            # 创建文档处理器
            processor = DocumentProcessor(config)
            
            # 获取所有需要处理的文档
            raw_dir = Path(self.raw_documents_dir)
            if not raw_dir.exists():
                logger.warning("raw文档目录不存在")
                return
            
            # 使用异步方式处理文档
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                processor.process_all_documents
            )
            
            if result.get("status") == "completed":
                processed_count = result.get('processed', 0)
                failed_count = result.get('failed', 0)
                skipped_count = result.get('skipped', 0)
                logger.info(f"Raw文档处理完成: 成功 {processed_count}, 失败 {failed_count}, 跳过 {skipped_count}")
            else:
                logger.warning(f"文档处理结果: {result}")
            
        except Exception as e:
            logger.error(f"处理raw文档失败: {e}")
            # 不抛出异常，允许系统继续初始化
    
    async def _rebuild_vector_database(self):
        """重建向量数据库"""
        try:
            logger.info("开始重建向量数据库...")
            
            # 动态导入RAG组件
            from hydrorag.rag_system import RAGSystem
            from hydrorag.config import Config
            
            # 创建配置
            config = Config(
                documents_dir=self.documents_dir,
                raw_documents_dir=self.raw_documents_dir,
                processed_documents_dir=os.path.join(self.documents_dir, "processed"),
                vector_db_dir=os.path.join(self.documents_dir, "vector_db"),
                chunk_size=500,
                chunk_overlap=50
            )
            
            # 只有在用户明确要求重建时才删除现有向量库
            if self.rebuild_vector_db:
                vector_db_dir = os.path.join(self.documents_dir, "vector_db")
                if os.path.exists(vector_db_dir):
                    import shutil
                    logger.info("用户要求重建向量库，删除现有向量数据库...")
                    shutil.rmtree(vector_db_dir)
            else:
                logger.info("保留现有向量库，仅构建索引...")
            
            # 创建新的RAG系统实例
            temp_rag_system = RAGSystem(config)
            
            # 检查processed目录
            processed_dir = Path(os.path.join(self.documents_dir, "processed"))
            if not processed_dir.exists():
                logger.warning("processed目录不存在，无法构建向量库")
                return
            
            # 获取所有processed文档文件
            processed_files = []
            for file_path in processed_dir.rglob("*.json"):
                if file_path.is_file() and "_processed.json" in file_path.name:
                    processed_files.append(str(file_path))
            
            if not processed_files:
                logger.warning("未找到processed文档文件")
                return
            
            logger.info(f"使用 {len(processed_files)} 个processed文档构建向量库...")
            
            # 使用RAG系统的标准方法构建向量库
            # rebuild参数取决于用户是否明确要求重建
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                temp_rag_system.build_vector_index,
                self.rebuild_vector_db  # 使用用户指定的重建参数
            )
            
            if result.get("status") in ["completed", "success"]:
                total_docs = result.get('total_documents_processed', 0)
                total_chunks = result.get('total_chunks_added', 0)
                failed_docs = result.get('failed_documents', 0)
                logger.info(f"向量库构建完成: 处理 {total_docs} 个文档, 添加 {total_chunks} 个向量块, {failed_docs} 个失败")
            else:
                logger.warning(f"向量库构建结果: {result}")
            
            logger.info("向量数据库处理完成")
            
        except Exception as e:
            logger.error(f"重建向量数据库失败: {e}")
            raise
    
    async def check_documents_periodically(self):
        """定期检查文档变更（可在后台任务中调用）"""
        try:
            if not self.enable_rag or not self.rag_config.get("auto_update_vectordb", True):
                return
            
            # 检查是否需要检查（避免频繁检查）
            if self.last_document_check:
                time_since_check = (datetime.now() - self.last_document_check).total_seconds()
                check_interval = self.rag_config.get("document_check_interval", 300)
                
                if time_since_check < check_interval:
                    return
            
            # 执行检查
            await self._check_and_update_documents()
            
        except Exception as e:
            logger.error(f"定期文档检查失败: {e}")
    
    async def cleanup(self):
        """清理资源"""
        try:
            logger.info("清理RAG增强工作流管理器资源")
            
            # 清理RAG系统
            if self.rag_system and hasattr(self.rag_system, 'cleanup'):
                try:
                    if asyncio.iscoroutinefunction(self.rag_system.cleanup):
                        await self.rag_system.cleanup()
                    else:
                        self.rag_system.cleanup()
                except Exception as e:
                    logger.warning(f"清理RAG系统时出错: {e}")
            
            # 清理工作流组件
            components = [
                self.intent_processor,
                self.query_expander,
                self.context_builder,
                self.workflow_generator,
                self.knowledge_retriever
            ]
            
            for component in components:
                if component and hasattr(component, 'cleanup'):
                    try:
                        if asyncio.iscoroutinefunction(component.cleanup):
                            await component.cleanup()
                        else:
                            component.cleanup()
                    except Exception as e:
                        logger.warning(f"清理组件时出错: {e}")
            
            # 重置状态
            self.is_initialized = False
            logger.info("RAG增强工作流管理器资源清理完成")
            
        except Exception as e:
            logger.error(f"清理RAG增强工作流管理器资源时发生错误: {e}")

"""
Author: zhuanglaihong
Date: 2024-09-24 16:35:00
LastEditTime: 2024-09-24 16:35:00
LastEditors: zhuanglaihong
Description: Global parameter configuration for HydroAgent system
FilePath: \HydroAgent\config.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

# ============================================================================
# HydroAgent 全局配置参数
#
# 此文件包含 HydroAgent 系统的所有可调整参数。
# 用户可以修改这些值而无需触及核心代码文件。
# ============================================================================

# ============================================================================
# RAG 系统参数
# ============================================================================

# 文档处理
RAG_CHUNK_SIZE = 1000                    # 文档分割的文本块大小
RAG_CHUNK_OVERLAP = 200                  # 文本块之间的重叠
RAG_MAX_CHUNK_SIZE = 2000               # 最大文本块大小
RAG_SUPPORTED_EXTENSIONS = [             # 支持的文件扩展名
    ".txt", ".md", ".markdown", ".rst",
    ".pdf", ".docx", ".doc", ".py",
    ".yaml", ".yml", ".json"
]

# 查询和检索
RAG_TOP_K = 5                           # 默认返回结果数量
RAG_SCORE_THRESHOLD = 0.7               # 最小相似度分数阈值
RAG_RERANK_ENABLED = True               # 启用结果重排序
RAG_QUERY_EXPANSION = True              # 启用查询扩展

# 重排序权重
RAG_SEMANTIC_WEIGHT = 0.6               # 语义相似性权重
RAG_DIVERSITY_WEIGHT = 0.3              # 结果多样性权重
RAG_RECENCY_WEIGHT = 0.1                # 内容时效性权重

# 向量数据库（FAISS配置）
VECTOR_DB_TYPE = "faiss"                 # 向量数据库类型: faiss, chroma
VECTOR_DB_COLLECTION_NAME = "hydro_knowledge"
VECTOR_DB_DISTANCE_FUNCTION = "cosine"   # 距离函数: cosine, l2, ip

# FAISS特定配置
FAISS_INDEX_TYPE = "Flat"               # FAISS索引类型: Flat, IVF, HNSW
FAISS_IVF_NLIST = 100                   # IVF索引的聚类数量
FAISS_HNSW_M = 16                       # HNSW图的连接数
FAISS_HNSW_EF_SEARCH = 64               # HNSW搜索时的候选数量
FAISS_ENABLE_GPU = False                # 是否启用GPU加速（需要faiss-gpu）

# 向量库索引文件
VECTOR_INDEX_FILE = "faiss_index.index" # FAISS索引文件名
VECTOR_METADATA_FILE = "metadata.json"  # 元数据文件名

# ============================================================================
# LLM 模型参数
# ============================================================================

# ============================
# 推理模型配置（Builder阶段使用）
# ============================
# 用于工作流规划、意图识别等推理任务

# API优先配置
REASONING_USE_API_FIRST = True          # 优先使用 API 推理模型
REASONING_API_MODEL = "qwen3-max"      # API 推理模型名称
REASONING_API_TIMEOUT = 30              # API 调用超时时间（秒）
REASONING_API_MAX_RETRIES = 2           # API 调用最大重试次数

# 本地降级配置
REASONING_FALLBACK_MODEL = "qwen3:8b"   # 降级使用的本地推理模型
REASONING_FALLBACK_TIMEOUT = 60         # 本地模型调用超时时间（秒）

# 推理参数
REASONING_TEMPERATURE = 0.1             # 推理任务的文本生成温度
REASONING_MAX_TOKENS = 4000             # 推理响应最大令牌数
REASONING_TOP_P = 0.95                  # Top-p 采样参数

# ============================
# 代码生成模型配置（Executor阶段使用）
# ============================
# 用于代码生成、工具调用等执行任务

# API优先配置
CODER_USE_API_FIRST = True              # 优先使用 API 代码模型
CODER_API_MODEL = "qwen3-coder-plus"    # API 代码生成模型名称
CODER_API_TIMEOUT = 45                  # API 调用超时时间（秒）
CODER_API_MAX_RETRIES = 2               # API 调用最大重试次数

# 本地降级配置
CODER_FALLBACK_MODEL = "deepseek-coder:6.7b"  # 降级使用的本地代码模型
CODER_FALLBACK_TIMEOUT = 90             # 本地代码模型调用超时时间（秒）

# 代码生成参数
CODER_TEMPERATURE = 0.1                 # 代码生成的温度参数
CODER_MAX_TOKENS = 6000                 # 代码生成响应最大令牌数
CODER_TOP_P = 0.95                      # Top-p 采样参数

# ============================
# 嵌入模型配置（RAG系统使用）
# ============================
# 用于文档向量化、语义检索等

# API优先配置
EMBEDDING_USE_API_FIRST = True          # 优先使用 API 嵌入模型
EMBEDDING_API_MODEL = "text-embedding-v3"    # API 嵌入模型名称
EMBEDDING_API_TIMEOUT = 30              # API 调用超时时间（秒）
EMBEDDING_API_MAX_RETRIES = 2           # API 调用最大重试次数

# 本地降级配置
EMBEDDING_FALLBACK_MODEL = "bge-large:335m"  # 本地嵌入模型降级
EMBEDDING_FALLBACK_TIMEOUT = 60         # 本地嵌入模型超时时间（秒）
EMBEDDING_AUTO_FALLBACK = True          # 自动切换到本地模型
EMBEDDING_TOTAL_TIMEOUT = 90            # 总超时时间（API + 本地）

# 嵌入参数
EMBEDDING_DIMENSION = 1536              # 预期嵌入维度
EMBEDDING_DEVICE = "cpu"                # 本地嵌入设备

# 重排序配置
RERANK_ENABLED = True                   # 启用重排序
RERANK_MODEL_TYPE = "cross-encoder"     # 重排序模型类型
RERANK_TOP_K_CANDIDATES = 20            # 重排序候选数量
RERANK_FINAL_K = 5                      # 重排序后最终返回数量

# ============================
# 兼容性配置（向后兼容）
# ============================
# 保持旧的配置项以确保现有代码不受影响

LLM_USE_API_FIRST = REASONING_USE_API_FIRST         # 向后兼容
LLM_API_MODEL_NAME = REASONING_API_MODEL            # 向后兼容
LLM_API_TIMEOUT = REASONING_API_TIMEOUT             # 向后兼容
LLM_API_MAX_RETRIES = REASONING_API_MAX_RETRIES     # 向后兼容
LLM_FALLBACK_MODEL = REASONING_FALLBACK_MODEL       # 向后兼容
LLM_FALLBACK_TIMEOUT = REASONING_FALLBACK_TIMEOUT   # 向后兼容
LLM_MODEL_NAME = REASONING_FALLBACK_MODEL           # 向后兼容
LLM_TEMPERATURE = REASONING_TEMPERATURE             # 向后兼容
LLM_MAX_TOKENS = REASONING_MAX_TOKENS               # 向后兼容
LLM_TOP_P = REASONING_TOP_P                         # 向后兼容

# 嵌入模型向后兼容
EMBEDDING_MODEL_API = EMBEDDING_API_MODEL           # 向后兼容
EMBEDDING_MODEL_LOCAL = EMBEDDING_FALLBACK_MODEL    # 向后兼容

# ============================================================================
# 构建器参数（工作流规划系统）
# ============================================================================

# 思维链（CoT）推理
COT_MAX_ITERATIONS = 5                  # CoT 推理的最大迭代次数
COT_TEMPERATURE = 0.2                   # CoT 推理温度
COT_KNOWLEDGE_CHUNKS = 5                # CoT 的知识块数量

# 工作流构建器配置
BUILDER_MAX_TASKS = 10                  # 工作流中的最大任务数
BUILDER_TIMEOUT = 120                   # 构建工作流的超时时间（秒）
BUILDER_RETRY_ATTEMPTS = 2              # 构建的重试尝试次数

# 执行模式分析
MODE_COMPLEXITY_THRESHOLD_LOW = 0.3     # 线性模式的低复杂度阈值
MODE_COMPLEXITY_THRESHOLD_HIGH = 0.7    # 反应模式的高复杂度阈值
MODE_CONFIDENCE_THRESHOLD = 0.6         # 模式推荐的最小置信度

# 工作流验证
VALIDATE_WORKFLOW_STRUCTURE = True      # 启用工作流结构验证
VALIDATE_TOOL_AVAILABILITY = True      # 启用工具可用性验证
VALIDATE_DEPENDENCY_CYCLES = True      # 启用循环依赖检测

# 构建器性能
BUILDER_CACHE_ENABLED = True            # 启用构建器结果缓存
BUILDER_CACHE_TTL = 1800               # 缓存生存时间（秒，30分钟）
BUILDER_STATS_ENABLED = True           # 启用构建器统计收集

# ============================================================================
# 执行器系统参数（Executor）
# ============================================================================

# 执行器主配置
EXECUTOR_MAX_CONCURRENT_TASKS = 4        # 最大并发任务数
EXECUTOR_DEFAULT_TIMEOUT = 300           # 默认超时时间（秒）
EXECUTOR_ENABLE_VISUALIZATION = True     # 启用结果可视化

# 工作流执行参数
WORKFLOW_MAX_STEPS = 10                 # 工作流中的最大步骤数
WORKFLOW_TIMEOUT = 300                  # 每个工作流的超时时间（秒）
WORKFLOW_RETRY_ATTEMPTS = 3             # 重试尝试次数

# 简单任务配置
SIMPLE_TASK_DEFAULT_TIMEOUT = 300       # 简单任务默认超时（秒）
SIMPLE_TASK_MAX_RETRIES = 2             # 简单任务最大重试次数
SIMPLE_TASK_CACHE_ENABLED = True        # 启用简单任务缓存

# 复杂任务配置
COMPLEX_TASK_DEFAULT_TIMEOUT = 1800     # 复杂任务默认超时（秒）
COMPLEX_TASK_MAX_ITERATIONS = 5         # 复杂任务最大迭代次数
COMPLEX_TASK_MIN_CONFIDENCE = 0.7       # 解决方案最小置信度
COMPLEX_TASK_ENABLE_RAG = True          # 启用RAG知识增强

# React模式配置
REACT_MAX_ITERATIONS = 3                # React模式最大迭代次数
REACT_CONVERGENCE_THRESHOLD = 0.01      # 收敛判断阈值
REACT_TARGET_PATIENCE = 2               # 目标等待轮次
REACT_ENABLE_ADAPTIVE = True            # 启用自适应调整

# ============================================================================
# 模型率定参数
# ============================================================================

# 优化设置
CALIB_MAX_ITERATIONS = 100              # 最大优化迭代次数
CALIB_TOLERANCE = 1e-6                  # 收敛容差
CALIB_POPULATION_SIZE = 50              # 遗传算法的种群大小

# 目标函数
CALIB_PRIMARY_METRIC = "nse"            # 主要率定指标（nse、kge 等）
CALIB_SECONDARY_METRICS = ["r2", "rmse", "mae"]  # 要跟踪的额外指标

# 交叉验证
CALIB_CV_FOLDS = 5                      # 交叉验证折数
CALIB_VALIDATION_SPLIT = 0.3            # 用于验证的数据比例

# ============================================================================
# 数据处理参数
# ============================================================================

# 时间序列处理
TS_MIN_YEARS = 3                        # 所需的最少年数据
TS_MAX_MISSING_RATIO = 0.1              # 允许的最大缺失数据比例
TS_INTERPOLATION_METHOD = "linear"      # 缺失数据的插值方法

# 质量控制
QC_MIN_FLOW = 0.001                     # 最小有效流量值（m³/s）
QC_MAX_FLOW_RATIO = 100                 # 时间步之间的最大流量变化比例
QC_OUTLIER_THRESHOLD = 3.0              # 异常值检测的标准差

# ============================================================================
# 日志和监控
# ============================================================================

# 日志配置
LOG_LEVEL = "INFO"                      # 日志级别（DEBUG、INFO、WARNING、ERROR）
LOG_MAX_FILE_SIZE = 10 * 1024 * 1024   # 最大日志文件大小（10MB）
LOG_BACKUP_COUNT = 5                    # 保留的备份日志文件数量
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# 性能监控
MONITOR_ENABLED = True                  # 启用性能监控
MONITOR_INTERVAL = 60                   # 监控间隔（秒）
MONITOR_METRICS = ["cpu", "memory", "disk"]  # 要监控的指标

# ============================================================================
# API 和网络配置
# ============================================================================

# API 设置
API_TIMEOUT = 30                        # API 请求超时时间（秒）
API_MAX_RETRIES = 3                     # 最大 API 重试次数
API_RETRY_DELAY = 1.0                   # 初始重试延迟（秒）
API_BACKOFF_FACTOR = 2.0                # 指数退避乘数

# 限率
API_RATE_LIMIT = 100                    # 每分钟 API 调用数
API_BURST_LIMIT = 20                    # 最大突发 API 调用数

# ============================================================================
# 缓存配置
# ============================================================================

# 缓存设置
CACHE_ENABLED = True                    # 启用缓存
CACHE_TTL = 3600                        # 缓存生存时间（秒）
CACHE_MAX_SIZE = 1000                   # 最大缓存项目数
CACHE_CLEANUP_INTERVAL = 600            # 缓存清理间隔（秒）

# 工具系统缓存
TOOL_CACHE_ENABLED = True               # 启用工具结果缓存
TOOL_CACHE_TTL = 1800                   # 工具缓存时间（秒）
LLM_RESPONSE_CACHE_SIZE = 100           # LLM响应缓存大小

# ============================================================================
# 开发和测试
# ============================================================================

# 开发设置
DEBUG_MODE = False                      # 启用调试模式
VERBOSE_LOGGING = False                 # 启用详细日志
PROFILE_PERFORMANCE = False             # 启用性能分析

# 测试配置
TEST_DATA_PATH = "test/data"            # 测试数据路径
TEST_TIMEOUT = 60                       # 测试超时时间（秒）
TEST_PARALLEL = True                    # 启用并行测试

# 模拟设置
MOCK_APIS = False                       # 使用模拟API进行测试
MOCK_DELAY = 0.1                        # 模拟 API 响应延迟

# ============================================================================
# 资源限制
# ============================================================================

# 内存管理
MAX_MEMORY_USAGE = 8 * 1024 * 1024 * 1024  # 最大内存使用量（8GB）
MAX_CHUNK_MEMORY = 500 * 1024 * 1024       # 每个块的最大内存（500MB）
GARBAGE_COLLECT_INTERVAL = 300              # 垃圾收集间隔

# 磁盘使用
MAX_DISK_USAGE = 50 * 1024 * 1024 * 1024   # 最大磁盘使用量（50GB）
TEMP_FILE_CLEANUP = True                    # 启用临时文件清理
TEMP_FILE_MAX_AGE = 86400                   # 临时文件最大年龄（24小时）

# 处理限制
MAX_CONCURRENT_TASKS = 4                # 最大并发处理任务数
MAX_FILE_SIZE = 100 * 1024 * 1024      # 处理的最大文件大小（100MB）
MAX_DOCUMENTS_BATCH = 100               # 每批次的最大文档数

# 执行器资源限制
EXECUTOR_MAX_MEMORY_MB = 4096           # 执行器最大内存（MB）
EXECUTOR_MAX_CPU_CORES = 2              # 执行器最大CPU核数
EXECUTOR_MAX_EXECUTION_TIME = 3600      # 最大执行时间（秒）

# ============================================================================
# 功能开关
# ============================================================================

# 系统功能
ENABLE_RAG = True                       # 启用 RAG 功能
ENABLE_MCP = True                       # 启用 MCP 集成
ENABLE_WORKFLOW = True                  # 启用工作流执行
ENABLE_VISUALIZATION = True             # 启用结果可视化

# 实验性功能
EXPERIMENTAL_MULTIMODAL = False         # 启用多模态处理
EXPERIMENTAL_DISTRIBUTED = False       # 启用分布式处理
EXPERIMENTAL_GPU_ACCELERATION = False  # 启用 GPU 加速

# ============================================================================
# 模型特定参数
# ============================================================================

# GR4J 模型
GR4J_PARAM_BOUNDS = {
    "X1": [1.0, 3000.0],        # 生产库容量
    "X2": [-30.0, 30.0],        # 地下水交换系数
    "X3": [1.0, 500.0],         # 汇流库容量
    "X4": [0.5, 10.0]           # 单位线时间常数
}

# XAJ 模型
XAJ_PARAM_BOUNDS = {
    "K": [0.1, 1.5],            # 蒸发系数
    "B": [0.1, 0.5],            # 张力水容量分布
    "IM": [0.0, 0.05],          # 不透水面积比
    "WM": [50.0, 500.0],        # 张力水库容量
    "WUM": [5.0, 50.0],         # 上层容量
    "WLM": [10.0, 100.0],       # 下层容量
    "C": [0.1, 0.3],            # 深层渗透系数
    "SM": [10.0, 100.0],        # 自由水库容量
    "EX": [1.0, 2.0],           # 自由水库分布
    "KI": [0.0, 0.7],           # 壤中流出流系数
    "KG": [0.0, 0.7],           # 地下水出流系数
    "A": [0.0, 1.0],            # 退水常数
    "THETA": [0.0, 1.0],        # 退水常数
    "CI": [0.5, 0.95],          # 滞后时间
    "CG": [0.8, 0.998]          # 滞后时间
}

# ============================================================================
# 用户自定义部分
# ============================================================================

# 用户可以通过取消注释和修改来覆盖上述任何参数：

# 覆盖示例：
# RAG_TOP_K = 10                        # 增加默认结果数
# LLM_TEMPERATURE = 0.3                 # 更创意的响应
# LOG_LEVEL = "DEBUG"                   # 更详细的日志

# 可以在此处添加自定义参数：
# CUSTOM_PARAMETER = "custom_value"
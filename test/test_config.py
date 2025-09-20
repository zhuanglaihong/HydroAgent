"""
集成测试配置文件
定义测试参数和设置
"""

from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 测试配置
TEST_CONFIG = {
    # 用户查询测试用例
    "test_queries": [
        {
            "id": "complete_workflow",
            "query": "整理数据camels_11532500流域，用其率定GR4J模型，并评估模型",
            "description": "完整建模流程：数据预处理 -> 模型率定 -> 模型评估",
            "expected_tools": ["prepare_data", "calibrate_model", "evaluate_model"],
            "expected_tasks": 3
        },
        {
            "id": "data_preprocessing",
            "query": "将camels_11532500流域的CSV数据转换为NetCDF格式",
            "description": "数据预处理",
            "expected_tools": ["prepare_data"],
            "expected_tasks": 1
        },
        {
            "id": "model_calibration",
            "query": "使用SCE-UA算法率定GR4J模型，数据集为basin_11532500",
            "description": "模型率定",
            "expected_tools": ["calibrate_model"],
            "expected_tasks": 1
        },
        {
            "id": "model_evaluation",
            "query": "评估GR4J模型性能，计算NSE和RMSE指标",
            "description": "模型评估",
            "expected_tools": ["evaluate_model"],
            "expected_tasks": 1
        }
    ],
    
    # Ollama配置
    "ollama": {
        "chat_model": "qwen3:8b",
        "embedding_model": "bge-large:335m",
        "base_url": "http://localhost:11434"
    },
    
    # RAG配置
    "rag": {
        "vector_store_path": PROJECT_ROOT / "documents" / "vector_db",
        "retrieval_k": 8,
        "score_threshold": 0.3
    },
    
    # 工作流生成配置
    "workflow": {
        "llm_model": "qwen3:8b",
        "enable_validation": True,
        "enable_feedback_learning": False,
        "reasoning_timeout": 120,
        "assembly_timeout": 60
    },
    
    # 测试数据配置
    "test_data": {
        "data_dir": PROJECT_ROOT / "data" / "camels_11532500",
        "required_files": [
            "basin_11532500.csv",
            "basin_attributes.csv"
        ],
        "optional_files": [
            "basin_11532500_monthly.csv",
            "basin_11532500_yearly.csv",
            "attributes.nc",
            "timeseries.nc"
        ]
    },
    
    # MCP工具配置
    "mcp_tools": {
        "available_tools": [
            "get_model_params",
            "prepare_data", 
            "calibrate_model",
            "evaluate_model"
        ],
        "default_parameters": {
            "prepare_data": {
                "target_data_scale": "D"
            },
            "calibrate_model": {
                "data_type": "owndata",
                "exp_name": "integration_test",
                "basin_ids": ["11532500"],
                "calibrate_period": ["2013-01-01", "2018-12-31"],
                "test_period": ["2019-01-01", "2023-12-31"],
                "warmup": 720,
                "cv_fold": 1
            },
            "evaluate_model": {
                "exp_name": "integration_test",
                "model_name": "gr4j",
                "cv_fold": 1
            }
        }
    },
    
    # 测试超时配置
    "timeouts": {
        "component_check": 30,      # 组件检查超时（秒）
        "knowledge_retrieval": 60,  # 知识检索超时（秒）
        "workflow_generation": 180, # 工作流生成超时（秒）
        "tool_execution": 300,      # 工具执行超时（秒）
        "total_test": 600          # 总测试超时（秒）
    },
    
    # 日志配置
    "logging": {
        "level": "INFO",
        "log_file": PROJECT_ROOT / "test" / "integration_test.log",
        "results_file": PROJECT_ROOT / "test" / "integration_test_results.json"
    }
}

# 验证函数
def validate_config():
    """验证配置有效性"""
    errors = []
    
    # 检查必要的路径
    if not PROJECT_ROOT.exists():
        errors.append(f"项目根目录不存在: {PROJECT_ROOT}")
    
    # 检查数据目录
    data_dir = TEST_CONFIG["test_data"]["data_dir"]
    if not data_dir.exists():
        errors.append(f"测试数据目录不存在: {data_dir}")
    
    # 检查向量数据库路径
    vector_db_path = TEST_CONFIG["rag"]["vector_store_path"]
    if not vector_db_path.exists():
        errors.append(f"向量数据库目录不存在: {vector_db_path}")
    
    return errors

if __name__ == "__main__":
    # 验证配置
    errors = validate_config()
    if errors:
        print("配置验证失败:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("配置验证通过")
        print(f"项目根目录: {PROJECT_ROOT}")
        print(f"测试用例数量: {len(TEST_CONFIG['test_queries'])}")
        print(f"可用工具: {', '.join(TEST_CONFIG['mcp_tools']['available_tools'])}")

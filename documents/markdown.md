# 模板类条目（供LLM识别任务模式）

%%%【模板1】数据准备模板

[问题模式] 准备[流域]流域数据

[MCP工具] prepare_data

[参数模式] {
data_path: [数据目录路径],
target_data_scale: [数据时间尺度，默认为日尺度("D")，可选"M"(月尺度)或"Y"(年尺度)]
}

[任务类型] simple

[计划映射] {
"id": "task_prepare_data",
"type": "simple",
"description": "$准备流域数据",
"mcp_tool": "prepare_data",
"params": {
"data_path": "str = "D:\Project\MCP\hydromodel\data\camels_11532500"",
"target_data_scale": str = "D"
}

%%%【模板2】模型率定模板

[问题模式] 率定[模型类型]模型[参数列表]

[MCP工具] calibrate_model

[参数模式] {
data_type: 数据类型，如 'camels' 或 'owndata'
data_dir: 数据目录
result_dir: 结果保存目录
exp_name: 实验名称
model: 模型配置字典
basin_ids: 流域ID列表
periods: 整个时间段 [start_date, end_date]
calibrate_period: 率定时间段 [start_date, end_date]
test_period: 测试时间段 [start_date, end_date]
warmup: 预热期长度，默认720
cv_fold: 交叉验证折数，默认1
algorithm: 优化算法配置
loss: 损失函数配置
param_range_file: 参数范围配置文件路径
}

[任务类型] simple

[计划映射] {
"id": "task_calibrate",
"type": "simple",
"description": "$模型参数率定,返回率定结果",
"mcp_tool": "calibrate_model",
"params": {
data_type: str = "owndata",
data_dir: str = "D:\\Project\\MCP\\hydromodel\\data\\camels_11532500",
result_dir: str = None,
exp_name: str = "exp_11532500",
model: dict = {
"name": "gr4j",
"source_type": "sources",
"source_book": "HF",
"kernel_size": 15,
"time_interval_hours": 24,
},
basin_ids: list = ["11532500"],
periods: list = ["2000-01-01", "2023-12-31"],
calibrate_period: list = ["2000-01-01", "2018-12-31"],
test_period: list = ["2019-01-01", "2023-12-31"],
warmup: int = 720,
cv_fold: int = 1,
algorithm: dict = {
"name": "SCE_UA",
"random_seed": 1234,
"rep": 100,
"ngs": 30,
"kstop": 5,
"peps": 0.05,
"pcento": 0.05,
},
loss: dict = {
"type": "time_series",
"obj_func": "RMSE",
"events": None,
},
param_range_file: str = "D:\\Project\\MCP\\hydromodel\\hydromodel\\models\\param.yaml",
},
"dependencies": ["task_prepare_data"]
}

%%%【模板3】评估模板

[问题模式] 评估[模型ID]模型

[MCP工具] evaluate_model

[参数模式] {
result_dir: 率定结果保存目录,和calibrate_model函数返回结果一致
exp_name: 实验名称,默认"exp_11532500"
cv_fold: 交叉验证折数,默认1
train_and_test_data:若为None,则自动从result_dir/config.yaml读取参数并生成。
model: 模型配置字典（可选）
param_range_file: 参数范围配置文件路径（可选）
}

[任务类型] simple

[计划映射] {
"id": "task_evaluate",
"type": "simple",
"description": "模型性能评估",
"mcp_tool": "evaluate_model",
"params": {
result_dir: str,
exp_name: str = "exp_11532500",
cv_fold: int = 1,
train_and_test_data=None,
model: dict = None,
param_range_file: str = None,
},
"dependencies": ["task_calibrate"]
}

# 完整工作流示例（供LLM参考）

%%%【完整示例】模型率定工作流
[用户问题] 率定XXX模型
[生成计划] {
"plan*id": "plan*$timestamp",
"objective": "率定XXX模型并且评估",
"data_type": "owndata",
"data_path": "path/to/data/",
"model_name": "XXX",

"tasks": [
{
"id": "task1",
"type": "simple",
"description": "准备XXX流域数据",
"mcp_tool": "prepare_data",
"params": {
"data_path": "str = "D:\Project\MCP\hydromodel\data\camels_11532500"",
"target_data_scale": str = "D"
},
"dependencies": []
},
{
"id": "task2",
"type": "simple",
"description": "XXX模型的参数率定",
"mcp_tool": "calibrate_model",
"params": {
data_type: str = "owndata",
data_dir: str = "D:\\Project\\MCP\\hydromodel\\data\\camels_11532500",
result_dir: str = None,
exp_name: str = "exp_11532500",
model: dict = {
"name": "gr4j",
"source_type": "sources",
"source_book": "HF",
"kernel_size": 15,
"time_interval_hours": 24,
},
basin_ids: list = ["11532500"],
periods: list = ["2000-01-01", "2023-12-31"],
calibrate_period: list = ["2000-01-01", "2018-12-31"],
test_period: list = ["2019-01-01", "2023-12-31"],
warmup: int = 720,
cv_fold: int = 1,
algorithm: dict = {
"name": "SCE_UA",
"random_seed": 1234,
"rep": 100,
"ngs": 30,
"kstop": 5,
"peps": 0.05,
"pcento": 0.05,
},
loss: dict = {
"type": "time_series",
"obj_func": "RMSE",
"events": None,
},
param_range_file: str = "D:\\Project\\MCP\\hydromodel\\hydromodel\\models\\param.yaml",
},
"dependencies": ["task1"]
},
{
"id": "task3",
"type": "simple",
"description": "XXX模型率定结果评估",
"mcp_tool": "evaluate_model",
"params": {
result_dir: str,
exp_name: str = "exp_11532500",
cv_fold: int = 1,
train_and_test_data=None,
model: dict = None,
param_range_file: str = None,
},
"dependencies": ["task2"]
}
]
}

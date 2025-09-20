"""
HydroMCP工具字典
存放所有可用工具的名称、描述、参数定义等信息，供工作流生成器使用
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class ToolParameter:
    """工具参数定义"""

    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[str]] = None

    def to_schema(self) -> Dict[str, Any]:
        """转换为JSON Schema格式"""
        schema = {"type": self.type, "description": self.description}
        if self.enum:
            schema["enum"] = self.enum
        if self.default is not None:
            schema["default"] = self.default
        return schema


@dataclass
class ToolDefinition:
    """工具定义"""

    name: str
    description: str
    parameters: List[ToolParameter]
    category: str = "hydro_modeling"
    usage_examples: Optional[List[str]] = None

    def get_required_params(self) -> List[str]:
        """获取必需参数列表"""
        return [p.name for p in self.parameters if p.required]

    def get_parameter_schema(self) -> Dict[str, Any]:
        """获取参数的JSON Schema"""
        properties = {}
        for param in self.parameters:
            properties[param.name] = param.to_schema()

        return {
            "type": "object",
            "properties": properties,
            "required": self.get_required_params(),
        }


# 定义所有可用的工具
HYDRO_TOOLS = {
    "get_model_params": ToolDefinition(
        name="get_model_params",
        description="获取指定水文模型的参数信息，包括参数名称、取值范围和数量",
        parameters=[
            ToolParameter(
                name="model_name",
                type="string",
                description="模型名称，支持的模型包括gr4j、gr2m、gr3j、gr5j、gr6j、xaj、hymod",
                required=True,
                enum=["gr4j", "gr2m", "gr3j", "gr5j", "gr6j", "xaj", "hymod"],
            )
        ],
        category="model_info",
        usage_examples=[
            "获取GR4J模型的参数信息",
            "查看新安江模型有哪些参数",
            "了解HYMOD模型的参数范围",
        ],
    ),
    "prepare_data": ToolDefinition(
        name="prepare_data",
        description="准备和预处理水文数据，将原始CSV格式转换为模型训练所需的NetCDF格式",
        parameters=[
            ToolParameter(
                name="data_dir",
                type="string",
                description="数据目录路径，应包含basin_attributes.csv和时间序列CSV文件",
                required=True,
            ),
            ToolParameter(
                name="target_data_scale",
                type="string",
                description="目标数据时间尺度：D(日尺度)、M(月尺度)、Y(年尺度)",
                required=False,
                default="D",
                enum=["D", "M", "Y"],
            ),
        ],
        category="data_processing",
        usage_examples=[
            "准备CAMELS数据集用于模型训练",
            "转换CSV数据为NetCDF格式",
            "预处理流域时间序列数据",
        ],
    ),
    "calibrate_model": ToolDefinition(
        name="calibrate_model",
        description="使用SCE-UA优化算法率定水文模型参数，寻找最佳参数组合",
        parameters=[
            ToolParameter(
                name="model_name",
                type="string",
                description="要率定的模型名称",
                required=True,
                enum=["gr4j", "gr2m", "gr3j", "gr5j", "gr6j", "xaj", "hymod"],
            ),
            ToolParameter(
                name="data_dir",
                type="string",
                description="包含预处理后数据文件的目录路径",
                required=True,
            ),
            ToolParameter(
                name="data_type",
                type="string",
                description="数据类型标识",
                required=False,
                default="owndata",
            ),
            ToolParameter(
                name="exp_name",
                type="string",
                description="实验名称，用于区分不同的率定实验",
                required=False,
                default="model_calibration",
            ),
            ToolParameter(
                name="result_dir",
                type="string",
                description="结果保存目录路径，不指定则使用默认目录",
                required=False,
            ),
            ToolParameter(
                name="basin_ids",
                type="array",
                description="要率定的流域ID列表",
                required=False,
                default=["11532500"],
            ),
            ToolParameter(
                name="calibrate_period",
                type="array",
                description="率定时间段，格式为[开始日期, 结束日期]",
                required=False,
                default=["2013-01-01", "2018-12-31"],
            ),
            ToolParameter(
                name="test_period",
                type="array",
                description="测试时间段，格式为[开始日期, 结束日期]",
                required=False,
                default=["2019-01-01", "2023-12-31"],
            ),
            ToolParameter(
                name="warmup",
                type="integer",
                description="模型预热期长度（天数），用于消除初始条件影响",
                required=False,
                default=720,
            ),
            ToolParameter(
                name="cv_fold",
                type="integer",
                description="交叉验证折数，1表示不进行交叉验证",
                required=False,
                default=1,
            ),
        ],
        category="model_calibration",
        usage_examples=[
            "率定GR4J模型参数",
            "使用SCE-UA算法优化新安江模型",
            "进行5折交叉验证的模型率定",
        ],
    ),
    "evaluate_model": ToolDefinition(
        name="evaluate_model",
        description="评估已率定模型的性能，计算R²、NSE、RMSE等统计指标",
        parameters=[
            ToolParameter(
                name="result_dir",
                type="string",
                description="率定结果保存目录路径",
                required=True,
            ),
            ToolParameter(
                name="exp_name",
                type="string",
                description="实验名称，应与率定时使用的名称一致",
                required=True,
                default="model_calibration",
            ),
            ToolParameter(
                name="model_name",
                type="string",
                description="模型名称",
                required=False,
                default="gr4j",
                enum=["gr4j", "gr2m", "gr3j", "gr5j", "gr6j", "xaj", "hymod"],
            ),
            ToolParameter(
                name="cv_fold",
                type="integer",
                description="交叉验证折数，应与率定时设置一致",
                required=False,
                default=1,
            ),
        ],
        category="model_evaluation",
        usage_examples=[
            "评估已率定模型的精度",
            "计算模型在训练期和测试期的R²指标",
            "生成模型性能评估报告",
        ],
    ),
}


def get_tool_by_name(tool_name: str) -> Optional[ToolDefinition]:
    """根据工具名称获取工具定义"""
    return HYDRO_TOOLS.get(tool_name)


def get_all_tool_names() -> List[str]:
    """获取所有可用工具名称列表"""
    return list(HYDRO_TOOLS.keys())


def get_tools_by_category(category: str) -> List[ToolDefinition]:
    """根据类别获取工具列表"""
    return [tool for tool in HYDRO_TOOLS.values() if tool.category == category]


def get_tool_categories() -> List[str]:
    """获取所有工具类别"""
    return list(set(tool.category for tool in HYDRO_TOOLS.values()))


def validate_tool_usage(tool_name: str, parameters: Dict[str, Any]) -> tuple[bool, str]:
    """
    验证工具使用是否正确

    Args:
        tool_name: 工具名称
        parameters: 工具参数

    Returns:
        (是否有效, 错误信息)
    """
    tool = get_tool_by_name(tool_name)
    if not tool:
        return (
            False,
            f"工具 '{tool_name}' 不存在。可用工具: {', '.join(get_all_tool_names())}",
        )

    # 检查必需参数
    required_params = tool.get_required_params()
    for param in required_params:
        if param not in parameters:
            return False, f"缺少必需参数: {param}"

    # 检查参数类型和枚举值
    for param_name, param_value in parameters.items():
        param_def = next((p for p in tool.parameters if p.name == param_name), None)
        if not param_def:
            return False, f"参数 '{param_name}' 不被工具 '{tool_name}' 支持"

        # 检查枚举值
        if param_def.enum and param_value not in param_def.enum:
            return (
                False,
                f"参数 '{param_name}' 的值 '{param_value}' 无效。可选值: {', '.join(param_def.enum)}",
            )

        # 简单类型检查
        if param_def.type == "string" and not isinstance(param_value, str):
            return False, f"参数 '{param_name}' 应为字符串类型"
        elif param_def.type == "integer" and not isinstance(param_value, int):
            return False, f"参数 '{param_name}' 应为整数类型"
        elif param_def.type == "array" and not isinstance(param_value, list):
            return False, f"参数 '{param_name}' 应为数组类型"

    return True, ""


def get_tool_summary() -> str:
    """获取工具摘要信息，用于RAG或LLM提示"""
    summary = "# HydroMCP工具集\n\n"
    summary += f"共提供 {len(HYDRO_TOOLS)} 个水文建模工具：\n\n"

    for category in get_tool_categories():
        tools_in_category = get_tools_by_category(category)
        summary += f"## {category.replace('_', ' ').title()}\n"

        for tool in tools_in_category:
            summary += f"- **{tool.name}**: {tool.description}\n"
            required_params = tool.get_required_params()
            if required_params:
                summary += f"  - 必需参数: {', '.join(required_params)}\n"
        summary += "\n"

    return summary


# 用于工作流生成的工具映射
WORKFLOW_TOOL_MAPPING = {
    # 数据相关操作
    "read_csv": "prepare_data",
    "load_data": "prepare_data",
    "data_preparation": "prepare_data",
    "process_data": "prepare_data",
    # 查看数据操作 - 注意：实际不存在这个工具，需要通过其他方式实现
    "view_data": None,  # 标记为无对应工具
    "show_data": None,
    "display_data": None,
    # 模型相关操作
    "model_info": "get_model_params",
    "get_params": "get_model_params",
    "model_params": "get_model_params",
    # 率定相关操作
    "calibrate": "calibrate_model",
    "optimize": "calibrate_model",
    "train_model": "calibrate_model",
    # 评估相关操作
    "evaluate": "evaluate_model",
    "assess": "evaluate_model",
    "validate": "evaluate_model",
}


def map_workflow_action_to_tool(action: str) -> Optional[str]:
    """
    将工作流中的动作映射到实际工具名称

    Args:
        action: 工作流中的动作名称

    Returns:
        对应的工具名称，如果无对应工具则返回None
    """
    # 直接匹配
    if action in HYDRO_TOOLS:
        return action

    # 映射匹配
    return WORKFLOW_TOOL_MAPPING.get(action)


def get_unsupported_actions() -> List[str]:
    """获取无对应工具支持的动作列表"""
    return [action for action, tool in WORKFLOW_TOOL_MAPPING.items() if tool is None]


if __name__ == "__main__":
    # 测试代码
    print(get_tool_summary())
    print("\n" + "=" * 50 + "\n")

    # 测试工具验证
    print("测试工具验证:")
    valid, msg = validate_tool_usage("get_model_params", {"model_name": "gr4j"})
    print(f"get_model_params(gr4j): {valid}, {msg}")

    valid, msg = validate_tool_usage(
        "get_model_params", {"model_name": "invalid_model"}
    )
    print(f"get_model_params(invalid): {valid}, {msg}")

    print(f"\n不支持的动作: {get_unsupported_actions()}")

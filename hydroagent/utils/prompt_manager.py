"""
Author: Claude & zhuanglaihong
Date: 2025-11-21 16:00:00
LastEditTime: 2025-11-21 16:00:00
LastEditors: Claude
Description: Dynamic Prompt Manager - Context-Aware Dynamic Prompting
             动态提示词管理器 - 上下文感知的动态提示词生成
FilePath: /HydroAgent/hydroagent/utils/prompt_manager.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

Inspired by OpenFOAMGPT 2.0's Prompt Generation Agent & Prompt Pool
"""

from typing import Dict, Any, Optional, List
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class AgentContext:
    """
    Agent运行时上下文。
    包含任务状态、历史反馈、资源路径等动态信息。
    """

    def __init__(
        self,
        agent_name: str,
        user_query: str = "",
        workspace_dir: Optional[Path] = None,
        **kwargs,
    ):
        """
        Initialize agent context.

        Args:
            agent_name: Agent名称
            user_query: 用户查询
            workspace_dir: 工作目录
            **kwargs: 其他上下文信息
        """
        self.agent_name = agent_name
        self.user_query = user_query
        self.workspace_dir = workspace_dir
        self.feedback: List[str] = []  # 历史反馈
        self.iteration: int = 0  # 当前迭代次数
        self.metadata: Dict[str, Any] = kwargs  # 额外元数据

    def add_feedback(self, feedback: str) -> None:
        """添加反馈信息"""
        self.feedback.append(feedback)
        logger.info(f"[{self.agent_name}] Feedback added: {feedback}")

    def increment_iteration(self) -> None:
        """增加迭代次数"""
        self.iteration += 1

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "agent_name": self.agent_name,
            "user_query": self.user_query,
            "workspace_dir": str(self.workspace_dir) if self.workspace_dir else None,
            "feedback": self.feedback,
            "iteration": self.iteration,
            "metadata": self.metadata,
        }


class PromptManager:
    """
    动态提示词管理器。

    实现三层提示词架构：
    1. Static Skeleton (静态骨架)
    2. Knowledge Injection (知识注入)
    3. Dynamic State (动态状态)

    Formula:
        Final Prompt = Static Template + Schema Constraints + Dynamic Context + Iterative Feedback
    """

    def __init__(self, resources_dir: Optional[Path] = None):
        """
        Initialize PromptManager.

        Args:
            resources_dir: 资源文件目录（存放Schema、API签名等）
        """
        if resources_dir is None:
            # 默认使用项目中的resources目录
            from pathlib import Path

            project_root = Path(__file__).parent.parent.parent
            resources_dir = project_root / "hydroagent" / "resources"

        self.resources_dir = resources_dir
        self.static_prompts: Dict[str, str] = {}  # Agent -> 静态prompt
        self.schemas: Dict[str, str] = {}  # 类型 -> Schema内容

        logger.info(f"PromptManager initialized with resources_dir: {resources_dir}")

    # =========================================================================
    # Level 1: Static Skeleton Management
    # =========================================================================

    def register_static_prompt(self, agent_name: str, prompt: str) -> None:
        """
        注册Agent的静态提示词骨架。

        Args:
            agent_name: Agent名称
            prompt: 静态提示词模板
        """
        self.static_prompts[agent_name] = prompt
        logger.debug(f"Registered static prompt for {agent_name}")

    def get_static_prompt(self, agent_name: str) -> str:
        """获取Agent的静态提示词"""
        return self.static_prompts.get(agent_name, "")

    # =========================================================================
    # Level 2: Knowledge Injection
    # =========================================================================

    def load_schema(self, schema_type: str, file_path: Optional[Path] = None) -> str:
        """
        加载Schema文件（API签名、配置结构等）。

        Args:
            schema_type: Schema类型 ('config', 'api', 'parameters')
            file_path: Schema文件路径（如果为None，使用默认路径）

        Returns:
            Schema内容
        """
        if file_path is None:
            # 默认路径
            file_path = self.resources_dir / f"{schema_type}_schema.txt"

        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                self.schemas[schema_type] = content
                logger.info(f"Loaded schema '{schema_type}' from {file_path}")
                return content
        else:
            logger.warning(f"Schema file not found: {file_path}")
            return ""

    def get_schema(self, schema_type: str) -> str:
        """获取已加载的Schema"""
        return self.schemas.get(schema_type, "")

    # =========================================================================
    # Level 3: Dynamic State Composition
    # =========================================================================

    def build_prompt(
        self,
        agent_name: str,
        context: AgentContext,
        include_schema: bool = True,
        include_feedback: bool = True,
        **kwargs,
    ) -> str:
        """
        动态构建完整的提示词。

        Args:
            agent_name: Agent名称
            context: Agent运行时上下文
            include_schema: 是否包含Schema
            include_feedback: 是否包含历史反馈
            **kwargs: 额外的模板变量

        Returns:
            完整的提示词

        Formula:
            Final Prompt = Static Template + Schema + Dynamic Context + Feedback
        """
        prompt_parts = []

        # ========= Part 1: Static Skeleton =========
        static_prompt = self.get_static_prompt(agent_name)
        if static_prompt:
            prompt_parts.append(static_prompt)

        # ========= Part 2: Knowledge Injection (Schema) =========
        if include_schema:
            schema_section = self._build_schema_section(agent_name)
            if schema_section:
                prompt_parts.append(schema_section)

        # ========= Part 3: Dynamic Context =========
        context_section = self._build_context_section(context)
        if context_section:
            prompt_parts.append(context_section)

        # ========= Part 4: Iterative Feedback =========
        if include_feedback and context.feedback:
            feedback_section = self._build_feedback_section(context)
            if feedback_section:
                prompt_parts.append(feedback_section)

        # 组合所有部分
        final_prompt = "\n\n".join(prompt_parts)

        # 应用额外的模板变量
        if kwargs:
            final_prompt = final_prompt.format(**kwargs)

        logger.debug(
            f"Built prompt for {agent_name} (length: {len(final_prompt)} chars)"
        )
        return final_prompt

    def _build_schema_section(self, agent_name: str) -> str:
        """构建Schema部分"""
        # 根据Agent类型选择相应的Schema
        schema_mapping = {
            "IntentAgent": "algorithm_params",  # IntentAgent需要算法参数Schema
            "ConfigAgent": "config",
            "RunnerAgent": "api",
            "DeveloperAgent": None,  # DeveloperAgent不需要Schema
        }

        schema_type = schema_mapping.get(agent_name)
        if not schema_type:
            return ""

        schema = self.get_schema(schema_type)
        if not schema:
            return ""

        return f"""**Schema Constraints**:
```
{schema}
```"""

    def _build_context_section(self, context: AgentContext) -> str:
        """构建动态上下文部分"""
        parts = []

        # 用户查询
        if context.user_query:
            parts.append(f"**User Query**: {context.user_query}")

        # 工作目录
        if context.workspace_dir:
            parts.append(f"**Workspace**: {context.workspace_dir}")

        # 迭代次数
        if context.iteration > 0:
            parts.append(f"**Iteration**: {context.iteration}")

        # 额外元数据
        if context.metadata:
            metadata_str = ", ".join(f"{k}={v}" for k, v in context.metadata.items())
            parts.append(f"**Context**: {metadata_str}")

        return "\n".join(parts) if parts else ""

    def _build_feedback_section(self, context: AgentContext) -> str:
        """构建反馈部分"""
        if not context.feedback:
            return ""

        feedback_str = "\n".join(f"  - {fb}" for fb in context.feedback)
        return f"""**Previous Feedback** (from iteration {len(context.feedback)}):
{feedback_str}

**Action Required**: Address the issues mentioned above and adjust your response accordingly."""

    # =========================================================================
    # Convenience Methods
    # =========================================================================

    def create_context(
        self,
        agent_name: str,
        user_query: str = "",
        workspace_dir: Optional[Path] = None,
        **kwargs,
    ) -> AgentContext:
        """
        便捷方法：创建AgentContext。

        Args:
            agent_name: Agent名称
            user_query: 用户查询
            workspace_dir: 工作目录
            **kwargs: 额外上下文

        Returns:
            AgentContext实例
        """
        return AgentContext(
            agent_name=agent_name,
            user_query=user_query,
            workspace_dir=workspace_dir,
            **kwargs,
        )


# =============================================================================
#   Code Generation Prompt Builder (v4.0)
#   从RunnerAgent提取的代码生成提示词构建工具
# =============================================================================


def _build_fdc_prompt(basin_id: str, params: Dict[str, Any]) -> str:
    """
    构建FDC代码生成提示词（带数据路径和示例代码）。
    Build FDC code generation prompt with data paths and examples.
    """
    # 获取previous_results，找到evaluation的输出目录
    previous_results = params.get("previous_results", [])
    data_dir = None
    nc_file = None

    # 查找evaluation或calibration的结果目录
    for result in previous_results:
        if result.get("success") and result.get("output_dir"):
            output_dir = Path(result["output_dir"])
            # 查找.nc文件
            nc_files = list(output_dir.glob("*.nc"))
            if nc_files:
                data_dir = str(output_dir)
                nc_file = nc_files[0].name
                break

    # 构建数据路径提示
    if data_dir and nc_file:
        data_path_hint = f"""
📂 **数据文件路径**：
- 评估结果目录：`{data_dir}`
- NetCDF文件：`{nc_file}`
- 完整路径：`{data_dir}/{nc_file}`

💡 **读取NetCDF文件示例**：
```python
import xarray as xr
from pathlib import Path

# 读取hydromodel生成的评估结果
nc_file = Path(r"{data_dir}") / "{nc_file}"
ds = xr.open_dataset(nc_file)

# 提取观测值和模拟值（测试期数据）
qobs = ds['qobs'].values.flatten()  # 观测流量
qsim = ds['qsim'].values.flatten()  # 模拟流量

# 移除NaN值
valid_mask = ~(np.isnan(qobs) | np.isnan(qsim))
qobs = qobs[valid_mask]
qsim = qsim[valid_mask]

# 确保为正值（用于对数坐标）
qobs = np.maximum(qobs, 0.001)
qsim = np.maximum(qsim, 0.001)
```
"""
    else:
        data_path_hint = """
⚠️ **未找到previous_results数据路径**

请生成通用的FDC绘制代码，假设数据文件为：
- `evaluation_results.nc` 或 `flow_data.csv`
- 包含 'qobs' 和 'qsim' 变量

建议添加文件检查逻辑，如果文件不存在则提示用户。
"""

    return f"""
请生成Python代码，绘制流域 {basin_id} 的流量历时曲线（Flow Duration Curve, FDC）。

{data_path_hint}

具体要求：
1. **读取流量数据**（观测值和模拟值）
   - 使用 xarray 读取 NetCDF 文件
   - 提取 qobs（观测流量）和 qsim（模拟流量）
   - 移除NaN值，确保数据为正值

2. **计算超越概率**（exceedance probability）
   - 对流量数据进行降序排序
   - 使用Weibull公式计算：P = m/(n+1) * 100

3. **绘制FDC曲线**
   - 使用对数坐标（plt.semilogy）
   - 同时绘制观测值和模拟值的FDC
   - X轴：超越概率(%)，Y轴：流量(m³/s)

4. **图表美化**
   - 添加图例、网格、标题
   - 配置中文字体（见下方）
   - 保存高分辨率图片（fdc_curve.png, 300 DPI）

5. **打印统计信息**
   - 数据点数量
   - 最大/最小流量
   - 中位数流量（P50）

🔧 **CRITICAL: matplotlib 中文显示配置**
必须在导入matplotlib后立即添加：
```python
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
```

📝 **代码要求**：
- 使用 type hints
- 添加详细注释
- 包含错误处理（文件不存在、数据格式错误）
- 打印进度信息
- 代码应该可以直接运行，无需修改路径
"""


def build_code_generation_prompt(analysis_type: str, params: Dict[str, Any]) -> str:
    """
    构建代码生成提示词（实验4：代码生成）。
    Build code generation prompt.

    Args:
        analysis_type: 分析类型 (runoff_coefficient, FDC, water_balance, seasonal_analysis)
        params: 参数字典 (包含 basin_id, model_name 等)

    Returns:
        完整的代码生成提示词
    """
    basin_id = params.get("basin_id", "N/A")
    model_name = params.get("model_name", "N/A")

    # 预定义的分析类型模板
    templates = {
        "runoff_coefficient": f"""
请生成Python代码，计算流域 {basin_id} 的径流系数。

具体要求：
1. 从率定结果目录读取流量和降水数据
2. 计算总径流量和总降水量
3. 径流系数 = 总径流量 / 总降水量
4. 打印结果，保存到CSV文件（runoff_coefficient.csv）
5. 如果可能，绘制时间序列对比图

数据源：
- 从 calibration_results.json 或 NetCDF 文件读取
- 或使用 hydrodataset 加载原始数据

代码要求：
- 使用 type hints
- 添加详细注释
- 包含错误处理
- 打印进度信息

🔧 **CRITICAL: 中文显示配置**
如果使用 matplotlib 绘图，必须在代码开头添加：
```python
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
```
""",
        "FDC": _build_fdc_prompt(basin_id, params),
        "water_balance": f"""
请生成Python代码，分析流域 {basin_id} 的水量平衡。

具体要求：
1. 读取降水、蒸散发、径流数据
2. 计算水量平衡：P = ET + Q + ΔS
3. 分析各项占比（降水、蒸散发、径流）
4. 绘制水量平衡饼图或柱状图
5. 计算和显示误差项
6. 保存结果到CSV和图片

🔧 **CRITICAL: matplotlib 中文显示配置**
必须在导入matplotlib后立即添加：
```python
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
```

代码要求：
- 使用 type hints
- 添加详细注释
- 包含错误处理
""",
        "seasonal_analysis": f"""
请生成Python代码，进行流域 {basin_id} 的季节性分析。

具体要求：
1. 读取多年流量数据
2. 按季节（春夏秋冬）分组统计
3. 计算每个季节的平均流量、最大流量、最小流量
4. 绘制季节性变化箱线图
5. 分析径流的季节性特征
6. 保存统计结果和图表

🔧 **CRITICAL: matplotlib 中文显示配置**
必须在导入matplotlib后立即添加：
```python
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
```

代码要求：
- 使用 type hints
- 添加详细注释
- 包含错误处理
""",
    }

    # 获取对应的模板，如果没有则使用通用模板
    if analysis_type in templates:
        return templates[analysis_type]
    else:
        # 通用模板
        return f"""
请生成Python代码，进行流域 {basin_id} 的 {analysis_type} 分析。

具体要求：
1. 从率定结果目录读取必要的数据
2. 进行 {analysis_type} 相关的计算和分析
3. 如果适用，生成可视化图表
4. 将结果保存到文件（CSV或图片）
5. 打印清晰的分析结果

数据源：
- 从 workspace_dir 中的 calibration_results.json 或 NetCDF 文件读取
- 使用 {model_name} 模型的输出结果

🔧 **CRITICAL: matplotlib 中文显示配置**
如果使用 matplotlib 绘图，必须在导入后立即添加：
```python
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
```

代码要求：
- 使用 type hints
- 添加详细注释
- 包含错误处理
- 打印进度信息
"""


# =============================================================================
# Example Usage
# =============================================================================


def example_usage():
    """示例：如何使用PromptManager"""
    from pathlib import Path

    # 1. 创建PromptManager
    pm = PromptManager()

    # 2. 注册静态提示词
    pm.register_static_prompt(
        "IntentAgent",
        """你是一个水文模型意图分析助手。
从用户查询中提取结构化信息。

**任务**: 分析水文模型查询，提取意图、模型、流域、时间、算法等信息

**意图分类**:
- calibration (中文: 率定/校准/参数率定)
- evaluation (中文: 评估/验证/测试)
- simulation (中文: 模拟/预测/计算)

**输出格式**: 必须返回有效JSON
""",
    )

    # 3. 创建上下文
    context = pm.create_context(
        agent_name="IntentAgent",
        user_query="率定GR4J模型，流域01013500，迭代500次",
        workspace_dir=Path("/workspace/session_001"),
    )

    # 4. 第一轮：初始请求
    prompt_v1 = pm.build_prompt("IntentAgent", context, include_schema=False)
    print("=== Prompt V1 (Initial) ===")
    print(prompt_v1)
    print()

    # 5. 添加反馈（模拟第一轮失败）
    context.add_feedback("解析失败：未能识别模型名称")
    context.increment_iteration()

    # 6. 第二轮：包含反馈
    prompt_v2 = pm.build_prompt("IntentAgent", context, include_schema=False)
    print("=== Prompt V2 (With Feedback) ===")
    print(prompt_v2)


if __name__ == "__main__":
    example_usage()

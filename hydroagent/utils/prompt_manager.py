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
        **kwargs
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
            "metadata": self.metadata
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
            with open(file_path, 'r', encoding='utf-8') as f:
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
        **kwargs
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

        logger.debug(f"Built prompt for {agent_name} (length: {len(final_prompt)} chars)")
        return final_prompt

    def _build_schema_section(self, agent_name: str) -> str:
        """构建Schema部分"""
        # 根据Agent类型选择相应的Schema
        schema_mapping = {
            "IntentAgent": "algorithm_params",  # IntentAgent需要算法参数Schema
            "ConfigAgent": "config",
            "RunnerAgent": "api",
            "DeveloperAgent": None  # DeveloperAgent不需要Schema
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
        **kwargs
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
            **kwargs
        )


# =============================================================================
# Example Usage
# =============================================================================

def example_usage():
    """示例：如何使用PromptManager"""
    from pathlib import Path

    # 1. 创建PromptManager
    pm = PromptManager()

    # 2. 注册静态提示词
    pm.register_static_prompt("IntentAgent", """你是一个水文模型意图分析助手。
从用户查询中提取结构化信息。

**任务**: 分析水文模型查询，提取意图、模型、流域、时间、算法等信息

**意图分类**:
- calibration (中文: 率定/校准/参数率定)
- evaluation (中文: 评估/验证/测试)
- simulation (中文: 模拟/预测/计算)

**输出格式**: 必须返回有效JSON
""")

    # 3. 创建上下文
    context = pm.create_context(
        agent_name="IntentAgent",
        user_query="率定GR4J模型，流域01013500，迭代500次",
        workspace_dir=Path("/workspace/session_001")
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

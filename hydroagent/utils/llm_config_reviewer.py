"""
Author: Claude
Date: 2025-12-01 11:55:00
LastEditTime: 2025-12-01 11:55:00
LastEditors: Claude
Description: LLM-based configuration reviewer for intelligent validation
             基于LLM的配置审查器，用于智能验证配置的合理性
FilePath: /HydroAgent/hydroagent/utils/llm_config_reviewer.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from typing import Dict, Any, Optional, Tuple
import json
import logging
from datetime import datetime

from ..core.llm_interface import LLMInterface

logger = logging.getLogger(__name__)


class LLMConfigReviewer:
    """
    LLM-based configuration reviewer.
    基于LLM的配置审查器。

    Purpose:
    - Use LLM to intelligently review hydromodel configurations
    - Detect unreasonable values, logic errors, and inconsistencies
    - Provide user-friendly error messages
    - Extensible: no need to hardcode every validation rule

    This replaces manual validation rules with intelligent LLM-based review.
    """

    def __init__(self, llm_interface: LLMInterface):
        """
        Initialize LLMConfigReviewer.

        Args:
            llm_interface: LLM API interface for review
        """
        self.llm = llm_interface

        # System prompt for config review
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """构建配置审查的系统提示词。"""
        current_year = datetime.now().year

        return f"""你是一个水文模型配置审查专家。你的任务是检查hydromodel配置的合理性。

**当前年份**: {current_year}

**需要检查的常见问题**:

1. **流域ID (basin_ids)**:
   - 应为8位数字格式（如 "01013500"）
   - CAMELS-US数据集范围：01000000 - 14500000
   - 99999999 等明显不合理的ID应报错

2. **算法参数 (algorithm_params)**:
   - 所有参数必须为正数（rep, ngs, kstop, generations 等）
   - 负数参数（如 rep=-100）是不合理的
   - 过大的值（如 rep=1000000）可能导致计算时间过长

3. **时间段 (train_period, test_period)**:
   - 格式：YYYY-MM-DD（如 "2000-01-01"）
   - 必须是历史时间，不能是未来（如 2050-2060 在 {current_year} 年是不合理的）
   - 开始时间必须早于结束时间
   - 训练时间段应早于测试时间段
   - CAMELS数据集通常覆盖 1980-2014 年

4. **模型名称 (model_name)**:
   - 有效值：xaj, xaj_mz, gr4j, gr5j, gr6j, gr1y, gr2m
   - 大小写不敏感

5. **逻辑一致性**:
   - 配置应与用户查询意图一致
   - 如果用户明确指定了某个值，配置中应体现

**输出格式**:
- 如果配置完全合理，返回: {{"valid": true}}
- 如果有问题，返回: {{"valid": false, "error": "友好的错误描述，告诉用户哪里不合理"}}

**错误描述要求**:
- 清晰指出具体的问题
- 解释为什么不合理
- 给出修改建议
- 使用友好的语气

只返回JSON格式，不要其他内容。"""

    def review_config(
        self, config: Dict[str, Any], user_query: str
    ) -> Tuple[bool, Optional[str]]:
        """
        使用LLM审查配置的合理性。

        Args:
            config: hydromodel配置字典
            user_query: 用户原始查询（用于上下文）

        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
                - is_valid: 配置是否合理
                - error_message: 如果不合理，返回错误信息；否则为None
        """
        # 跳过custom_analysis任务（不需要审查）
        task_metadata = config.get("task_metadata", {})
        if task_metadata.get("task_type") == "custom_analysis":
            logger.info("[LLMConfigReviewer] Custom analysis task, skipping review")
            return True, None

        # 构建审查提示
        user_prompt = self._build_review_prompt(config, user_query)

        try:
            # 调用LLM进行审查
            response = self.llm.generate_json(
                system_prompt=self.system_prompt,
                user_prompt=user_prompt,
                temperature=0.1,  # 低温度，确保一致性
            )

            logger.debug(f"[LLMConfigReviewer] LLM response: {response}")

            # 解析结果
            is_valid = response.get("valid", False)

            if is_valid:
                logger.info("[LLMConfigReviewer] Configuration review passed")
                return True, None
            else:
                error_message = response.get("error", "配置存在问题，但未提供详细信息")
                logger.warning(f"[LLMConfigReviewer] Configuration review failed: {error_message}")
                return False, error_message

        except Exception as e:
            logger.error(f"[LLMConfigReviewer] Review failed with exception: {str(e)}", exc_info=True)
            # 如果LLM审查失败，返回验证通过（避免阻塞正常流程）
            logger.warning("[LLMConfigReviewer] Falling back to 'valid' due to LLM error")
            return True, None

    def _build_review_prompt(self, config: Dict[str, Any], user_query: str) -> str:
        """
        构建配置审查的用户提示词。

        Args:
            config: 配置字典
            user_query: 用户查询

        Returns:
            审查提示词
        """
        # 提取关键信息用于审查
        config_summary = {
            "data_cfgs": config.get("data_cfgs", {}),
            "model_cfgs": config.get("model_cfgs", {}),
            "training_cfgs": config.get("training_cfgs", {}),
        }

        prompt = f"""请审查以下水文模型配置的合理性。

**用户查询**:
{user_query}

**生成的配置**:
```json
{json.dumps(config_summary, indent=2, ensure_ascii=False)}
```

请仔细检查配置中的所有参数，特别关注：
1. 流域ID是否在合理范围内
2. 算法参数是否为正数
3. 时间段是否为历史时间（不是未来）
4. 训练和测试时间段的逻辑顺序
5. 配置是否与用户查询一致

如果发现任何不合理之处，请详细说明问题并给出修改建议。

只返回JSON格式: {{"valid": true/false, "error": "..."}}
"""

        return prompt

    def quick_review(
        self, config: Dict[str, Any], user_query: str, max_attempts: int = 2
    ) -> Tuple[bool, Optional[str]]:
        """
        快速审查（带重试机制）。

        Args:
            config: 配置字典
            user_query: 用户查询
            max_attempts: 最大尝试次数

        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        for attempt in range(max_attempts):
            try:
                is_valid, error_message = self.review_config(config, user_query)
                return is_valid, error_message
            except Exception as e:
                logger.warning(
                    f"[LLMConfigReviewer] Attempt {attempt + 1}/{max_attempts} failed: {str(e)}"
                )
                if attempt == max_attempts - 1:
                    # 最后一次尝试仍然失败，返回验证通过
                    logger.error("[LLMConfigReviewer] All review attempts failed, fallback to valid")
                    return True, None

        return True, None


def create_reviewer(llm_interface: LLMInterface) -> LLMConfigReviewer:
    """
    便捷函数：创建配置审查器。

    Args:
        llm_interface: LLM接口

    Returns:
        LLMConfigReviewer实例
    """
    return LLMConfigReviewer(llm_interface)

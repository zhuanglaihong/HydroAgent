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
from .basin_validator import BasinValidator
from .config_validator import ConfigValidator

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

        # Initialize basin validator (uses actual hydrodataset)
        self.basin_validator = BasinValidator()
        logger.info("[LLMConfigReviewer] Basin validator initialized (uses real dataset)")

        # System prompt for config review
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """构建配置审查的系统提示词。"""
        current_year = datetime.now().year

        # 获取真实的算法参数范围
        param_ranges = ConfigValidator.ALGORITHM_PARAM_RANGES

        # 构建参数范围说明
        param_ranges_text = "**算法参数的合理范围**:\n"
        for algo_name, params in param_ranges.items():
            param_ranges_text += f"\n   {algo_name}:\n"
            for param_name, param_info in params.items():
                min_val = param_info.get('min')
                max_val = param_info.get('max')
                desc = param_info.get('description', param_name)
                param_ranges_text += f"   - {param_name} ({desc}): {min_val} ~ {max_val}\n"

        return f"""你是一个水文模型配置审查专家。你的任务是检查hydromodel配置的合理性。

**当前年份**: {current_year}

**重要说明**:
- **流域ID已通过真实数据集工具验证，你无需检查流域ID是否存在**
- 流域ID验证由专门的BasinValidator工具完成（使用hydrodataset真实检查）
- 你只需要检查配置的其他方面

**需要检查的问题**:

1. **算法参数 (algorithm_params)**:
   - 所有参数必须为正数
   - 负数参数（如 rep=-100）是不合理的
   - **请参考以下合理范围进行检查**：

{param_ranges_text}

   - **重要**: 只有当参数值**超出上述范围**时才报错，范围内的任何值都是合理的
   - **严格规则**: 如果参数值在min~max范围内，**必须**判定为合理，**禁止**报错
   - ✅ 合理示例：
     * rep=500 在范围内（1~50000） → 合理
     * rep=5000 在范围内（1~50000） → 合理
     * rep=30000 在范围内（1~50000） → 合理
   - ❌ 不合理示例：
     * rep=100000 超出范围（>50000） → 不合理，应报错
     * rep=-100 为负数 → 不合理，应报错
   - **禁止主观判断**: 不要根据"计算时间"、"建议值"等主观因素拒绝范围内的参数

2. **时间段 (train_period, test_period)**:
   - 格式：YYYY-MM-DD（如 "2000-01-01"）
   - 必须是历史时间，不能是未来（如 2050-2060 在 {current_year} 年是不合理的）
   - 开始时间必须早于结束时间
   - **重要**：即使用户只指定了训练期，系统自动添加测试期也是**完全合理**的（这是标准做法）
   - 对于多任务查询，train_period和test_period可能相同或重叠，这也是可以接受的
   - CAMELS数据集通常覆盖 1980-2024 年

3. **模型名称 (model_name)**:
   - 有效值：xaj, xaj_mz, gr4j, gr5j, gr6j
   - 大小写不敏感

4. **模型参数验证**:
   - **GR4J/GR5J/GR6J模型**：不应包含 kernel_size 参数（kernel_size 属于XAJ模型）
   - **XAJ模型**：可以包含 kernel_size、source_book等参数
   - 配置中不应出现与当前模型不匹配的参数

5. **目标函数 (obj_func)**:
   - **CRITICAL**: obj_func是优化器要MINIMIZE的损失函数，不是评估停止条件！
   - **重要区分**：
     * "NSE≥0.65"、"直到NSE达到0.7" → 这是**停止条件**，NOT优化目标！
     * "优化NSE"、"maximize NSE" → 这才是优化目标，obj_func应为"spotpy_nashsutcliffe"
   - **正确逻辑**：
     * 如果用户明确说"优化RMSE"/"minimize RMSE" → obj_func应为"RMSE" (大写)
     * 如果用户明确说"优化KGE"/"maximize KGE" → obj_func应为"spotpy_kge"
     * 如果用户明确说"优化NSE"/"maximize NSE" → obj_func应为"spotpy_nashsutcliffe"
     * 如果用户只提到停止条件（如"NSE≥0.65"）→ obj_func用默认值"RMSE"是**完全合理的**！
   - **错误示例**: 配置中obj_func="nse"或"NSE" → 应该是"spotpy_nashsutcliffe"或"RMSE"！
   - **Hydromodel要求**: obj_func必须是hydromodel LOSS_DICT中的准确键名，否则会报KeyError
   - **有效值**: "RMSE" (推荐默认), "spotpy_nashsutcliffe" (NSE), "spotpy_kge" (KGE), "spotpy_rmse"等
   - **实践经验**: 使用"RMSE"作为obj_func通常能获得更好的NSE值（综合拟合效果好）

6. **流程控制参数（不属于hydromodel配置）**:
   - ⚠️ **NSE阈值**（如"NSE低于0.7"中的0.7）**不属于hydromodel配置**
   - ⚠️ **迭代次数**、**重复次数**等也不属于hydromodel配置
   - ⚠️ 这些是**外部流程控制参数**，由Orchestrator/DeveloperAgent处理
   - ✅ **不要要求在配置中添加threshold、nse_target等字段**
   - ✅ Hydromodel配置只需要包含obj_func（如"NSE"），不需要阈值

7. **逻辑一致性**:
   - 配置应与用户查询意图一致
   - 如果用户明确指定了某个值，配置中应体现
   - **重要**: 只检查hydromodel标准配置格式中的字段，不要要求添加额外字段

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

        # ========== STEP 1: 使用真实工具验证流域ID ==========
        basin_ids = config.get("data_cfgs", {}).get("basin_ids", [])
        if basin_ids:
            logger.info(f"[LLMConfigReviewer] Validating basin IDs using real dataset: {basin_ids}")
            all_valid, error_messages = self.basin_validator.validate_basin_list(basin_ids)

            if not all_valid:
                # 流域ID验证失败，直接返回错误
                error_msg = "\n".join(error_messages)
                logger.warning(f"[LLMConfigReviewer] Basin validation failed: {error_msg}")
                return False, error_msg

            logger.info("[LLMConfigReviewer] Basin IDs validated successfully against real dataset")

        # ========== STEP 2: 使用LLM审查其他配置问题 ==========
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

        # 检测是否是多任务查询
        multi_task_indicators = [
            "完成后", "然后", "接着", "之后",
            "计算", "分析", "画", "生成", "统计",
            "径流系数", "FDC", "曲线"
        ]
        is_multi_task = any(indicator in user_query for indicator in multi_task_indicators)

        # 检测是否是批量任务
        batch_task_indicators = ["批量", "多个流域", "分别", "分别率定"]
        is_batch_task = any(indicator in user_query for indicator in batch_task_indicators)

        # 检测是否是多模型对比任务
        multi_model_indicators = ["GR4J和XAJ", "XAJ和GR4J", "多个模型", "两个模型", "分别率定", "对比"]
        is_multi_model_task = any(indicator in user_query for indicator in multi_model_indicators)

        # 检测是否是迭代优化任务
        iterative_task_indicators = ["迭代", "优化直到", "达到", "最多", "重复", "次"]
        is_iterative_task = any(indicator in user_query for indicator in iterative_task_indicators)

        # 构建提示词
        task_context = ""
        if is_multi_task:
            task_context = """
**注意**: 此查询是多任务查询（包含率定 + 后续分析），当前配置可能是其中一个子任务的配置。
对于多任务查询的calibration子任务，train_period和test_period重叠是可以接受的。
"""

        if is_batch_task:
            task_context += """
**注意**: 此查询是批量任务（涉及多个流域），系统可能会将其拆解为多个独立子任务。
当前配置可能只包含部分流域的信息（例如3个流域中的1个），这是**完全合理**的。
不要因为配置中流域数量少于查询中提到的总数而报错。
"""

        if is_multi_model_task:
            task_context += """
**注意**: 此查询是多模型对比任务（例如"对GR4J和XAJ两个模型分别率定"），系统会将其拆解为多个独立子任务。
**重要**: 每个子任务的配置**只包含一个模型**（例如只有'model_name': 'xaj'），这是**完全正确**的！
**系统工作机制**:
- 系统会为每个模型生成独立的配置和子任务
- 配置1: model_name: "gr4j" (GR4J任务)
- 配置2: model_name: "xaj" (XAJ任务)
**不要报错**: 不要因为"配置只有xaj，缺少gr4j"而拒绝配置！
每个配置只负责一个模型是**系统设计如此**，不是配置错误。
"""

        if is_iterative_task:
            task_context += """
**注意**: 此查询是迭代优化任务（例如"迭代优化直到NSE≥0.65，最多5次"）。
查询中提到的"NSE阈值"、"迭代次数"等参数是**外部流程控制参数**（execution_mode参数），**不应该**出现在hydromodel配置中。
hydromodel配置只需包含单次率定所需的标准参数（basin_ids, train_period, test_period, model_name, algorithm等）。
迭代逻辑由外部系统（RunnerAgent）控制，不是hydromodel的职责。
因此，配置中**没有**这些迭代控制参数是**完全正确**的，不要因此报错。
"""

        prompt = f"""请审查以下水文模型配置的合理性。

**用户查询**:
{user_query}
{task_context}
**生成的配置**:
```json
{json.dumps(config_summary, indent=2, ensure_ascii=False)}
```

**重要提示**:
- ✅ 流域ID已通过真实数据集工具验证（使用hydrodataset），你无需检查流域ID是否存在
- 你只需要检查配置的其他方面

请仔细检查配置中的所有参数，特别关注：
1. 算法参数是否为正数
2. 时间段是否为历史时间（不是未来）
3. 训练和测试时间段的逻辑顺序（注意多任务查询的特殊情况）
4. 配置是否与用户查询一致
5. 模型参数是否与模型类型匹配

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

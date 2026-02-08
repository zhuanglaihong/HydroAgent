"""
Author: HydroAgent Team
Date: 2025-01-25 11:30:00
LastEditTime: 2026-01-13 20:30:00
LastEditors: Claude Code (v6.1 Fix)
Description: Tool orchestrator for generating tool execution chains
    v6.1 Fix (2026-01-13): CustomAnalysisTool marked as optional for batch tasks
FilePath: /HydroAgent/hydroagent/agents/tool_orchestrator.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from typing import Dict, Any, List, Optional
from hydroagent.tools.registry import ToolRegistry
import logging

logger = logging.getLogger(__name__)


class ToolOrchestrator:
    """
    Tool orchestrator - generates tool execution chains based on task types.

    Phase 1: Rule-based orchestration
    Phase 3: LLM-assisted orchestration (optional)

    Supported task types:
    - standard_calibration: validate → calibrate → evaluate → visualize
    - evaluation: validate → evaluate → visualize
    - iterative_optimization: validate → iterative_calibration → visualize
    - extended_analysis: validate → calibrate → evaluate → custom_analysis
    """

    def __init__(self, registry: Optional[ToolRegistry] = None, llm_interface=None):
        """
        Initialize tool orchestrator.

        Args:
            registry: Tool registry (default: global registry)
            llm_interface: LLM interface for intelligent orchestration (optional)
        """
        from hydroagent.tools.registry import registry as global_registry
        self.registry = registry or global_registry
        self.llm_interface = llm_interface
        self.logger = logging.getLogger(self.__class__.__name__)

    def generate_tool_chain(
        self,
        task_type: str,
        intent_result: Dict[str, Any],
        use_llm: bool = False
    ) -> Dict[str, Any]:
        """
        Generate tool execution chain for a task.

        Args:
            task_type: Task type identifier
            intent_result: Intent recognition result
            use_llm: Whether to use LLM-assisted orchestration (Phase 3)

        Returns:
            Dict: Tool chain with execution mode, format:
                {
                    "tool_chain": [
                        {"tool": "tool_name", "inputs": {...}, "description": "..."},
                        ...
                    ],
                    "execution_mode": "simple" | "iterative" | "repeated",
                    "mode_params": {...}  # Parameters for execution mode
                }
        """
        self.logger.info(f"[ToolOrchestrator] Generating tool chain for task: {task_type}")

        if use_llm:
            if self.llm_interface is None:
                self.logger.warning("[ToolOrchestrator] LLM interface not available, falling back to rules")
                return self._rule_based_orchestration(task_type, intent_result)
            else:
                # Try LLM-based orchestration, fallback to rules on error
                try:
                    return self._llm_based_orchestration(task_type, intent_result)
                except Exception as e:
                    self.logger.error(f"[ToolOrchestrator] LLM orchestration failed: {e}, falling back to rules")
                    return self._rule_based_orchestration(task_type, intent_result)
        else:
            return self._rule_based_orchestration(task_type, intent_result)

    def _llm_based_orchestration(
        self,
        task_type: str,
        intent_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        LLM-based intelligent tool orchestration.
        让LLM根据用户查询和可用工具，灵活决定工具链。

        Args:
            task_type: Task type (reference only)
            intent_result: Intent recognition result

        Returns:
            Dict: Tool chain with execution mode
        """
        import json

        self.logger.info("[ToolOrchestrator] Using LLM-based orchestration")

        # 🔧 优化：只获取与任务相关的工具（减少token消耗）
        relevant_tools = self._get_relevant_tools(task_type, intent_result)

        # Build tool descriptions for LLM (only relevant tools)
        tool_descriptions = []
        for tool_name in relevant_tools:
            tool = self.registry.get_tool(tool_name)
            if tool and hasattr(tool, 'metadata') and tool.metadata:
                metadata = tool.metadata
                tool_descriptions.append({
                    "name": metadata.name,
                    "description": metadata.description,
                    "category": metadata.category.value if hasattr(metadata.category, 'value') else str(metadata.category),
                    "input_schema": metadata.input_schema,
                    "dependencies": metadata.dependencies
                })

        self.logger.info(f"[ToolOrchestrator] Selected {len(tool_descriptions)} relevant tools (from {len(self.registry.list_tools())} total)")

        # Extract key information from intent
        user_query = intent_result.get("original_query", "")
        model_name = intent_result.get("model_name", "")
        basin_id = intent_result.get("basin_id", "")
        time_period = intent_result.get("time_period", {})
        depends_on_previous = intent_result.get("depends_on_previous", False)

        # Build LLM prompt
        prompt = f"""你是一个水文建模工具编排专家。用户提出了一个水文建模任务，你需要选择合适的工具并确定执行顺序。

## 用户查询
{user_query}

## 任务信息
- 模型: {model_name}
- 流域: {basin_id}
- 时间段: {json.dumps(time_period, ensure_ascii=False)}
- 任务类型: {task_type}
- 依赖前置任务: {'是（前置任务已完成率定和评估）' if depends_on_previous else '否（独立任务）'}

## 可用工具
{json.dumps(tool_descriptions, indent=2, ensure_ascii=False)}

## 核心工具说明

### evaluate vs simulate 的关键区别
- **evaluate**: 评估模型性能，输出**性能指标**（NSE、RMSE、KGE等），用于验证模型效果
- **simulate**: 生成流量**预测序列**，输出模拟流量时间序列，用于分析、决策支持

### code_generation vs custom_analysis 的关键区别
- **code_generation**: 🔑 **生成可执行的Python脚本文件**，用于自定义分析任务
  - 适用场景：用户明确要求"生成代码"、"编写脚本"、"生成Python代码"、"写一个程序"
  - 输出：完整的.py文件，包含type hints、注释、错误处理
  - 典型任务：径流系数计算、FDC曲线绘制、自定义水文指标分析

- **custom_analysis**: 🔑 **LLM辅助的自定义分析任务**，分析特定水文特征或非标准指标
  - 适用场景：
    - 🎯 分析特定时期：洪峰、枯水期、汛期、丰水期等
    - 🎯 分析特定指标：洪峰误差、峰现时间偏差、水量平衡等
    - 🎯 统计分析：误差分布、相关性分析、趋势分析等
    - 🎯 条件筛选：筛选特定流量范围、特定月份、特定事件等
  - 关键识别词：**分析**、**统计**、**筛选**、**提取**、**计算**（非标准指标）
  - 输出：分析结果、统计报告、LLM解读
  - 典型任务：洪峰流量误差分析、枯水期精度评估、月尺度统计、事件提取

### 工具选择规则

#### 🔄 复合任务依赖规则（非常重要！）
**如果"依赖前置任务=是"**：
- ⚠️ **跳过前置工具**：不要再添加 validate_data、calibrate、evaluate
- ✅ **直接使用后续工具**：根据任务需求直接选择 visualize、code_generation 或 custom_analysis
- 💡 **原因**：前置任务已经完成了率定和评估，结果已保存，后续任务可以直接使用
- 📝 **示例**：
  - 前置任务："率定XAJ模型" → validate_data → calibrate → evaluate
  - 当前任务："绘制水文过程线" (依赖=是) → **只需** visualize

#### 🆕 独立任务规则（依赖=否）
1. **⚠️ CRITICAL - 所有率定任务的标准流程**: validate_data → calibrate → evaluate → visualize
   - **calibrate**: 在训练期优化参数（train period）
   - **evaluate**: 在测试期计算NSE等性能指标（test period）
   - ⚠️ **两者必不可少**！calibrate≠评估，必须用evaluate才能获得NSE
   - 适用于: standard_calibration, auto_iterative_calibration, iterative_optimization
   - **迭代模式**：auto_iterative_calibration在iterative执行模式下会循环执行calibrate→evaluate直到NSE达标

2. **率定后需要模拟流量序列**: validate_data → calibrate → simulate → visualize
   - 用于预测、预报、水文过程分析
   - simulate生成完整的流量时间序列

3. **既要指标又要序列**: validate_data → calibrate → evaluate → visualize
   - **注意**: evaluate已经包含模拟过程，不需要额外的simulate
   - 除非用户明确要求在不同时期进行模拟

4. **⭐ 率定后生成Python代码进行自定义分析**: validate_data → calibrate → evaluate → code_generation
   - 🔑 **关键识别词**：生成代码、编写脚本、生成Python、写程序、生成.py文件
   - ⚠️ **重要**: code_generation工具需要evaluate生成的NetCDF文件来获取流量/降水数据，因此必须先执行evaluate
   - 典型任务：径流系数计算、FDC曲线绘制

6. **⭐ 率定后进行自定义水文分析**: validate_data → calibrate → evaluate → custom_analysis
   - 🔑 **关键识别词**：分析洪峰、分析枯水期、统计误差、分析XX精度、提取事件、计算XX（非标准指标）
   - ⚠️ **重要**: custom_analysis工具也需要evaluate生成的NetCDF文件
   - 典型任务：洪峰流量误差分析、枯水期精度评估、峰现时间偏差、月尺度统计
   - **与evaluate的区别**: evaluate只输出标准指标（NSE、RMSE等），custom_analysis可以深入分析特定水文特征

### 关键注意事项
⚠️ **避免冗余**: 如果evaluate和simulate在同一时期（如都在test period），只需要evaluate即可
⚠️ **明确模拟意图**: 只有当用户明确要求"模拟未来"、"预测XX时期"、"生成流量序列"时，才使用simulate
⚠️ **代码生成识别**: 如果用户查询中包含"生成代码"、"编写脚本"、"Python代码"等关键词，必须使用code_generation工具
⚠️ **自定义分析识别**: 如果用户要求分析特定水文特征（洪峰、枯水期等）或非标准指标，必须使用custom_analysis工具，而不是仅使用evaluate+visualize
⚠️ **evaluate vs custom_analysis**:
   - evaluate只能输出标准指标（NSE、RMSE、KGE等）
   - 如果用户要分析"洪峰误差"、"枯水期精度"、"峰现时间"等特定特征，必须用custom_analysis

## 常见工具链模式

### 独立任务（依赖=否）
- 标准率定验证: validate_data → calibrate → evaluate → visualize
- 流量预测分析: validate_data → calibrate → simulate → visualize
- 代码生成分析: validate_data → calibrate → evaluate → code_generation
- 自定义水文分析: validate_data → calibrate → evaluate → custom_analysis

### 复合任务后续步骤（依赖=是）
- 绘制图表: visualize
- 生成分析代码: code_generation
- 自定义分析: custom_analysis

## 典型任务识别示例

### 独立任务示例
- "分析洪峰流量的模拟误差" → 使用 custom_analysis（需要提取洪峰并计算误差）
- "统计枯水期的模拟精度" → 使用 custom_analysis（需要筛选枯水期数据）
- "生成Python代码计算径流系数" → 使用 code_generation（明确要求生成代码）
- "率定XAJ模型并评估性能" → 使用 evaluate + visualize（标准评估）

### 复合任务示例（依赖=是）
- "绘制水文过程线"（前置：已率定） → **只需** visualize
- "生成径流系数代码"（前置：已率定和评估） → **只需** code_generation
- "分析洪峰误差"（前置：已率定和评估） → **只需** custom_analysis

## 你的任务
根据用户查询，选择合适的工具并确定执行顺序。

**特别注意**：
1. ⚠️ **🔄 复合任务依赖检测**（最优先！）:
   - 如果"依赖前置任务=是" → **跳过所有前置工具**（validate_data、calibrate、evaluate）
   - 直接选择后续工具: visualize、code_generation 或 custom_analysis
   - **不要重复执行已完成的工具**！

2. ⚠️ **代码生成检测**: 检查是否包含"生成代码"、"编写脚本"、"生成Python"、"写程序"等关键词
   - 如果有 → 必须使用 code_generation
   - 独立任务: validate_data → calibrate → evaluate → code_generation
   - 依赖任务: code_generation

3. ⚠️ **自定义分析检测**: 检查是否要分析特定水文特征或非标准指标
   - 关键词: "分析洪峰"、"分析枯水期"、"统计XX"、"提取XX"、"分析XX误差/精度"
   - 如果有 → 必须使用 custom_analysis（不要只用evaluate+visualize）
   - 独立任务: validate_data → calibrate → evaluate → custom_analysis
   - 依赖任务: custom_analysis

4. ⚠️ **区分evaluate和custom_analysis**:
   - evaluate: 只输出标准指标（NSE、RMSE、KGE等），适合基本验证
   - custom_analysis: 深入分析特定特征（洪峰、枯水期、误差分布等）
   - **判断标准**: 如果任务超出标准指标范围 → 使用custom_analysis

5. ⚠️ 不要用visualize替代code_generation或custom_analysis

返回JSON格式（不要markdown标记）：
{{
    "tool_chain": [
        {{"tool": "工具名", "description": "步骤描述", "required": true/false}}
    ],
    "execution_mode": "simple",
    "reasoning": "选择这些工具的理由。必须说明：1) 是否检测到依赖关系（如果是，为什么跳过前置工具）；2) 如果使用code_generation或custom_analysis，识别到了哪些关键词；3) 为什么选择这个工具链"
}}
"""

        # Call LLM
        try:
            response = self.llm_interface.generate(
                system_prompt="你是一个水文建模工具编排专家，负责为用户任务选择合适的工具链。",
                user_prompt=prompt,
                temperature=0.3
            )

            # Parse JSON response
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()

            llm_result = json.loads(response)

            self.logger.info(f"[ToolOrchestrator] LLM selected {len(llm_result.get('tool_chain', []))} tools")
            self.logger.info(f"[ToolOrchestrator] Reasoning: {llm_result.get('reasoning', 'N/A')}")

            # Convert LLM tool chain to our format with inputs
            tool_chain = self._enrich_tool_chain(llm_result.get("tool_chain", []), intent_result)

            # 🔧 CRITICAL FIX: 根据task_type强制设置execution_mode（不依赖LLM返回值）
            execution_mode = "simple"  # Default
            mode_params = {}

            if task_type in ["iterative_optimization", "auto_iterative_calibration"]:
                execution_mode = "iterative"
                mode_params = {
                    "max_iterations": intent_result.get("max_iterations", 5),
                    "nse_threshold": intent_result.get("nse_threshold", 0.65),
                    "boundary_threshold": intent_result.get("boundary_threshold", 0.05),
                    "min_nse_improvement": intent_result.get("min_nse_improvement", 0.01)
                }
                self.logger.info(f"[ToolOrchestrator] Set execution_mode=iterative for {task_type}")
                self.logger.info(f"[ToolOrchestrator] mode_params: {mode_params}")

            elif task_type in ["repeated_experiment", "repeated_calibration"]:
                execution_mode = "repeated"
                mode_params = {
                    "repeat_times": intent_result.get("n_repeats") or intent_result.get("repeat_times", 5)
                }
                self.logger.info(f"[ToolOrchestrator] Set execution_mode=repeated for {task_type}")
                self.logger.info(f"[ToolOrchestrator] mode_params: {mode_params}")

            return {
                "task_type": task_type,
                "subtasks": [],
                "tool_chain": tool_chain,
                "execution_mode": execution_mode,
                "mode_params": mode_params,
                "total_tools": len(tool_chain),
                "use_tool_system": True
            }

        except Exception as e:
            self.logger.error(f"[ToolOrchestrator] LLM orchestration error: {e}")
            raise

    def _enrich_tool_chain(
        self,
        llm_tool_chain: List[Dict[str, Any]],
        intent_result: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        将LLM返回的简化工具链转换为完整的工具链（补充inputs等）。

        Args:
            llm_tool_chain: LLM返回的工具链
            intent_result: Intent结果

        Returns:
            完整的工具链
        """
        enriched_chain = []

        # Extract common parameters
        basin_ids = intent_result.get("basin_ids") or intent_result.get("basin_id")
        if not basin_ids:
            basin_ids = []
        elif isinstance(basin_ids, str):
            basin_ids = [basin_ids]
        elif not isinstance(basin_ids, list):
            basin_ids = [basin_ids]

        time_period = intent_result.get("time_period", {})
        if isinstance(time_period, dict):
            train_period = time_period.get("train")
            test_period = time_period.get("test")
        else:
            train_period = intent_result.get("train_period")
            test_period = intent_result.get("test_period")

        data_source = intent_result.get("data_source", "camels_us")

        # Enrich each tool with proper inputs
        for tool_spec in llm_tool_chain:
            tool_name = tool_spec.get("tool")
            description = tool_spec.get("description", "")
            required = tool_spec.get("required", True)

            inputs = {}

            # Add tool-specific inputs based on name
            if tool_name == "validate_data":
                inputs = {
                    "basin_ids": basin_ids,
                    "train_period": train_period,
                    "test_period": test_period,
                    "data_source": data_source,
                    "required_variables": ["streamflow"]
                }
            elif tool_name == "calibrate":
                inputs = {"config": intent_result.get("config", {})}
            elif tool_name == "evaluate":
                inputs = {
                    "calibration_dir": "${calibrate.calibration_dir}",
                    "config": intent_result.get("config", {})
                }
            elif tool_name == "simulate":
                inputs = {
                    "config": intent_result.get("config", {}),
                    "calibration_dir": "${calibrate.calibration_dir}",
                    "show_progress": True
                }
            elif tool_name == "visualize":
                inputs = {
                    "calibration_dir": "${calibrate.calibration_dir}",
                    "basin_ids": basin_ids,
                    "plot_types": ["hydrograph", "metrics"]
                }
            elif tool_name == "custom_analysis":
                analysis_request = intent_result.get("analysis_request", "自定义分析")
                inputs = {
                    "analysis_request": analysis_request,
                    "calibration_dir": "${calibrate.calibration_dir}",
                    "basin_ids": basin_ids,
                    "data_source": data_source
                }
            elif tool_name == "code_generation":
                inputs = {
                    "analysis_types": ["custom"],
                    "calibration_dir": "${calibrate.calibration_dir}",
                    "basin_ids": basin_ids
                }

            enriched_chain.append({
                "tool": tool_name,
                "inputs": inputs,
                "description": description,
                "required": required
            })

        return enriched_chain

    def _get_relevant_tools(
        self,
        task_type: str,
        intent_result: Dict[str, Any]
    ) -> List[str]:
        """
        根据任务类型筛选相关工具，减少LLM提示词长度。

        Args:
            task_type: 任务类型
            intent_result: 意图结果

        Returns:
            相关工具名称列表
        """
        # 核心工具（几乎所有任务都需要）
        core_tools = ["validate_data", "calibrate", "evaluate", "visualize"]

        # 高级工具（根据任务类型选择性添加）
        advanced_tools = {
            "simulate": ["simulation", "repeated_experiment"],  # 模拟类任务
            "code_generation": ["extended_analysis", "batch_processing"],  # 代码生成类任务
            "custom_analysis": ["extended_analysis", "batch_processing"],  # 自定义分析类任务
        }

        # 开始选择工具
        relevant_tools = set(core_tools)  # 从核心工具开始

        # 根据task_type添加高级工具
        for tool, task_types in advanced_tools.items():
            if task_type in task_types:
                relevant_tools.add(tool)

        # 特殊规则：检查查询中的关键词
        user_query = intent_result.get("original_query", "").lower()

        # 代码生成关键词
        code_keywords = ["生成代码", "编写脚本", "写一个程序", "python代码", "generate code", "write script"]
        if any(keyword in user_query for keyword in code_keywords):
            relevant_tools.add("code_generation")

        # 自定义分析关键词
        analysis_keywords = ["分析洪峰", "分析枯水", "统计", "筛选", "提取", "计算径流系数", "fdc", "流量历时"]
        if any(keyword in user_query for keyword in analysis_keywords):
            relevant_tools.add("custom_analysis")
            # 如果有分析需求，通常也需要代码生成
            relevant_tools.add("code_generation")

        # 模拟关键词
        sim_keywords = ["模拟流量", "预测", "生成流量序列", "simulate"]
        if any(keyword in user_query for keyword in sim_keywords):
            relevant_tools.add("simulate")

        # 如果依赖前置任务，可能不需要validate/calibrate/evaluate
        # 但保留它们以便LLM根据具体情况判断（LLM会在reasoning中说明跳过）

        self.logger.debug(f"[ToolOrchestrator] Relevant tools for {task_type}: {relevant_tools}")
        return list(relevant_tools)

    def _rule_based_orchestration(
        self,
        task_type: str,
        intent_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Rule-based tool orchestration (Phase 1 implementation).

        Args:
            task_type: Task type
            intent_result: Intent result

        Returns:
            Dict: Tool chain with execution mode
        """
        chain = []
        execution_mode = "simple"  # Default: simple execution
        mode_params = {}  # Parameters for execution mode

        # 🆕 Detect special requests in query (Phase 2 Enhancements)
        original_query = intent_result.get("original_query", "")

        # Detect analysis request
        analysis_keywords = [
            "分析", "统计", "计算", "诊断", "评价",
            "洪峰", "枯水期", "丰水期", "径流系数", "FDC", "流量历时曲线"
        ]
        has_analysis_request = any(kw in original_query for kw in analysis_keywords)

        # 🆕 Detect simulation request
        simulation_keywords = ["模拟", "预测", "预报", "预估"]
        has_simulation_request = any(kw in original_query for kw in simulation_keywords)

        # Upgrade standard_calibration to extended_analysis if analysis is requested
        if task_type == "standard_calibration" and has_analysis_request:
            # Extract analysis request from query (text after "后，" or "然后")
            analysis_request = original_query
            for separator in ["后，", "后,", "然后", "接着", "并", "同时"]:
                if separator in original_query:
                    analysis_request = original_query.split(separator)[-1].strip()
                    break

            self.logger.info(
                f"[ToolOrchestrator] Detected analysis request in calibration task: '{analysis_request[:50]}...'"
            )
            self.logger.info(
                "[ToolOrchestrator] Upgrading task_type: standard_calibration → extended_analysis"
            )

            # Upgrade task_type
            task_type = "extended_analysis"
            intent_result["analysis_request"] = analysis_request

        # 🆕 Store simulation request flag for later use
        intent_result["_has_simulation_request"] = has_simulation_request

        # Extract common parameters
        # Support both basin_id (singular) and basin_ids (plural)
        basin_ids = intent_result.get("basin_ids") or intent_result.get("basin_id")
        if not basin_ids:
            basin_ids = []
        elif isinstance(basin_ids, str):
            basin_ids = [basin_ids]
        elif not isinstance(basin_ids, list):
            basin_ids = [basin_ids]

        # Extract time periods from time_period dict or direct keys
        time_period = intent_result.get("time_period", {})
        if isinstance(time_period, dict):
            train_period = time_period.get("train")
            test_period = time_period.get("test")
        else:
            # Fallback: try direct keys (legacy format)
            train_period = intent_result.get("train_period")
            test_period = intent_result.get("test_period")

        data_source = intent_result.get("data_source", "camels_us")

        # ========== Step 1: Data Validation (for all data-dependent tasks) ==========
        if task_type in ["standard_calibration", "calibration", "evaluation",
                         "iterative_optimization", "auto_iterative_calibration",
                         "repeated_calibration", "repeated_experiment", "extended_analysis"]:
            chain.append({
                "tool": "validate_data",
                "inputs": {
                    "basin_ids": basin_ids,
                    "train_period": train_period,
                    "test_period": test_period,
                    "data_source": data_source,
                    "required_variables": ["streamflow"]
                },
                "description": "验证流域数据可用性",
                "required": True
            })

        # ========== Step 2: Main Task Tools ==========

        # Standard Calibration Workflow
        if task_type in ["standard_calibration", "calibration"]:
            chain.extend([
                {
                    "tool": "calibrate",
                    "inputs": {
                        "config": intent_result.get("config", {})  # Will be filled by InterpreterAgent
                    },
                    "description": "执行模型率定",
                    "required": True
                },
                {
                    "tool": "evaluate",
                    "inputs": {
                        "calibration_dir": "${calibrate.calibration_dir}",  # Reference to previous output
                        "config": intent_result.get("config", {})
                    },
                    "description": "评估率定结果",
                    "required": True
                }
            ])

            # 🆕 Add simulate tool if simulation is requested
            if intent_result.get("_has_simulation_request"):
                self.logger.info("[ToolOrchestrator] Detected simulation request, adding simulate tool")
                chain.append({
                    "tool": "simulate",
                    "inputs": {
                        "config": intent_result.get("config", {}),  # Will be filled by InterpreterAgent
                        "calibration_dir": "${calibrate.calibration_dir}",  # Use calibrated parameters
                        "show_progress": True
                    },
                    "description": "使用率定参数执行模拟预测",
                    "required": True
                })

            # Add visualization (optional)
            chain.append({
                "tool": "visualize",
                "inputs": {
                    "calibration_dir": "${calibrate.calibration_dir}",
                    "basin_ids": basin_ids,
                    "plot_types": ["hydrograph", "metrics"]
                },
                "description": "绘制结果图表",
                "required": False  # Optional
            })

        # Evaluation Only
        elif task_type == "evaluation":
            calibration_dir = intent_result.get("calibration_dir")
            if not calibration_dir:
                self.logger.warning("[ToolOrchestrator] Evaluation task missing calibration_dir")
                # Return empty chain - will cause error

            chain.extend([
                {
                    "tool": "evaluate",
                    "inputs": {
                        "calibration_dir": calibration_dir,
                        "config": intent_result.get("config", {})
                    },
                    "description": "执行模型评估",
                    "required": True
                },
                {
                    "tool": "visualize",
                    "inputs": {
                        "calibration_dir": calibration_dir,
                        "basin_ids": basin_ids,
                        "plot_types": ["metrics"]
                    },
                    "description": "绘制评估指标",
                    "required": False
                }
            ])

        # 🆕 Simulation Task (预测模拟)
        elif task_type in ["info_completion"] and intent_result.get("intent") == "simulation":
            # Simulation can use parameters from calibration or custom parameters
            calibration_dir = intent_result.get("calibration_dir")
            optimal_params = intent_result.get("optimal_params")

            chain.append({
                "tool": "simulate",
                "inputs": {
                    "config": intent_result.get("config", {}),  # Will be filled by InterpreterAgent
                    "calibration_dir": calibration_dir,  # Optional: load params from calibration
                    "params": optimal_params,  # Optional: use custom parameters
                    "show_progress": True
                },
                "description": "执行水文模型预测模拟",
                "required": True
            })

        # Iterative Optimization - 这是执行模式，不是独立工具
        elif task_type in ["iterative_optimization", "auto_iterative_calibration"]:
            execution_mode = "iterative"
            mode_params = {
                "max_iterations": intent_result.get("max_iterations", 5),
                "nse_threshold": intent_result.get("nse_threshold", 0.65),
                "boundary_threshold": intent_result.get("boundary_threshold", 0.05),
                "min_nse_improvement": intent_result.get("min_nse_improvement", 0.01)
            }

            # 工具链：率定 → 评估（会在 iterative 模式下循环执行）
            chain.extend([
                {
                    "tool": "calibrate",
                    "inputs": {"config": intent_result.get("config", {})},
                    "description": "执行模型率定",
                    "required": True
                },
                {
                    "tool": "evaluate",
                    "inputs": {
                        "calibration_dir": "${calibrate.calibration_dir}",
                        "config": intent_result.get("config", {})
                    },
                    "description": "评估率定结果",
                    "required": True
                }
            ])

        # Extended Analysis (实验4 - 自定义分析)
        elif task_type == "extended_analysis":
            # 🔧 v6.1 Fix: 检测是否是批量任务，批量任务中 custom_analysis 为 optional
            # Detect batch processing: multiple basins or batch keywords in query
            is_batch_task = False
            if len(basin_ids) > 1:
                is_batch_task = True
                self.logger.info(f"[ToolOrchestrator] Detected batch task: {len(basin_ids)} basins")

            batch_keywords = ["批量", "多个", "分别", "所有"]
            if any(kw in original_query for kw in batch_keywords):
                is_batch_task = True
                self.logger.info(f"[ToolOrchestrator] Detected batch keywords in query")

            # Determine if custom_analysis should be required
            custom_analysis_required = not is_batch_task
            if is_batch_task:
                self.logger.info(
                    "[ToolOrchestrator] Batch task detected → custom_analysis marked as OPTIONAL "
                    "(to prevent task failure if custom_analysis is not fully implemented)"
                )

            # First calibrate, then perform custom analysis
            chain.extend([
                {
                    "tool": "calibrate",
                    "inputs": {"config": intent_result.get("config", {})},
                    "description": "执行模型率定",
                    "required": True
                },
                {
                    "tool": "evaluate",
                    "inputs": {
                        "calibration_dir": "${calibrate.calibration_dir}",
                        "config": intent_result.get("config", {})
                    },
                    "description": "评估率定结果",
                    "required": True
                },
                {
                    "tool": "custom_analysis",  # 🆕 Changed from code_generation to custom_analysis
                    "inputs": {
                        "analysis_request": intent_result.get("analysis_request", "自定义分析"),  # 🆕 From query
                        "calibration_dir": "${calibrate.calibration_dir}",
                        "basin_ids": basin_ids,
                        "data_source": data_source
                    },
                    "description": "执行自定义分析任务",
                    "required": custom_analysis_required  # 🔧 v6.1: 批量任务中为 False
                }
            ])

        # Repeated Calibration (实验5 - 稳定性验证)
        # Support both repeated_calibration and repeated_experiment for compatibility
        elif task_type in ["repeated_calibration", "repeated_experiment"]:
            execution_mode = "repeated"
            mode_params = {
                "repeat_times": intent_result.get("n_repeats") or intent_result.get("repeat_times", 5)
            }

            # 工具链：率定 → 评估（会重复执行N次）
            chain.extend([
                {
                    "tool": "calibrate",
                    "inputs": {"config": intent_result.get("config", {})},
                    "description": "执行模型率定",
                    "required": True
                },
                {
                    "tool": "evaluate",
                    "inputs": {
                        "calibration_dir": "${calibrate.calibration_dir}",
                        "config": intent_result.get("config", {})
                    },
                    "description": "评估率定结果",
                    "required": True
                }
            ])

        # Batch Processing / Data Validation (批量处理 / 数据验证)
        elif task_type in ["batch_processing", "data_validation", "validation"]:
            # Only data validation for multiple basins
            chain.append({
                "tool": "validate_data",
                "inputs": {
                    "basin_ids": basin_ids,
                    "train_period": train_period,
                    "test_period": test_period,
                    "data_source": data_source,
                    "required_variables": ["streamflow"]
                },
                "description": "批量验证流域数据可用性",
                "required": True
            })

        # Unknown task type
        else:
            self.logger.warning(f"[ToolOrchestrator] Unknown task type: {task_type}")
            # Return empty chain

        self.logger.info(f"[ToolOrchestrator] Generated tool chain with {len(chain)} tools, execution_mode={execution_mode}")

        # Validate tool chain (Phase 2)
        is_valid, error = self.validate_tool_chain(chain)
        if not is_valid:
            self.logger.error(f"[ToolOrchestrator] Tool chain validation failed: {error}")
            raise ValueError(f"Invalid tool chain: {error}")

        self.logger.info("[ToolOrchestrator] Tool chain validation passed")

        return {
            "tool_chain": chain,
            "execution_mode": execution_mode,
            "mode_params": mode_params,
            "task_type": task_type  # 🆕 Return updated task_type (may have been upgraded from standard_calibration to extended_analysis)
        }

    def validate_tool_chain(
        self,
        tool_chain: List[Dict[str, Any]]
    ) -> tuple[bool, Optional[str]]:
        """
        Validate tool chain for correctness.

        Checks:
        1. All tools exist in registry
        2. Tool dependencies are satisfied (Phase 2)
        3. Required inputs are present

        Args:
            tool_chain: Tool chain to validate

        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        import re

        executed_tools = set()  # Track which tools have been executed

        for idx, step in enumerate(tool_chain):
            tool_name = step.get("tool")

            if not tool_name:
                return False, f"Tool chain step {idx}: missing 'tool' key"

            # Check if tool exists
            if tool_name not in self.registry:
                # For Phase 2 tools (not yet implemented), allow them
                if tool_name in ["auto_iterative_calibration", "custom_analysis",
                                 "statistical_analysis", "boundary_check"]:
                    self.logger.debug(f"[ToolOrchestrator] Tool '{tool_name}' not yet implemented (Phase 2)")
                    executed_tools.add(tool_name)
                    continue
                else:
                    return False, f"Tool '{tool_name}' not found in registry"

            # Phase 2: Check dependency references
            inputs = step.get("inputs", {})
            is_valid, error = self._validate_references(inputs, executed_tools, idx)
            if not is_valid:
                return False, error

            # Mark tool as executed for dependency tracking
            executed_tools.add(tool_name)

        return True, None

    def _validate_references(
        self,
        inputs: Dict[str, Any],
        executed_tools: set,
        step_idx: int
    ) -> tuple[bool, Optional[str]]:
        """
        Validate that all ${tool.field} references point to previously executed tools.

        Args:
            inputs: Input parameters (may contain references)
            executed_tools: Set of tools executed before this step
            step_idx: Current step index

        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        import re

        def check_value(value, path=""):
            """Recursively check a value for invalid references"""
            if isinstance(value, str):
                # Find all ${...} references
                pattern = r'\$\{([^}]+)\}'
                matches = re.findall(pattern, value)

                for match in matches:
                    parts = match.split('.')
                    referenced_tool = parts[0]

                    if referenced_tool not in executed_tools:
                        return False, (
                            f"Step {step_idx}: Invalid reference '${{{match}}}' - "
                            f"tool '{referenced_tool}' not executed yet. "
                            f"Available tools: {sorted(executed_tools)}"
                        )

            elif isinstance(value, dict):
                for k, v in value.items():
                    is_valid, error = check_value(v, f"{path}.{k}" if path else k)
                    if not is_valid:
                        return False, error

            elif isinstance(value, list):
                for i, v in enumerate(value):
                    is_valid, error = check_value(v, f"{path}[{i}]")
                    if not is_valid:
                        return False, error

            return True, None

        return check_value(inputs)

    def get_tool_chain_summary(
        self,
        tool_chain: List[Dict[str, Any]]
    ) -> str:
        """
        Get human-readable summary of tool chain.

        Args:
            tool_chain: Tool chain

        Returns:
            str: Summary string
        """
        if not tool_chain:
            return "Empty tool chain"

        lines = [f"Tool Chain ({len(tool_chain)} steps):"]
        for idx, step in enumerate(tool_chain, 1):
            tool_name = step.get("tool", "unknown")
            description = step.get("description", "No description")
            required = step.get("required", True)
            status = "✓ Required" if required else "○ Optional"
            lines.append(f"  {idx}. {tool_name}: {description} [{status}]")

        return "\n".join(lines)

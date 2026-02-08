"""
Author: Claude
Date: 2025-12-20 18:00:00
LastEditTime: 2025-12-20 18:00:00
LastEditors: Claude
Description: 智能代码生成器 - 模板优先，LLM兜底
             Smart code generator - Template first, LLM fallback
FilePath: /HydroAgent/hydroagent/utils/smart_code_generator.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import xarray as xr

logger = logging.getLogger(__name__)


class SmartCodeGenerator:
    """
    智能代码生成器。

    策略：
    1. 优先使用模板（常用分析，100%可靠）
    2. 模板不存在时使用LLM生成（灵活应对新需求）
    3. 将模板作为Few-shot示例，提高LLM生成质量
    """

    def __init__(self, code_llm, templates_dir: Optional[Path] = None):
        """
        Initialize SmartCodeGenerator.

        Args:
            code_llm: Code LLM接口
            templates_dir: 模板目录
        """
        self.code_llm = code_llm

        if templates_dir is None:
            project_root = Path(__file__).parent.parent.parent
            templates_dir = project_root / "hydroagent" / "resources" / "code_templates"

        self.templates_dir = templates_dir

        # 加载所有模板作为示例库
        self.template_examples = self._load_template_examples()

        logger.info(f"[SmartCodeGenerator] Initialized with {len(self.template_examples)} template examples")

    def _load_template_examples(self) -> Dict[str, str]:
        """加载模板作为示例"""
        examples = {}

        if not self.templates_dir.exists():
            logger.warning(f"[SmartCodeGenerator] Templates directory not found: {self.templates_dir}")
            return examples

        for template_file in self.templates_dir.glob("*_template.py"):
            # 提取分析类型 (e.g., "FDC_template.py" -> "FDC")
            analysis_type = template_file.stem.replace("_template", "")

            try:
                template_code = template_file.read_text(encoding="utf-8")
                examples[analysis_type] = template_code
                logger.debug(f"[SmartCodeGenerator] Loaded template example: {analysis_type}")
            except Exception as e:
                logger.warning(f"[SmartCodeGenerator] Failed to load template {template_file}: {e}")

        return examples

    def generate_code(
        self,
        analysis_type: str,
        params: Dict[str, Any],
        use_template_if_exists: bool = True
    ) -> Dict[str, Any]:
        """
        智能代码生成（模板优先，LLM兜底）。

        Args:
            analysis_type: 分析类型
            params: 参数字典
            use_template_if_exists: 如果模板存在，优先使用模板

        Returns:
            {"code": str, "method": "template"|"llm"}
        """
        # Step 1: 优先使用模板（如果存在）
        if use_template_if_exists and analysis_type in self.template_examples:
            logger.info(f"[SmartCodeGenerator] Using template for {analysis_type}")
            return self._generate_from_template(analysis_type, params)

        # Step 2: 使用LLM生成
        logger.info(f"[SmartCodeGenerator] Using LLM for {analysis_type} (no template available)")
        return self._generate_with_llm(analysis_type, params)

    def _generate_from_template(self, analysis_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """从模板生成代码"""
        from .template_manager import TemplateManager, extract_placeholders

        template_manager = TemplateManager(templates_dir=self.templates_dir)

        # 提取占位符
        nc_file_path = params.get("nc_file_path", "")
        basin_id = params.get("basin_id", "unknown")
        output_dir = params.get("output_dir", "results")

        placeholders = extract_placeholders(nc_file_path, basin_id, output_dir)

        # 生成代码
        code = template_manager.generate_code(analysis_type, placeholders)

        return {
            "code": code,
            "method": "template",
            "analysis_type": analysis_type
        }

    def _generate_with_llm(self, analysis_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """使用LLM生成代码（带Few-shot示例）"""

        # Step 1: 构建智能提示词
        prompt = self._build_smart_prompt(analysis_type, params)

        # Step 2: 调用LLM
        try:
            response = self.code_llm.generate(
                system_prompt=self._get_code_generation_system_prompt(),
                user_prompt=prompt,
                temperature=0.1,  # 低温度保证代码质量
                max_tokens=3000
            )

            # Step 3: 提取代码
            code = self._extract_code_from_response(response)

            return {
                "code": code,
                "method": "llm",
                "analysis_type": analysis_type,
                "llm_response": response
            }

        except Exception as e:
            logger.error(f"[SmartCodeGenerator] LLM generation failed: {e}")
            return {
                "error": str(e),
                "method": "llm_failed"
            }

    def _build_smart_prompt(self, analysis_type: str, params: Dict[str, Any]) -> str:
        """构建智能提示词（包含Few-shot示例和数据schema）"""

        parts = []

        # Part 1: 任务描述
        parts.append("# 任务\n")
        parts.append(f"生成Python代码来完成水文分析任务：**{analysis_type}**\n")
        parts.append(f"用户需求：{params.get('user_query', analysis_type)}\n")

        # Part 2: 数据信息
        parts.append("\n# 数据源\n")
        nc_file_path = params.get("nc_file_path", "")
        basin_id = params.get("basin_id", "unknown")

        if nc_file_path:
            parts.append(f"- NC文件路径: `{nc_file_path}`\n")

            # 尝试读取NC文件schema
            data_schema = self._get_nc_file_schema(nc_file_path)
            if data_schema:
                parts.append(f"- 可用变量: {', '.join(data_schema['variables'])}\n")
                parts.append(f"- 数据维度: {data_schema['dimensions']}\n")

        parts.append(f"- 流域ID: {basin_id}\n")
        parts.append(f"- 输出目录: {params.get('output_dir', 'results')}\n")

        # Part 3: Few-shot示例（提供1-2个最相关的模板）
        parts.append("\n# 参考示例\n")
        parts.append("以下是类似任务的高质量代码示例，请学习其风格和结构：\n")

        relevant_examples = self._get_relevant_examples(analysis_type)
        for i, (example_type, example_code) in enumerate(relevant_examples[:2], 1):
            parts.append(f"\n## 示例 {i}: {example_type}\n")
            parts.append("```python\n")
            parts.append(self._extract_key_functions(example_code))  # 只提取关键函数，节省token
            parts.append("```\n")

        # Part 4: 代码要求
        parts.append("\n# 代码要求\n")
        parts.append(self._get_code_requirements())

        # Part 5: 输出格式
        parts.append("\n# 输出格式\n")
        parts.append("请直接输出完整的Python代码，使用以下格式：\n")
        parts.append("```python\n")
        parts.append("# 你的代码\n")
        parts.append("```\n")

        return "\n".join(parts)

    def _get_nc_file_schema(self, nc_file_path: str) -> Optional[Dict[str, Any]]:
        """获取NC文件的schema信息"""
        try:
            # 如果是目录，找到第一个.nc文件
            path_obj = Path(nc_file_path)
            if path_obj.is_dir():
                nc_files = list(path_obj.glob("*.nc"))
                if nc_files:
                    nc_file_path = str(nc_files[0])
                else:
                    return None

            with xr.open_dataset(nc_file_path) as ds:
                return {
                    "variables": list(ds.data_vars.keys()),
                    "dimensions": {dim: ds.sizes[dim] for dim in ds.dims},
                    "coords": list(ds.coords.keys())
                }
        except Exception as e:
            logger.warning(f"[SmartCodeGenerator] Failed to read NC schema: {e}")
            return None

    def _get_relevant_examples(self, analysis_type: str) -> List[tuple]:
        """获取最相关的模板示例"""
        # 简单策略：返回所有示例（可以扩展为相似度匹配）
        return list(self.template_examples.items())

    def _extract_key_functions(self, template_code: str, max_lines: int = 100) -> str:
        """从模板中提取关键函数（避免提示词过长）"""
        lines = template_code.split("\n")

        # 提取主要函数定义
        key_sections = []
        in_function = False
        current_function = []

        for line in lines:
            if line.strip().startswith("def ") and "main(" not in line:
                in_function = True
                current_function = [line]
            elif in_function:
                current_function.append(line)

                # 函数结束（空行或下一个def）
                if line.strip() == "" or (line.strip().startswith("def ") and len(current_function) > 1):
                    key_sections.extend(current_function)
                    in_function = False
                    current_function = []

                    # 限制长度
                    if len(key_sections) > max_lines:
                        break

        return "\n".join(key_sections[:max_lines])

    def _get_code_requirements(self) -> str:
        """获取代码生成要求"""
        return """
1. **类型提示**: 所有函数必须包含type hints
2. **错误处理**: 使用try-except处理文件读取、数据处理等可能出错的操作
3. **中文支持**: 配置matplotlib中文显示（使用SimHei、Microsoft YaHei）
4. **输出文件**:
   - 图表保存为PNG格式，dpi=300
   - 数据保存为CSV格式，使用utf-8编码
   - 文件名格式：`{analysis_type}_{basin_id}.{ext}`
5. **进度信息**: 使用print()打印关键步骤和结果
6. **main函数**: 必须包含main()函数作为入口点
7. **路径处理**: 使用pathlib.Path处理路径
8. **数据验证**: 检查NC文件是否存在，变量是否存在
9. **注释**: 关键逻辑添加中文注释
10. **返回值**: main()函数返回0（成功）或1（失败）
"""

    def _get_code_generation_system_prompt(self) -> str:
        """获取代码生成的system prompt"""
        return """你是一个专业的Python水文分析代码生成专家。

你的职责是根据用户需求生成高质量、可运行的Python代码。

核心原则:
1. **代码质量**: 生成的代码必须遵循Python最佳实践
2. **健壮性**: 包含完整的错误处理和数据验证
3. **可读性**: 清晰的变量命名和适当的注释
4. **学习能力**: 参考提供的示例代码，学习其风格和结构

技术要求:
- 使用Python 3.9+
- 常用库: xarray, numpy, pandas, matplotlib
- NetCDF文件读取: xarray.open_dataset()
- 时间序列处理: pandas.to_datetime()
- 绘图: matplotlib.pyplot

输出规范:
- 直接输出完整的Python代码
- 使用```python...```包裹代码
- 不要添加额外的解释文本（除非在代码注释中）
"""

    def _extract_code_from_response(self, response: str) -> str:
        """从LLM响应中提取代码"""
        import re

        # 尝试提取```python...```代码块
        match = re.search(r"```python\s*(.*?)\s*```", response, re.DOTALL)
        if match:
            return match.group(1).strip()

        # 尝试提取```...```代码块
        match = re.search(r"```\s*(.*?)\s*```", response, re.DOTALL)
        if match:
            return match.group(1).strip()

        # 如果没有代码块标记，返回全部内容
        logger.warning("[SmartCodeGenerator] No code block found, using full response")
        return response.strip()


def generate_analysis_code_smart(
    code_llm,
    analysis_type: str,
    params: Dict[str, Any],
    project_root: Optional[Path] = None,
    use_template_if_exists: bool = True
) -> Dict[str, Any]:
    """
    智能代码生成的便捷函数。

    Args:
        code_llm: Code LLM接口
        analysis_type: 分析类型
        params: 参数字典
        project_root: 项目根目录
        use_template_if_exists: 优先使用模板

    Returns:
        生成结果 {"code": str, "code_file": str, "method": str}
    """
    if project_root is None:
        project_root = Path(__file__).parent.parent.parent

    # 创建智能代码生成器
    generator = SmartCodeGenerator(code_llm)

    # 生成代码
    result = generator.generate_code(analysis_type, params, use_template_if_exists)

    if "error" in result:
        return result

    code = result["code"]
    method = result["method"]

    # 保存代码到文件
    generated_code_dir = project_root / "generated_code"
    generated_code_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    code_file = generated_code_dir / f"{analysis_type}_analysis_{timestamp}.py"

    code_file.write_text(code, encoding="utf-8")

    logger.info(f"[SmartCodeGenerator] Code saved to: {code_file} (method: {method})")

    return {
        "code": code,
        "code_file": str(code_file),
        "method": method,
        "analysis_type": analysis_type
    }

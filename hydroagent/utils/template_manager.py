"""
Author: Claude
Date: 2025-12-07 17:00:00
LastEditTime: 2025-12-07 17:00:00
LastEditors: Claude
Description: Template-based code generation manager for reliable analysis script generation
FilePath: /HydroAgent/hydroagent/utils/template_manager.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class TemplateManager:
    """
    Manages pre-validated code templates for common analysis tasks.

    This provides 100% reliability for supported analysis types by using
    pre-tested, validated code templates instead of LLM-generated code.
    """

    # Mapping from analysis_type to template file
    TEMPLATE_MAP = {
        'runoff_coefficient': 'runoff_coefficient_template.py',
        'FDC': 'FDC_template.py',
        'flow_duration_curve': 'FDC_template.py',  # Alias
    }

    def __init__(self, templates_dir: Optional[str] = None):
        """
        Initialize TemplateManager

        Args:
            templates_dir: Path to templates directory. If None, uses default location.
        """
        if templates_dir is None:
            # Default: hydroagent/resources/code_templates/
            current_file = Path(__file__)
            self.templates_dir = current_file.parent.parent / "resources" / "code_templates"
        else:
            self.templates_dir = Path(templates_dir)

        logger.info(f"[TemplateManager] Templates directory: {self.templates_dir}")

        # Verify templates directory exists
        if not self.templates_dir.exists():
            logger.warning(f"[TemplateManager] Templates directory does not exist: {self.templates_dir}")
            self.templates_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"[TemplateManager] Created templates directory")

    def has_template(self, analysis_type: str) -> bool:
        """
        Check if a template exists for the given analysis type

        Args:
            analysis_type: Type of analysis (e.g., 'runoff_coefficient', 'FDC')

        Returns:
            bool: True if template exists
        """
        template_name = self.TEMPLATE_MAP.get(analysis_type)
        if template_name is None:
            return False

        template_path = self.templates_dir / template_name
        return template_path.exists()

    def get_template(self, analysis_type: str) -> Optional[str]:
        """
        Get template code for the given analysis type

        Args:
            analysis_type: Type of analysis (e.g., 'runoff_coefficient', 'FDC')

        Returns:
            str: Template code, or None if template not found
        """
        template_name = self.TEMPLATE_MAP.get(analysis_type)
        if template_name is None:
            logger.warning(f"[TemplateManager] No template mapping for analysis_type='{analysis_type}'")
            return None

        template_path = self.templates_dir / template_name

        if not template_path.exists():
            logger.warning(f"[TemplateManager] Template file not found: {template_path}")
            return None

        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template_code = f.read()

            logger.info(f"[TemplateManager] Loaded template: {template_name} ({len(template_code)} chars)")
            return template_code

        except Exception as e:
            logger.error(f"[TemplateManager] Failed to load template {template_name}: {e}")
            return None

    def fill_template(
        self,
        template_code: str,
        placeholders: Dict[str, str]
    ) -> str:
        """
        Fill template placeholders with actual values

        Args:
            template_code: Template code with {{PLACEHOLDER}} markers
            placeholders: Dictionary mapping placeholder names to values
                         e.g., {'NC_FILE_PATH': 'path/to/data.nc', 'BASIN_ID': '01539000'}

        Returns:
            str: Code with placeholders replaced
        """
        filled_code = template_code

        for key, value in placeholders.items():
            placeholder = f"{{{{{key}}}}}"  # {{KEY}}
            filled_code = filled_code.replace(placeholder, str(value))

        logger.info(f"[TemplateManager] Filled {len(placeholders)} placeholders")

        # Check for any remaining placeholders (indicating missing values)
        import re
        remaining = re.findall(r'\{\{(\w+)\}\}', filled_code)
        if remaining:
            logger.warning(f"[TemplateManager] Unfilled placeholders: {remaining}")

        return filled_code

    def generate_code(
        self,
        analysis_type: str,
        placeholders: Dict[str, str]
    ) -> Optional[str]:
        """
        Generate complete code from template

        This is a convenience method combining get_template() and fill_template()

        Args:
            analysis_type: Type of analysis
            placeholders: Dictionary of placeholder values

        Returns:
            str: Complete code ready to execute, or None if template not found
        """
        template_code = self.get_template(analysis_type)

        if template_code is None:
            return None

        filled_code = self.fill_template(template_code, placeholders)

        logger.info(f"[TemplateManager] Generated code for {analysis_type} ({len(filled_code)} chars)")

        return filled_code

    def list_available_templates(self) -> List[str]:
        """
        List all available analysis types with templates

        Returns:
            List[str]: List of analysis type names
        """
        available = []

        for analysis_type, template_name in self.TEMPLATE_MAP.items():
            template_path = self.templates_dir / template_name
            if template_path.exists():
                available.append(analysis_type)

        return available


def extract_placeholders(nc_file_path: str, basin_id: str, output_dir: str) -> Dict[str, str]:
    """
    Helper function to extract common placeholders from analysis parameters

    🆕 v5.1: 自动修复Windows路径转义问题

    Args:
        nc_file_path: Path to NetCDF data file
        basin_id: Basin ID
        output_dir: Output directory for results

    Returns:
        Dict[str, str]: Placeholder dictionary ready for fill_template()
    """
    # 🆕 修复Windows路径转义问题：
    # 将反斜杠转换为双反斜杠，确保在Python字符串中正确解析
    # 例如：D:\project\... → D:\\project\\...
    def fix_windows_path(path: str) -> str:
        """修复Windows路径，避免转义序列错误"""
        if not isinstance(path, str):
            return str(path)

        # 如果路径包含反斜杠，加上原始字符串前缀
        if '\\' in path:
            # 替换单反斜杠为双反斜杠（用于字符串字面量）
            # 或者使用原始字符串标记
            # 这里我们保持路径不变，但在模板中使用r""字符串
            return path.replace('\\', '\\\\')
        return path

    return {
        'NC_FILE_PATH': fix_windows_path(nc_file_path),
        'BASIN_ID': basin_id,
        'OUTPUT_DIR': fix_windows_path(output_dir)
    }

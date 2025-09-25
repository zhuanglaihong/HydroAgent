"""
数据准备工具
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any
import logging

# 添加项目根路径
repo_path = Path(os.path.abspath(__file__)).parent.parent.parent.parent
sys.path.append(str(repo_path))

from .base_tool import BaseTool, ToolResult

# 尝试导入相关模块
try:
    from definitions import DATASET_DIR
    from hydromodel.datasets.data_preprocess import process_and_save_data_as_nc
    HYDROMODEL_AVAILABLE = True
except ImportError as e:
    logging.warning(f"水文模型模块导入失败: {e}")
    HYDROMODEL_AVAILABLE = False
    DATASET_DIR = "data"


class PrepareDataTool(BaseTool):
    """数据准备工具"""

    def __init__(self):
        super().__init__(
            name="prepare_data",
            description="处理和验证水文时间序列数据，转换为模型可用格式"
        )

    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """验证输入参数"""
        try:
            # 设置默认值
            data_dir = parameters.get("data_dir", DATASET_DIR)
            target_data_scale = parameters.get("target_data_scale", "D")

            # 验证数据目录
            if not isinstance(data_dir, str):
                self.logger.error("data_dir 必须是字符串")
                return False

            # 验证时间尺度
            valid_scales = ["D", "M", "Y"]
            if target_data_scale not in valid_scales:
                self.logger.error(f"target_data_scale 必须是 {valid_scales} 中的一个")
                return False

            # 检查数据目录是否存在
            if not os.path.exists(data_dir):
                self.logger.error(f"数据目录不存在: {data_dir}")
                return False

            return True

        except Exception as e:
            self.logger.error(f"参数验证失败: {e}")
            return False

    def get_parameter_schema(self) -> Dict[str, Any]:
        """获取参数模式定义"""
        return {
            "type": "object",
            "properties": {
                "data_dir": {
                    "type": "string",
                    "description": "数据目录路径",
                    "default": DATASET_DIR
                },
                "target_data_scale": {
                    "type": "string",
                    "description": "数据时间尺度，默认为日尺度('D')，可选'M'(月尺度)或'Y'(年尺度)",
                    "enum": ["D", "M", "Y"],
                    "default": "D"
                }
            },
            "required": [],
            "additionalProperties": False
        }

    def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """执行数据准备"""
        if not HYDROMODEL_AVAILABLE:
            return self._create_error_result(
                "水文模型模块不可用，请检查依赖安装"
            )

        # 获取参数，设置默认值
        data_dir = parameters.get("data_dir", DATASET_DIR)
        target_data_scale = parameters.get("target_data_scale", "D")

        try:
            # 确保数据目录存在
            if not os.path.exists(data_dir):
                return self._create_error_result(f"数据目录不存在: {data_dir}")

            # 检查数据目录中的文件
            data_files = self._check_data_files(data_dir)
            if not data_files["has_required_files"]:
                return self._create_error_result(
                    f"数据目录缺少必要文件: {data_files['missing_files']}"
                )

            # 处理数据
            self.logger.info(f"开始处理数据目录: {data_dir}, 时间尺度: {target_data_scale}")

            # 调用数据处理函数
            success = process_and_save_data_as_nc(
                folder_path=data_dir,
                target_data_scale=target_data_scale,
                save_folder=data_dir
            )

            if success:
                # 检查处理后的文件
                processed_files = self._check_processed_files(data_dir)

                output = {
                    "status": "success",
                    "message": "数据准备完成，已转换为nc格式",
                    "data_dir": data_dir,
                    "target_data_scale": target_data_scale,
                    "input_files": data_files["found_files"],
                    "processed_files": processed_files["nc_files"],
                    "file_count": len(processed_files["nc_files"]),
                    "processing_details": {
                        "input_format": "csv/txt",
                        "output_format": "netcdf",
                        "time_scale": target_data_scale
                    }
                }

                self.logger.info(f"数据处理成功，生成 {len(processed_files['nc_files'])} 个文件")
                return self._create_success_result(output)
            else:
                return self._create_error_result(
                    "数据准备失败，请检查数据格式和内容"
                )

        except Exception as e:
            error_msg = f"数据准备失败: {str(e)}"
            self.logger.error(error_msg)
            return self._create_error_result(error_msg)

    def _check_data_files(self, data_dir: str) -> Dict[str, Any]:
        """检查数据目录中的文件"""
        try:
            data_path = Path(data_dir)
            found_files = []
            required_patterns = [".csv", ".txt"]

            # 搜索数据文件
            for pattern in ["*.csv", "*.txt"]:
                found_files.extend(list(data_path.glob(pattern)))

            # 转换为字符串路径
            found_file_names = [f.name for f in found_files]

            # 检查是否有必要的文件
            has_required_files = len(found_files) > 0

            return {
                "has_required_files": has_required_files,
                "found_files": found_file_names,
                "missing_files": [] if has_required_files else required_patterns,
                "total_files": len(found_files)
            }

        except Exception as e:
            self.logger.error(f"检查数据文件失败: {e}")
            return {
                "has_required_files": False,
                "found_files": [],
                "missing_files": ["检查失败"],
                "total_files": 0
            }

    def _check_processed_files(self, data_dir: str) -> Dict[str, Any]:
        """检查处理后的文件"""
        try:
            data_path = Path(data_dir)
            nc_files = list(data_path.glob("*.nc"))
            nc_file_names = [f.name for f in nc_files]

            return {
                "nc_files": nc_file_names,
                "count": len(nc_files)
            }

        except Exception as e:
            self.logger.error(f"检查处理后文件失败: {e}")
            return {
                "nc_files": [],
                "count": 0
            }
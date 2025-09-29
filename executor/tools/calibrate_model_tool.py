"""
Author: zhuanglaihong
Date: 2024-09-26 16:30:00
LastEditTime: 2024-09-26 16:30:00
LastEditors: zhuanglaihong
Description: 水文模型率定工具
FilePath: \HydroAgent\executor\tools\calibrate_model_tool.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import sys
import os
import yaml
from pathlib import Path
from typing import Dict, Any
import logging
import numpy as np

# 添加项目根路径
repo_path = Path(os.path.abspath(__file__)).parent.parent.parent
sys.path.append(str(repo_path))

from .base_tool import BaseTool, ToolResult

# 尝试导入水文模型模块
try:
    from hydromodel.models.model_dict import MODEL_DICT
    from hydromodel.models.model_config import MODEL_PARAM_DICT
    from hydromodel.datasets.data_preprocess import (
        cross_val_split_tsdata,
        _get_pe_q_from_ts,
    )
    from hydromodel.trainers.calibrate_sceua import calibrate_by_sceua

    HYDROMODEL_AVAILABLE = True
except ImportError as e:
    logging.warning(f"水文模型模块导入失败: {e}")
    HYDROMODEL_AVAILABLE = False


class CalibrateModelTool(BaseTool):
    """水文模型率定工具"""

    def __init__(self):
        super().__init__(
            name="calibrate_model",
            description="率定水文模型，使用SCE-UA算法优化模型参数",
        )

    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """验证输入参数"""
        try:
            # 检查必需参数
            required_params = ["data_dir", "basin_ids"]
            for param in required_params:
                if param not in parameters:
                    self.logger.error(f"缺少必需参数: {param}")
                    return False

            # 检查数据目录是否存在
            if not os.path.exists(parameters["data_dir"]):
                self.logger.error(f"数据目录不存在: {parameters['data_dir']}")
                return False

            # 检查basin_ids是否为列表
            if not isinstance(parameters["basin_ids"], list):
                self.logger.error("basin_ids 必须是列表")
                return False

            if len(parameters["basin_ids"]) == 0:
                self.logger.error("basin_ids 不能为空")
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
                "data_type": {
                    "type": "string",
                    "description": "数据类型",
                    "default": "owndata",
                },
                "data_dir": {
                    "type": "string",
                    "description": "数据目录路径",
                    "default": "data/camels_11532500",
                },
                "result_dir": {
                    "type": "string",
                    "description": "结果保存目录，如果不提供则使用默认目录",
                    "default": "result",
                },
                "exp_name": {
                    "type": "string",
                    "description": "实验名称",
                    "default": "exp_calibration",
                },
                "model": {
                    "type": "object",
                    "description": "模型配置",
                    "properties": {
                        "name": {"type": "string", "default": "gr4j"},
                        "source_type": {"type": "string", "default": "sources"},
                        "source_book": {"type": "string", "default": "HF"},
                        "kernel_size": {"type": "integer", "default": 15},
                        "time_interval_hours": {"type": "integer", "default": 24},
                    },
                    "default": {
                        "name": "gr4j",
                        "source_type": "sources",
                        "source_book": "HF",
                        "kernel_size": 15,
                        "time_interval_hours": 24,
                    },
                },
                "basin_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "流域ID列表",
                },
                "periods": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "整个时间段 [start_date, end_date]",
                    "default": ["2000-01-01", "2023-12-31"],
                },
                "calibrate_period": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "率定时间段 [start_date, end_date]",
                    "default": ["2000-01-01", "2018-12-31"],
                },
                "test_period": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "测试时间段 [start_date, end_date]",
                    "default": ["2019-01-01", "2023-12-31"],
                },
                "warmup": {
                    "type": "integer",
                    "description": "预热期长度",
                    "default": 720,
                },
                "cv_fold": {
                    "type": "integer",
                    "description": "交叉验证折数",
                    "default": 1,
                },
                "algorithm": {
                    "type": "object",
                    "description": "优化算法配置",
                    "properties": {
                        "name": {"type": "string", "default": "SCE_UA"},
                        "random_seed": {"type": "integer", "default": 1234},
                        "rep": {"type": "integer", "default": 100},
                        "ngs": {"type": "integer", "default": 30},
                        "kstop": {"type": "integer", "default": 5},
                        "peps": {"type": "number", "default": 0.05},
                        "pcento": {"type": "number", "default": 0.05},
                    },
                    "default": {
                        "name": "SCE_UA",
                        "random_seed": 1234,
                        "rep": 100,
                        "ngs": 30,
                        "kstop": 5,
                        "peps": 0.05,
                        "pcento": 0.05,
                    },
                },
                "loss": {
                    "type": "object",
                    "description": "损失函数配置",
                    "properties": {
                        "type": {"type": "string", "default": "time_series"},
                        "obj_func": {"type": "string", "default": "RMSE"},
                        "events": {"type": ["null", "array"], "default": None},
                    },
                    "default": {
                        "type": "time_series",
                        "obj_func": "RMSE",
                        "events": None,
                    },
                },
                "param_range_file": {
                    "type": "string",
                    "description": "参数范围配置文件路径",
                },
            },
            "required": ["data_dir", "basin_ids"],
            "additionalProperties": False,
        }

    def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """执行模型率定"""
        if not HYDROMODEL_AVAILABLE:
            return self._create_error_result(
                "水文模型模块不可用，请检查 hydromodel 依赖安装"
            )

        try:
            # 设置默认参数
            data_type = parameters.get("data_type", "owndata")
            data_dir = parameters["data_dir"]
            result_dir = parameters.get("result_dir")
            exp_name = parameters.get("exp_name", "exp_calibration")
            model = parameters.get(
                "model",
                {
                    "name": "gr4j",
                    "source_type": "sources",
                    "source_book": "HF",
                    "kernel_size": 15,
                    "time_interval_hours": 24,
                },
            )
            basin_ids = parameters["basin_ids"]
            periods = parameters.get("periods", ["2000-01-01", "2023-12-31"])
            calibrate_period = parameters.get(
                "calibrate_period", ["2000-01-01", "2018-12-31"]
            )
            test_period = parameters.get("test_period", ["2019-01-01", "2023-12-31"])
            warmup = parameters.get("warmup", 720)
            cv_fold = parameters.get("cv_fold", 1)
            algorithm = parameters.get(
                "algorithm",
                {
                    "name": "SCE_UA",
                    "random_seed": 1234,
                    "rep": 100,
                    "ngs": 30,
                    "kstop": 5,
                    "peps": 0.05,
                    "pcento": 0.05,
                },
            )
            loss = parameters.get(
                "loss", {"type": "time_series", "obj_func": "RMSE", "events": None}
            )
            param_range_file = parameters.get("param_range_file")

            # 设置结果目录
            if result_dir is None:
                result_dir = os.path.join(str(repo_path), "result")
            if result_dir.endswith(exp_name):
                result_dir = os.path.normpath(result_dir)
            else:
                result_dir = os.path.join(result_dir, exp_name)

            where_save = Path(result_dir)
            if not where_save.exists():
                os.makedirs(where_save, exist_ok=True)

            self.logger.info("开始准备训练和测试数据")
            train_and_test_data = cross_val_split_tsdata(
                data_type,
                data_dir,
                cv_fold,
                calibrate_period,
                test_period,
                periods,
                warmup,
                basin_ids,
            )

            self.logger.info("开始模型率定")
            if cv_fold <= 1:
                p_and_e, qobs = _get_pe_q_from_ts(train_and_test_data[0])
                if isinstance(p_and_e, str) or isinstance(qobs, str):
                    raise ValueError("输入数据应为numpy数组格式")
                calibrate_by_sceua(
                    basin_ids,
                    p_and_e.astype(np.float64),
                    qobs.astype(np.float64),
                    os.path.join(where_save, "sceua_gr_model"),
                    warmup,
                    model=model,
                    algorithm=algorithm,
                    loss=loss,
                    param_file=param_range_file,
                )
            else:
                for i in range(cv_fold):
                    train_data, test_data = train_and_test_data[i]
                    p_and_e_cv, qobs_cv = _get_pe_q_from_ts(train_data)
                    model_save_dir = os.path.join(where_save, f"sceua_gr_model_cv{i+1}")
                    calibrate_by_sceua(
                        basin_ids,
                        p_and_e_cv,
                        qobs_cv,
                        model_save_dir,
                        warmup,
                        model=model,
                        algorithm=algorithm,
                        loss=loss,
                        param_file=param_range_file,
                    )

            # 保存配置文件
            args_dict = {
                "data_type": data_type,
                "data_dir": data_dir,
                "result_dir": str(where_save),
                "exp_name": exp_name,
                "model": model,
                "basin_ids": basin_ids,
                "periods": periods,
                "calibrate_period": calibrate_period,
                "test_period": test_period,
                "warmup": warmup,
                "cv_fold": cv_fold,
                "algorithm": algorithm,
                "loss": loss,
                "param_range_file": param_range_file,
            }
            with open(os.path.join(where_save, "config.yaml"), "w") as f:
                yaml.dump(args_dict, f)

            # 复制参数文件
            if param_range_file is None:
                param_range_file = os.path.join(where_save, "param_range.yaml")
                with open(param_range_file, "w") as f:
                    yaml.dump(MODEL_PARAM_DICT, f)
            else:
                dest_param_file = os.path.join(
                    where_save, os.path.basename(param_range_file)
                )
                if param_range_file != dest_param_file:
                    import shutil

                    shutil.copy(param_range_file, dest_param_file)

            output = {
                "status": "success",
                "message": "模型率定完成",
                "result_dir": str(where_save),
                "exp_name": exp_name,
                "model_name": model.get("name", "unknown"),
                "basin_count": len(basin_ids),
                "cv_fold": cv_fold,
            }

            self.logger.info(f"模型率定成功完成，结果保存至: {where_save}")
            return self._create_success_result(output)

        except Exception as e:
            import traceback

            error_trace = traceback.format_exc()
            error_msg = f"模型率定失败: {str(e)}"
            self.logger.error(f"{error_msg}\n{error_trace}")
            return self._create_error_result(error_msg)

"""
Author: zhuanglaihong
Date: 2024-09-26 16:30:00
LastEditTime: 2024-09-26 16:30:00
LastEditors: zhuanglaihong
Description: 水文模型评估工具
FilePath: \HydroAgent\executor\tools\evaluate_model_tool.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import sys
import os
import yaml
import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional
import logging

# 添加项目根路径
repo_path = Path(os.path.abspath(__file__)).parent.parent.parent
sys.path.append(str(repo_path))

from .base_tool import BaseTool, ToolResult

# 尝试导入水文模型模块
try:
    from hydromodel.trainers.evaluate import Evaluator, read_yaml_config
    from hydromodel.datasets.data_preprocess import cross_val_split_tsdata
    HYDROMODEL_AVAILABLE = True
except ImportError as e:
    logging.warning(f"水文模型模块导入失败: {e}")
    HYDROMODEL_AVAILABLE = False


class EvaluateModelTool(BaseTool):
    """水文模型评估工具"""

    def __init__(self):
        super().__init__(
            name="evaluate_model",
            description="评估已率定的水文模型性能，计算训练期和测试期的评估指标"
        )

    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """验证输入参数"""
        try:
            # 检查必需参数
            if "result_dir" not in parameters:
                self.logger.error("缺少必需参数: result_dir")
                return False

            # 检查结果目录是否存在
            result_dir = parameters["result_dir"]
            if not os.path.exists(result_dir):
                self.logger.error(f"结果目录不存在: {result_dir}")
                return False

            # 检查配置文件是否存在
            config_path = os.path.join(result_dir, "config.yaml")
            if not os.path.exists(config_path):
                self.logger.error(f"配置文件不存在: {config_path}")
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
                "result_dir": {
                    "type": "string",
                    "description": "率定结果保存目录，应包含config.yaml配置文件"
                },
                "exp_name": {
                    "type": "string",
                    "description": "实验名称",
                    "default": "exp_evaluation"
                },
                "cv_fold": {
                    "type": "integer",
                    "description": "交叉验证折数，如果不提供则从config.yaml读取",
                    "default": None
                }
            },
            "required": ["result_dir"],
            "additionalProperties": False
        }

    def _evaluate(self, cali_dir: str, param_dir: str, train_data, test_data) -> None:
        """执行评估"""
        eval_train_dir = os.path.join(param_dir, "train")
        eval_test_dir = os.path.join(param_dir, "test")

        train_eval = Evaluator(cali_dir, param_dir, eval_train_dir)
        test_eval = Evaluator(cali_dir, param_dir, eval_test_dir)

        qsim_train, qobs_train, etsim_train = train_eval.predict(train_data)
        qsim_test, qobs_test, etsim_test = test_eval.predict(test_data)

        train_eval.save_results(train_data, qsim_train, qobs_train, etsim_train)
        test_eval.save_results(test_data, qsim_test, qobs_test, etsim_test)

    def _read_r2_score(self, csv_path: str) -> Optional[float]:
        """读取R2分数"""
        try:
            df = pd.read_csv(csv_path)
            return df.loc[0, "R2"]
        except (FileNotFoundError, KeyError, pd.errors.EmptyDataError) as e:
            self.logger.error(f"读取指标文件失败: {str(e)}")
            return None

    def _read_metrics(self, csv_path: str) -> Dict[str, float]:
        """读取所有评估指标"""
        try:
            df = pd.read_csv(csv_path)
            metrics = {}
            if not df.empty:
                for col in df.columns:
                    if col != 'basin_id':  # 跳过流域ID列
                        metrics[col] = float(df.loc[0, col])
            return metrics
        except (FileNotFoundError, KeyError, pd.errors.EmptyDataError) as e:
            self.logger.error(f"读取指标文件失败: {str(e)}")
            return {}

    def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """执行模型评估"""
        if not HYDROMODEL_AVAILABLE:
            return self._create_error_result(
                "水文模型模块不可用，请检查 hydromodel 依赖安装"
            )

        try:
            result_dir = parameters["result_dir"]
            exp_name = parameters.get("exp_name", "exp_evaluation")

            where_save = Path(result_dir)

            # 读取配置文件
            config_path = os.path.join(result_dir, "config.yaml")
            cali_config = read_yaml_config(config_path)

            # 从配置获取必要参数
            data_type = cali_config.get("data_type")
            data_dir = cali_config.get("data_dir")
            cv_fold = parameters.get("cv_fold") or cali_config.get("cv_fold", 1)
            train_period = cali_config.get("calibrate_period")
            test_period = cali_config.get("test_period")
            periods = cali_config.get("periods") or cali_config.get("period")
            warmup = cali_config.get("warmup", 720)
            basin_ids = cali_config.get("basin_ids") or cali_config.get("basin_id")

            self.logger.info("开始准备评估数据")
            train_and_test_data = cross_val_split_tsdata(
                data_type,
                data_dir,
                cv_fold,
                train_period,
                test_period,
                periods,
                warmup,
                basin_ids,
            )

            self.logger.info("开始模型评估")
            if cv_fold <= 1:
                cali_dir = where_save
                param_dir = os.path.join(cali_dir, "sceua_gr_model")
                train_data = train_and_test_data[0]
                test_data = train_and_test_data[1]
                self._evaluate(cali_dir, param_dir, train_data, test_data)
            else:
                for i in range(cv_fold):
                    cali_dir = where_save
                    fold_dir = os.path.join(cali_dir, f"sceua_gr_model_cv{i+1}")
                    train_data = train_and_test_data[i][0]
                    test_data = train_and_test_data[i][1]
                    self._evaluate(cali_dir, fold_dir, train_data, test_data)

            # 读取评估指标
            evaluation_results = {}

            if cv_fold <= 1:
                param_dir = os.path.join(where_save, "sceua_gr_model")
                train_metrics_path = os.path.join(param_dir, "train", "basins_metrics.csv")
                test_metrics_path = os.path.join(param_dir, "test", "basins_metrics.csv")

                train_metrics = self._read_metrics(train_metrics_path)
                test_metrics = self._read_metrics(test_metrics_path)

                evaluation_results = {
                    "train_metrics": train_metrics,
                    "test_metrics": test_metrics,
                    "train_R2": train_metrics.get("R2"),
                    "test_R2": test_metrics.get("R2")
                }
            else:
                # 对于交叉验证，可以计算平均指标
                fold_results = []
                for i in range(cv_fold):
                    fold_dir = os.path.join(where_save, f"sceua_gr_model_cv{i+1}")
                    train_metrics_path = os.path.join(fold_dir, "train", "basins_metrics.csv")
                    test_metrics_path = os.path.join(fold_dir, "test", "basins_metrics.csv")

                    train_metrics = self._read_metrics(train_metrics_path)
                    test_metrics = self._read_metrics(test_metrics_path)

                    fold_results.append({
                        "fold": i + 1,
                        "train_metrics": train_metrics,
                        "test_metrics": test_metrics
                    })

                evaluation_results["cv_results"] = fold_results
                evaluation_results["cv_fold"] = cv_fold

            output = {
                "status": "success",
                "message": "模型评估完成",
                "result_dir": str(where_save),
                "exp_name": exp_name,
                "cv_fold": cv_fold,
                "evaluation_results": evaluation_results
            }

            # 添加简化的评估信息用于快速查看
            evl_info = {}
            if cv_fold <= 1:
                train_r2 = evaluation_results.get("train_R2")
                test_r2 = evaluation_results.get("test_R2")
                evl_info = {
                    "训练期R2": f"{round(train_r2, 4)}" if train_r2 is not None else "N/A",
                    "测试期R2": f"{round(test_r2, 4)}" if test_r2 is not None else "N/A",
                }
            else:
                evl_info["交叉验证折数"] = cv_fold
                evl_info["详细结果"] = "请查看evaluation_results.cv_results"

            output["evl_info"] = evl_info

            self.logger.info(f"模型评估成功完成")
            return self._create_success_result(output)

        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            error_msg = f"模型评估失败: {str(e)}"
            self.logger.error(f"{error_msg}\n{error_trace}")
            return self._create_error_result(error_msg)
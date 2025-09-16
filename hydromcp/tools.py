"""
水文模型MCP工具实现
"""

import sys
import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

# 添加项目根路径
repo_path = Path(__file__).parent.parent
sys.path.append(str(repo_path))

# 导入自定义路径
from definitions import DATASET_DIR, RESULT_DIR, PARAM_RANGE_FILE

logger = logging.getLogger(__name__)


class HydroModelMCPTools:
    """水文模型MCP工具实现类"""
    
    def __init__(self):
        """初始化工具"""
        self._import_hydromodel()
        
    def _import_hydromodel(self):
        """导入水文模型相关模块"""
        try:
            from hydromodel.models.model_dict import MODEL_DICT
            from hydromodel.models.model_config import MODEL_PARAM_DICT
            from hydromodel.datasets.data_preprocess import (
                cross_val_split_tsdata,
                _get_pe_q_from_ts,
                process_and_save_data_as_nc,
            )
            from hydromodel.trainers.calibrate_sceua import calibrate_by_sceua
            from hydromodel.trainers.evaluate import Evaluator, read_yaml_config
            import numpy as np
            import pandas as pd
            import yaml
            
            # 存储为实例属性
            self.MODEL_DICT = MODEL_DICT
            self.MODEL_PARAM_DICT = MODEL_PARAM_DICT
            self.cross_val_split_tsdata = cross_val_split_tsdata
            self._get_pe_q_from_ts = _get_pe_q_from_ts
            self.process_and_save_data_as_nc = process_and_save_data_as_nc
            self.calibrate_by_sceua = calibrate_by_sceua
            self.Evaluator = Evaluator
            self.read_yaml_config = read_yaml_config
            self.np = np
            self.pd = pd
            self.yaml = yaml
            
            self.hydromodel_available = True
            logger.info("水文模型模块导入成功")
            
        except ImportError as e:
            logger.error(f"水文模型模块导入失败: {e}")
            self.hydromodel_available = False
            
    def get_model_params(self, model_name: str) -> Dict[str, Any]:
        """
        获取模型参数信息
        
        Args:
            model_name: 模型名称
            
        Returns:
            包含参数信息的字典
        """
        if not self.hydromodel_available:
            return {
                "success": False,
                "error": "水文模型模块不可用，请检查依赖安装"
            }
            
        try:
            if model_name not in self.MODEL_PARAM_DICT:
                return {
                    "success": False,
                    "error": f"不支持的模型 {model_name}",
                    "supported_models": list(self.MODEL_PARAM_DICT.keys())
                }

            param_info = self.MODEL_PARAM_DICT[model_name]
            return {
                "success": True,
                "model_name": model_name,
                "param_names": param_info["param_name"],
                "param_ranges": param_info["param_range"],
                "param_count": len(param_info["param_name"])
            }
            
        except Exception as e:
            logger.error(f"获取模型参数失败: {e}")
            return {
                "success": False,
                "error": f"获取模型参数失败: {str(e)}"
            }
    
    def prepare_data(self, data_dir: str, target_data_scale: str = "D") -> Dict[str, Any]:
        """
        准备水文数据
        
        Args:
            data_dir: 数据目录路径
            target_data_scale: 数据时间尺度
            
        Returns:
            处理状态信息
        """
        if not self.hydromodel_available:
            return {
                "success": False,
                "error": "水文模型模块不可用，请检查依赖安装"
            }
            
        try:
            if not os.path.exists(data_dir):
                return {
                    "success": False,
                    "error": f"数据目录不存在: {data_dir}"
                }

            # 处理数据并保存为nc格式
            success = self.process_and_save_data_as_nc(
                data_dir, target_data_scale, save_folder=data_dir
            )
            
            if success:
                return {
                    "success": True,
                    "message": "数据准备完成，已转换为nc格式",
                    "data_dir": data_dir,
                    "data_scale": target_data_scale
                }
            else:
                return {
                    "success": False,
                    "error": "数据准备失败，请检查数据格式"
                }

        except Exception as e:
            logger.error(f"数据准备失败: {e}")
            return {
                "success": False,
                "error": f"数据准备失败: {str(e)}"
            }
    
    def calibrate_model(
        self,
        model_name: str,
        data_dir: str,
        data_type: str = "owndata",
        exp_name: str = "model_calibration",
        result_dir: Optional[str] = None,
        basin_ids: List[str] = None,
        calibrate_period: List[str] = None,
        test_period: List[str] = None,
        warmup: int = 720,
        cv_fold: int = 1
    ) -> Dict[str, Any]:
        """
        率定水文模型
        
        Args:
            model_name: 模型名称
            data_dir: 数据目录
            data_type: 数据类型
            exp_name: 实验名称
            result_dir: 结果保存目录
            basin_ids: 流域ID列表
            calibrate_period: 率定时间段
            test_period: 测试时间段
            warmup: 预热期长度
            cv_fold: 交叉验证折数
            
        Returns:
            率定结果信息
        """
        if not self.hydromodel_available:
            return {
                "success": False,
                "error": "水文模型模块不可用，请检查依赖安装"
            }
            
        try:
            # 设置默认参数
            if result_dir is None:
                result_dir = str(repo_path / "result")
            if basin_ids is None:
                basin_ids = ["11532500"]
            if calibrate_period is None:
                calibrate_period = ["2013-01-01", "2018-12-31"]
            if test_period is None:
                test_period = ["2019-01-01", "2023-12-31"]
                
            # 设置结果目录
            if result_dir.endswith(exp_name):
                result_dir = os.path.normpath(result_dir)
            else:
                result_dir = os.path.join(result_dir, exp_name)

            where_save = Path(result_dir)
            if not where_save.exists():
                os.makedirs(where_save, exist_ok=True)

            # 模型配置
            model = {
                "name": model_name,
                "source_type": "sources",
                "source_book": "HF",
                "kernel_size": 15,
                "time_interval_hours": 24,
            }

            # 算法配置
            algorithm = {
                "name": "SCE_UA",
                "random_seed": 1234,
                "rep": 100,
                "ngs": 30,
                "kstop": 5,
                "peps": 0.05,
                "pcento": 0.05,
            }

            # 损失函数配置
            loss = {
                "type": "time_series",
                "obj_func": "RMSE",
                "events": None,
            }

            # 计算完整时间段
            periods = [calibrate_period[0], test_period[1]]

            # 准备训练和测试数据
            train_and_test_data = self.cross_val_split_tsdata(
                data_type,
                data_dir,
                cv_fold,
                calibrate_period,
                test_period,
                periods,
                warmup,
                basin_ids,
            )

            logger.info(f"开始率定模型 {model_name}")

            if cv_fold <= 1:
                p_and_e, qobs = self._get_pe_q_from_ts(train_and_test_data[0])
                if isinstance(p_and_e, str) or isinstance(qobs, str):
                    raise ValueError("输入数据应为numpy数组格式")

                self.calibrate_by_sceua(
                    basin_ids,
                    p_and_e.astype(self.np.float64),
                    qobs.astype(self.np.float64),
                    os.path.join(where_save, "sceua_gr_model"),
                    warmup,
                    model=model,
                    algorithm=algorithm,
                    loss=loss,
                    param_file=PARAM_RANGE_FILE,
                )
            else:
                for i in range(cv_fold):
                    train_data, test_data = train_and_test_data[i]
                    p_and_e_cv, qobs_cv = self._get_pe_q_from_ts(train_data)
                    model_save_dir = os.path.join(where_save, f"sceua_gr_model_cv{i+1}")
                    self.calibrate_by_sceua(
                        basin_ids,
                        p_and_e_cv,
                        qobs_cv,
                        model_save_dir,
                        warmup,
                        model=model,
                        algorithm=algorithm,
                        loss=loss,
                        param_file=PARAM_RANGE_FILE,
                    )

            # 保存配置
            config = {
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
                "param_range_file": PARAM_RANGE_FILE,
            }

            with open(os.path.join(where_save, "config.yaml"), "w") as f:
                self.yaml.dump(config, f)

            return {
                "success": True,
                "message": f"模型 {model_name} 率定完成",
                "result_dir": str(where_save),
                "exp_name": exp_name,
                "model_name": model_name
            }

        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"模型率定失败: {e}")
            return {
                "success": False,
                "error": f"模型率定失败: {str(e)}",
                "error_stack": error_trace,
            }
    
    def evaluate_model(
        self,
        result_dir: str,
        exp_name: str = "model_calibration", 
        model_name: str = "gr4j",
        cv_fold: int = 1
    ) -> Dict[str, Any]:
        """
        评估水文模型
        
        Args:
            result_dir: 率定结果保存目录
            exp_name: 实验名称
            model_name: 模型名称
            cv_fold: 交叉验证折数
            
        Returns:
            评估结果信息
        """
        if not self.hydromodel_available:
            return {
                "success": False,
                "error": "水文模型模块不可用，请检查依赖安装"
            }
            
        try:
            where_save = Path(result_dir) / exp_name

            # 读取配置
            config_path = os.path.join(where_save, "config.yaml")
            if not os.path.exists(config_path):
                return {
                    "success": False,
                    "error": f"配置文件不存在: {config_path}"
                }
                
            cali_config = self.read_yaml_config(config_path)

            data_type = cali_config.get("data_type")
            data_dir = cali_config.get("data_dir")
            cv_fold = cali_config.get("cv_fold", 1)
            train_period = cali_config.get("calibrate_period")
            test_period = cali_config.get("test_period")
            periods = cali_config.get("periods") or cali_config.get("period")
            warmup = cali_config.get("warmup", 720)
            basin_ids = cali_config.get("basin_ids") or cali_config.get("basin_id")

            # 准备训练和测试数据
            train_and_test_data = self.cross_val_split_tsdata(
                data_type,
                data_dir,
                cv_fold,
                train_period,
                test_period,
                periods,
                warmup,
                basin_ids,
            )

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

            # 读取R2分数
            if cv_fold <= 1:
                param_dir = os.path.join(where_save, "sceua_gr_model")
                train_r2 = self._read_r2_score(
                    os.path.join(param_dir, "train", "basins_metrics.csv")
                )
                test_r2 = self._read_r2_score(
                    os.path.join(param_dir, "test", "basins_metrics.csv")
                )
            else:
                train_r2 = test_r2 = None

            return {
                "success": True,
                "message": f"模型 {model_name} 评估完成",
                "model_name": model_name,
                "exp_name": exp_name,
                "metrics": {
                    "训练期R2": f"{round(train_r2, 4)}" if train_r2 is not None else "N/A",
                    "测试期R2": f"{round(test_r2, 4)}" if test_r2 is not None else "N/A",
                },
            }

        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"模型评估失败: {e}")
            return {
                "success": False,
                "error": f"模型评估失败: {str(e)}",
                "error_stack": error_trace,
            }
    
    def _evaluate(self, cali_dir: str, param_dir: str, train_data: Any, test_data: Any):
        """评估模型"""
        eval_train_dir = os.path.join(param_dir, "train")
        eval_test_dir = os.path.join(param_dir, "test")
        train_eval = self.Evaluator(cali_dir, param_dir, eval_train_dir)
        test_eval = self.Evaluator(cali_dir, param_dir, eval_test_dir)
        qsim_train, qobs_train, etsim_train = train_eval.predict(train_data)
        qsim_test, qobs_test, etsim_test = test_eval.predict(test_data)
        train_eval.save_results(train_data, qsim_train, qobs_train, etsim_train)
        test_eval.save_results(test_data, qsim_test, qobs_test, etsim_test)

    def _read_r2_score(self, csv_path: str) -> Optional[float]:
        """读取R2分数"""
        try:
            df = self.pd.read_csv(csv_path)
            return df.loc[0, "R2"]
        except (FileNotFoundError, KeyError, self.pd.errors.EmptyDataError) as e:
            logger.error(f"读取指标文件失败: {str(e)}")
            return None

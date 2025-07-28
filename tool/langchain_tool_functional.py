"""
Author: zhuanglaihong
Date: 2025-02-21 14:54:24
LastEditTime: 2025-02-26 16:24:08
LastEditors: zhuanglaihong
Description: 水文模型 LangChain 工具 - 函数式版本
FilePath: tool/langchain_tool_functional.py
Copyright: Copyright (c) 2021-2024 zhuanglaihong. All rights reserved.
"""

import sys
import os
import yaml
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

repo_path = Path(os.path.abspath(__file__)).parent.parent  # 获取两次父路径
sys.path.append(str(repo_path))  # 添加项目根路径

# 导入自定义路径
from definitions import DATASET_DIR, RESULT_DIR, PARAM_RANGE_FILE

from langchain.tools import BaseTool
from langchain_core.tools import tool
from pydantic import BaseModel, Field
import pandas as pd

# 导入水文模型相关模块
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

    HYDROMODEL_AVAILABLE = True
except ImportError as e:
    logging.warning(f"水文模型模块导入失败: {e}")
    HYDROMODEL_AVAILABLE = False

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ModelParamsInput(BaseModel):
    """获取模型参数的输入模型"""

    model_name: str = Field(description="模型名称，如 'gr4j', 'xaj', 'sac-sma' 等")


class PrepareDataInput(BaseModel):
    """准备数据的输入模型"""

    data_dir: str = Field(default=DATASET_DIR, description="数据目录路径")
    target_data_scale: str = Field(
        default="D",
        description="数据时间尺度，默认为日尺度('D')，可选'M'(月尺度)或'Y'(年尺度)",
    )


class CalibrateModelInput(BaseModel):
    """率定模型的输入模型"""

    data_type: str = Field(default="owndata", description="数据类型")
    data_dir: str = Field(default=DATASET_DIR, description="数据目录")
    result_dir: Optional[str] = Field(default=None, description="结果保存目录")
    exp_name: str = Field(default="exp_11532500", description="实验名称")
    model_name: str = Field(default="gr4j", description="模型名称")
    basin_ids: List[str] = Field(default=["11532500"], description="流域ID列表")
    periods: List[str] = Field(
        default=["2013-01-01", "2023-12-31"],
        description="整个时间段 [start_date, end_date]",
    )
    calibrate_period: List[str] = Field(
        default=["2013-01-01", "2018-12-31"],
        description="率定时间段 [start_date, end_date]",
    )
    test_period: List[str] = Field(
        default=["2019-01-01", "2023-12-31"],
        description="测试时间段 [start_date, end_date]",
    )
    warmup: int = Field(default=720, description="预热期长度")
    cv_fold: int = Field(default=1, description="交叉验证折数")


class EvaluateModelInput(BaseModel):
    """评估模型的输入模型"""

    result_dir: str = Field(description="率定结果保存目录")
    exp_name: str = Field(default="exp_11532500", description="实验名称")
    cv_fold: int = Field(default=1, description="交叉验证折数")


def _read_r2_score(csv_path: str) -> Optional[float]:
    """读取R2分数"""
    try:
        df = pd.read_csv(csv_path)
        return df.loc[0, "R2"]
    except (FileNotFoundError, KeyError, pd.errors.EmptyDataError) as e:
        logger.error(f"读取指标文件失败: {str(e)}")
        return None


def _evaluate(cali_dir: str, param_dir: str, train_data: Any, test_data: Any):
    """评估模型"""
    eval_train_dir = os.path.join(param_dir, "train")
    eval_test_dir = os.path.join(param_dir, "test")
    train_eval = Evaluator(cali_dir, param_dir, eval_train_dir)
    test_eval = Evaluator(cali_dir, param_dir, eval_test_dir)
    qsim_train, qobs_train, etsim_train = train_eval.predict(train_data)
    qsim_test, qobs_test, etsim_test = test_eval.predict(test_data)
    train_eval.save_results(train_data, qsim_train, qobs_train, etsim_train)
    test_eval.save_results(test_data, qsim_test, qobs_test, etsim_test)


# 函数式工具定义
@tool("get_model_params", args_schema=ModelParamsInput)
def get_model_params(model_name: str) -> Dict[str, Any]:
    """
    获取模型参数信息

    Args:
        model_name: 模型名称，如 'gr4j', 'xaj', 'sac-sma' 等

    Returns:
        包含参数名称和范围的字典
    """
    if not HYDROMODEL_AVAILABLE:
        return {"error": "水文模型模块不可用"}

    if model_name not in MODEL_PARAM_DICT:
        return {"error": f"不支持的模型 {model_name}"}

    param_info = MODEL_PARAM_DICT[model_name]
    return {
        "model_name": model_name,
        "param_names": param_info["param_name"],
        "param_ranges": param_info["param_range"],
    }


@tool("prepare_data", args_schema=PrepareDataInput)
def prepare_data(
    data_dir: str = DATASET_DIR, target_data_scale: str = "D"
) -> Dict[str, str]:
    """
    准备水文数据

    Args:
        data_dir: 数据目录路径
        target_data_scale: 数据时间尺度

    Returns:
        处理状态信息
    """
    if not HYDROMODEL_AVAILABLE:
        return {"status": "error", "message": "水文模型模块不可用"}

    try:
        if not os.path.exists(data_dir):
            return {"status": "error", "message": f"数据目录不存在: {data_dir}"}

        if process_and_save_data_as_nc(
            data_dir, target_data_scale, save_folder=data_dir
        ):
            return {"status": "success", "message": "数据准备完成，已转换为nc格式"}
        else:
            return {"status": "error", "message": "数据准备失败，请检查数据格式"}

    except Exception as e:
        return {"status": "error", "message": f"数据准备失败: {str(e)}"}


@tool("calibrate_model", args_schema=CalibrateModelInput)
def calibrate_model(
    data_type: str = "owndata",
    data_dir: str = DATASET_DIR,
    result_dir: Optional[str] = None,
    exp_name: str = "exp_11532500",
    model_name: str = "gr4j",
    basin_ids: List[str] = ["11532500"],
    periods: List[str] = ["2013-01-01", "2023-12-31"],
    calibrate_period: List[str] = ["2013-01-01", "2018-12-31"],
    test_period: List[str] = ["2019-01-01", "2023-12-31"],
    warmup: int = 720,
    cv_fold: int = 1,
) -> Dict[str, Any]:
    """
    率定水文模型

    Args:
        data_type: 数据类型
        data_dir: 数据目录
        result_dir: 结果保存目录
        exp_name: 实验名称
        model_name: 模型名称
        basin_ids: 流域ID列表
        periods: 整个时间段
        calibrate_period: 率定时间段
        test_period: 测试时间段
        warmup: 预热期长度
        cv_fold: 交叉验证折数

    Returns:
        率定结果信息
    """
    if not HYDROMODEL_AVAILABLE:
        return {"status": "error", "message": "水文模型模块不可用"}

    try:
        # 设置默认结果目录
        if result_dir is None:
            result_dir = RESULT_DIR
        if result_dir.endswith(exp_name):
            result_dir = os.path.normpath(result_dir)
        else:
            result_dir = os.path.join(result_dir, exp_name)

        where_save = Path(result_dir) / exp_name
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

        # 参数范围文件
        param_range_file = PARAM_RANGE_FILE

        # 准备训练和测试数据
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

        logger.info("开始率定模型")

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

        # 保存配置
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

        return {
            "status": "success",
            "message": "模型率定完成",
            "result_dir": str(where_save),
        }

    except Exception as e:
        import traceback

        error_trace = traceback.format_exc()
        return {
            "status": "error",
            "message": f"模型率定失败: {str(e)}",
            "error_stack": error_trace,
        }


@tool("evaluate_model", args_schema=EvaluateModelInput)
def evaluate_model(
    result_dir: str, exp_name: str = "exp_11532500", cv_fold: int = 1
) -> Dict[str, Any]:
    """
    评估水文模型

    Args:
        result_dir: 率定结果保存目录
        exp_name: 实验名称
        cv_fold: 交叉验证折数

    Returns:
        评估结果信息
    """
    if not HYDROMODEL_AVAILABLE:
        return {"status": "error", "message": "水文模型模块不可用"}

    try:
        where_save = Path(result_dir) / exp_name

        # 读取配置
        config_path = os.path.join(result_dir, "config.yaml")
        cali_config = read_yaml_config(config_path)

        data_type = cali_config.get("data_type")
        data_dir = cali_config.get("data_dir")
        cv_fold = cali_config.get("cv_fold", 1)
        train_period = cali_config.get("calibrate_period")
        test_period = cali_config.get("test_period")
        periods = cali_config.get("periods") or cali_config.get("period")
        warmup = cali_config.get("warmup", 720)
        basin_ids = cali_config.get("basin_ids") or cali_config.get("basin_id")

        # 准备训练和测试数据
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

        if cv_fold <= 1:
            cali_dir = where_save
            param_dir = os.path.join(cali_dir, "sceua_gr_model")
            train_data = train_and_test_data[0]
            test_data = train_and_test_data[1]
            _evaluate(cali_dir, param_dir, train_data, test_data)
        else:
            for i in range(cv_fold):
                cali_dir = where_save
                fold_dir = os.path.join(cali_dir, f"sceua_gr_model_cv{i+1}")
                train_data = train_and_test_data[i][0]
                test_data = train_and_test_data[i][1]
                _evaluate(cali_dir, fold_dir, train_data, test_data)

        # 读取R2分数
        if cv_fold <= 1:
            param_dir = os.path.join(where_save, "sceua_gr_model")
            train_r2 = _read_r2_score(
                os.path.join(param_dir, "train", "basins_metrics.csv")
            )
            test_r2 = _read_r2_score(
                os.path.join(param_dir, "test", "basins_metrics.csv")
            )
        else:
            train_r2 = test_r2 = None

        return {
            "status": "success",
            "message": "模型评估完成",
            "evl_info": {
                "训练期R2": f"{round(train_r2, 4)}" if train_r2 is not None else "N/A",
                "测试期R2": f"{round(test_r2, 4)}" if test_r2 is not None else "N/A",
            },
        }

    except Exception as e:
        import traceback

        error_trace = traceback.format_exc()
        return {
            "status": "error",
            "message": f"模型评估失败: {str(e)}",
            "error_stack": error_trace,
        }


def get_hydromodel_tools_functional() -> List[BaseTool]:
    """
    获取水文模型工具列表（函数式版本）

    Returns:
        LangChain 工具列表
    """
    if not HYDROMODEL_AVAILABLE:
        logger.warning("水文模型模块不可用，返回空工具列表")
        return []

    return [
        get_model_params,
        prepare_data,
        calibrate_model,
        evaluate_model,
    ]


if __name__ == "__main__":
    # 测试工具
    tools = get_hydromodel_tools_functional()
    print(f"可用工具数量: {len(tools)}")

    for tool in tools:
        print(f"工具: {tool.name}")
        print(f"描述: {tool.description}")
        print("---")

    # 直接定义函数，类似MCP工具，不需要实例化对象
    # 对比类方法，逻辑简单，适用于原型开发

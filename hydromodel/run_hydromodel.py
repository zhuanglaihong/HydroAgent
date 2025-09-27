import httpx
from mcp.server.fastmcp import FastMCP
import sys
import os
import yaml
from pathlib import Path
import pandas as pd

# 添加hydromodel到Python路径
repo_path = Path(os.path.abspath(__file__)).parent.parent
sys.path.append(repo_path)

import logging
from hydromodel.models.model_dict import MODEL_DICT
from hydromodel.models.model_config import MODEL_PARAM_DICT
from hydromodel.datasets.data_preprocess import (
    cross_val_split_tsdata,
    _get_pe_q_from_ts,
    check_tsdata_format,
    check_basin_attr_format,
    check_folder_contents,
    process_and_save_data_as_nc,
)
from hydromodel.trainers.calibrate_sceua import calibrate_by_sceua
import numpy as np
from hydromodel.datasets import *
from hydromodel.trainers.evaluate import Evaluator
from hydromodel.trainers.evaluate import read_yaml_config
from hydromodel.datasets.data_preprocess import cross_val_split_tsdata
        

mcp = FastMCP("run_hydromodel", description="率定水文模型")

logging.basicConfig(level=logging.DEBUG)

def _evaluate(cali_dir, param_dir, train_data, test_data):
    eval_train_dir = os.path.join(param_dir, "train")
    eval_test_dir = os.path.join(param_dir, "test")
    train_eval = Evaluator(cali_dir, param_dir, eval_train_dir)
    test_eval = Evaluator(cali_dir, param_dir, eval_test_dir)
    qsim_train, qobs_train, etsim_train = train_eval.predict(train_data)
    qsim_test, qobs_test, etsim_test = test_eval.predict(test_data)
    train_eval.save_results(train_data, qsim_train, qobs_train, etsim_train)
    test_eval.save_results(test_data, qsim_test, qobs_test, etsim_test)


def _read_r2_score(csv_path):
    try:
        df = pd.read_csv(csv_path)
        return df.loc[0, "R2"]
    except (FileNotFoundError, KeyError, pd.errors.EmptyDataError) as e:
        logging.error(f"读取指标文件失败: {str(e)}")
        return None


@mcp.tool()
async def get_model_params(model_name: str):
    """
    获取模型参数信息

    Args:
        model_name: 模型名称
    """
    if model_name not in MODEL_PARAM_DICT:
        return f"错误：不支持的模型 {model_name}"

    param_info = MODEL_PARAM_DICT[model_name]
    return {
        "param_names": param_info["param_name"],
        "param_ranges": param_info["param_range"],
    }


@mcp.tool()
async def prepare_data(
    data_dir: str = "D:\Project\MCP\hydromodel\data\camels_11532500",
    target_data_scale: str = "D",
):
    """
    准备水文数据

    Args:
        data_dir: 数据目录路径
        target_data_scale: 数据时间尺度,默认为日尺度("D"),可选"M"(月尺度)或"Y"(年尺度)
    """
    try:
        # 检查数据目录是否存在
        if not os.path.exists(data_dir):
            return {"status": "error", "message": f"数据目录不存在: {data_dir}"}

        # 处理并保存数据为nc格式
        if process_and_save_data_as_nc(
            data_dir, target_data_scale, save_folder=data_dir
        ):
            return {"status": "success", "message": "数据准备完成,已转换为nc格式"}
        else:
            return {"status": "error", "message": "数据准备失败,请检查数据格式"}

    except Exception as e:
        return {"status": "error", "message": f"数据准备失败: {str(e)}"}
@mcp.tool()
async def calibrate_model(
    data_type: str = "owndata",
    data_dir: str = "D:\\Project\\MCP\\hydromodel\\data\\camels_11532500",
    result_dir: str = None,
    exp_name: str = "exp_11532500",
    model: dict = {
        "name": "gr4j",
        "source_type": "sources",
        "source_book": "HF",
        "kernel_size": 15,
        "time_interval_hours": 24,
    },
    basin_ids: list = ["11532500"],
    periods: list = ["2000-01-01", "2023-12-31"],
    calibrate_period: list = ["2000-01-01", "2018-12-31"],
    test_period: list = ["2019-01-01", "2023-12-31"],
    warmup: int = 720,
    cv_fold: int = 1,
    algorithm: dict = {
        "name": "SCE_UA",
        "random_seed": 1234,
        "rep": 100,
        "ngs": 30,
        "kstop": 5,
        "peps": 0.05,
        "pcento": 0.05,
    },
    loss: dict = {
        "type": "time_series",
        "obj_func": "RMSE",
        "events": None,
    },
    param_range_file: str = "D:\\Project\\MCP\\hydromodel\\hydromodel\\models\\param.yaml",
):
    """
    率定水文模型

    Args:
        data_type: 数据类型,如 'camels' 或 'owndata'
        data_dir: 数据目录
        result_dir: 结果保存目录
        exp_name: 实验名称
        model: 模型配置字典
        basin_ids: 流域ID列表
        periods: 整个时间段 [start_date, end_date]
        calibrate_period: 率定时间段 [start_date, end_date]
        test_period: 测试时间段 [start_date, end_date]
        warmup: 预热期长度,默认720
        cv_fold: 交叉验证折数,默认1
        algorithm: 优化算法配置
        loss: 损失函数配置
        param_range_file: 参数范围配置文件路径

    Returns:
        dict: 包含率定状态、信息和结果目录的字典。例如：
            {
                "status": "success",
                "message": "模型率定完成",
                "result_dir": "..."
            }
        若发生异常,返回包含错误信息的字典。
    """
    try:
        if result_dir is None:
            result_dir = os.path.join(
                os.path.dirname(Path(os.path.abspath(__file__)).parent), "result"
            )
        if result_dir.endswith(exp_name):
            result_dir = os.path.normpath(result_dir)
        else:
            result_dir = os.path.join(result_dir, exp_name)
        where_save = Path(result_dir)
        if not where_save.exists():
            os.makedirs(where_save, exist_ok=True)
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
        logging.info("Start to calibrate the model")
        print(f"[DEBUG] 接收 Start to calibrate the model ")
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
        if param_range_file is None:
            param_range_file = os.path.join(where_save, "param_range.yaml")
            yaml.dump(MODEL_PARAM_DICT, open(param_range_file, "w"))
        else:
            dest_param_file = os.path.join(
                where_save, os.path.basename(param_range_file)
            )
            if param_range_file != dest_param_file:
                import shutil
                shutil.copy(param_range_file, dest_param_file)
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
@mcp.tool()
async def evaluate_model(
    result_dir: str,
    exp_name: str = "exp_11532500",
    cv_fold: int = 1,
    train_and_test_data=None,
    model: dict = None,
    param_range_file: str = None,
):
    """
    评估水文模型（输入为率定结果和测试数据）

    Args:
        result_dir: 率定结果保存目录,和calibrate_model函数返回结果一致
        exp_name: 实验名称,默认"exp_11532500"
        cv_fold: 交叉验证折数,默认1
        train_and_test_data:若为None,则自动从result_dir/config.yaml读取参数并生成。
        model: 模型配置字典（可选）
        param_range_file: 参数范围配置文件路径（可选）

    Returns:
        dict: 包含评估状态、信息和评估指标的字典。例如：
            {
                "status": "success",
                "message": "模型评估完成",
                "evl_info": {
                    "训练期R2": "...",
                    "测试期R2": "..."
                }
            }
        若发生异常,返回包含错误信息的字典。
    """
    try:
        
        where_save = Path(result_dir)
        # 自动补充train_and_test_data
        if train_and_test_data is None:
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
            train_r2 = _read_r2_score(os.path.join(param_dir, "train", "basins_metrics.csv"))
            test_r2 = _read_r2_score(os.path.join(param_dir, "test", "basins_metrics.csv"))
        else:
            train_r2 = test_r2 = None  # 可扩展为多折平均
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


if __name__ == "__main__":
    mcp.run(transport="stdio")

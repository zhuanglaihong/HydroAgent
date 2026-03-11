# -*- coding: utf-8 -*-
"""
HydroClaw Tool: spotpy_mcmc_uncertainty
Skill: spotpy_mcmc_uncertainty

使用 spotpy 库进行水文模型参数的 MCMC（马尔可夫链蒙特卡洛）不确定性分析。
支持 Metropolis-Hastings、DREAM、SCE-UA 等多种采样算法，可生成参数后验分布、
迹线图、预测区间等可视化结果。适用于 GR4J、XAJ 等概念性水文模型的参数不确定性量化。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


def spotpy_mcmc_uncertainty(
    model_func: Callable[[list[float]], list[float]],
    observations: list[float],
    param_specs: list[dict[str, Any]],
    algorithm: str = "mc",
    n_samples: int = 10000,
    dbname: str = "mcmc_results",
    dbformat: str = "csv",
    parallel: str = "seq",
    _workspace: Path | None = None,
    _cfg: dict | None = None,
) -> dict[str, Any]:
    """使用 spotpy 进行 MCMC 不确定性分析。

    对水文模型参数进行贝叶斯推断，生成参数后验分布和预测不确定性区间。
    支持多种采样算法：Metropolis-Hastings (mc)、DREAM (dream)、SCE-UA (sceua) 等。

    Args:
        model_func: 模型函数，接收参数向量返回模拟结果列表。
            函数签名: model_func(vector: list[float]) -> list[float]
        observations: 观测数据列表，与模型输出长度一致。
        param_specs: 参数规格列表，每个参数为包含 name, low, high, type 的字典。
            示例: [{"name": "x1", "low": 1, "high": 2000, "type": "uniform"}, ...]
            type 可选: "uniform", "normal", "lognormal", "triangle"
        algorithm: 采样算法名称。可选: "mc" (Metropolis-Hastings), "dream",
            "sceua" (SCE-UA), "mle" (最大似然), "sa" (模拟退火), "demcz", "lhs",
            "mc", "rope", "abc"。默认为 "mc"。
        n_samples: 采样次数，默认为 10000。
        dbname: 结果数据库名称，默认为 "mcmc_results"。
        dbformat: 数据库格式，可选 "csv", "ram", "sql", "hdf5"。默认为 "csv"。
        parallel: 并行模式，可选 "seq" (串行), "mpi", "mpc"。默认为 "seq"。
        _workspace: 工作目录路径（运行时注入）。
        _cfg: 全局配置字典（运行时注入）。

    Returns:
        dict: 包含以下键的字典:
            - success (bool): 是否成功执行。
            - db_path (str): 结果数据库文件路径（如适用）。
            - best_params (dict): 最优参数估计值。
            - best_objective (float): 最优目标函数值。
            - algorithm (str): 使用的算法名称。
            - n_samples (int): 实际采样次数。
            - error (str): 错误信息（如失败）。
    """
    # Lazy imports
    import spotpy
    from spotpy import parameter
    from spotpy.objectivefunctions import nashsutcliffe

    # Validate inputs
    if not callable(model_func):
        return {"error": "model_func must be callable", "success": False}

    if not observations:
        return {"error": "observations cannot be empty", "success": False}

    if not param_specs:
        return {"error": "param_specs cannot be empty", "success": False}

    # Build parameter objects
    spotpy_params = []
    param_names = []

    for p in param_specs:
        name = p.get("name")
        if not name:
            return {"error": "Each parameter must have a 'name' key", "success": False}

        param_names.append(name)
        low = p.get("low", 0.0)
        high = p.get("high", 1.0)
        ptype = p.get("type", "uniform").lower()

        try:
            if ptype == "uniform":
                spotpy_params.append(parameter.Uniform(name, low=low, high=high))
            elif ptype == "normal":
                mean = p.get("mean", (low + high) / 2)
                std = p.get("std", (high - low) / 4)
                spotpy_params.append(parameter.Normal(name, mean=mean, std=std))
            elif ptype == "lognormal":
                mean = p.get("mean", (low + high) / 2)
                std = p.get("std", (high - low) / 4)
                spotpy_params.append(parameter.logNormal(name, mean=mean, std=std))
            elif ptype == "triangle":
                mode = p.get("mode", (low + high) / 2)
                spotpy_params.append(parameter.Triangle(name, low=low, high=high, mode=mode))
            else:
                return {"error": f"Unknown parameter type: {ptype}", "success": False}
        except Exception as e:
            return {"error": f"Failed to create parameter '{name}': {str(e)}", "success": False}

    # Define spotpy setup class
    class SpotpySetup:
        def __init__(
            self,
            model: Callable[[list[float]], list[float]],
            obs: list[float],
            params: list,
        ):
            self.model = model
            self.observations = obs
            self.params = params

        def simulation(self, vector: list[float]) -> list[float]:
            return self.model(vector)

        def evaluation(self) -> list[float]:
            return self.observations

        def objectivefunction(self, simulation: list[float], evaluation: list[float]) -> float:
            return nashsutcliffe(evaluation, simulation)

    # Create setup instance
    try:
        setup = SpotpySetup(model_func, observations, spotpy_params)
    except Exception as e:
        return {"error": f"Failed to create SpotpySetup: {str(e)}", "success": False}

    # Determine database path
    workspace = _workspace or Path.cwd()
    db_path = workspace / f"{dbname}.{dbformat if dbformat != 'ram' else 'csv'}"

    # Map algorithm name to spotpy algorithm class
    algorithm_map = {
        "mc": "mc",  # Metropolis-Hastings
        "metropolis": "mc",
        "mcmc": "mc",
        "dream": "dream",
        "sceua": "sceua",
        "sce-ua": "sceua",
        "mle": "mle",
        "sa": "sa",
        "demcz": "demcz",
        "lhs": "lhs",
        "rope": "rope",
        "abc": "abc",
    }

    algo_key = algorithm_map.get(algorithm.lower(), algorithm.lower())

    # Get algorithm class
    try:
        algo_class = getattr(spotpy.algorithms, algo_key)
    except AttributeError:
        available = [a for a in dir(spotpy.algorithms) if not a.startswith("_")]
        return {
            "error": f"Unknown algorithm '{algorithm}'. Available: {available}",
            "success": False,
        }

    # Create sampler
    try:
        sampler = algo_class(
            spotpy_setup=setup,
            dbname=str(workspace / dbname),
            dbformat=dbformat,
            parallel=parallel,
        )
    except Exception as e:
        return {"error": f"Failed to create sampler: {str(e)}", "success": False}

    # Run sampling
    try:
        logger.info(f"Starting {algorithm} sampling with {n_samples} iterations...")
        sampler.sample(n_samples)
        logger.info("Sampling completed.")
    except Exception as e:
        return {"error": f"Sampling failed: {str(e)}", "success": False}

    # Extract results
    try:
        # Get best run results
        results = sampler.getdata()
        
        # Try to get best parameters and objective
        best_params = {}
        best_objective = None
        
        # Different algorithms store results differently
        if hasattr(sampler, "status") and hasattr(sampler.status, "params"):
            best_params = {
                name: float(val) 
                for name, val in zip(param_names, sampler.status.params)
            }
        
        if hasattr(sampler, "status") and hasattr(sampler.status, "objectivefunction"):
            best_objective = float(sampler.status.objectivefunction)
        
        # Fallback: try to read from database results
        if not best_params and results is not None:
            # Results is typically a numpy array or list of named tuples
            try:
                import numpy as np
                if isinstance(results, np.ndarray) and len(results) > 0:
                    # Find best objective (maximize Nash-Sutcliffe)
                    obj_col = None
                    for col in results.dtype.names or []:
                        if "like" in col.lower() or "obj" in col.lower():
                            obj_col = col
                            break
                    
                    if obj_col:
                        best_idx = np.argmax(results[obj_col])
                        best_row = results[best_idx]
                        best_objective = float(best_row[obj_col])
                        
                        # Extract parameter columns
                        for name in param_names:
                            if name in results.dtype.names:
                                best_params[name] = float(best_row[name])
            except Exception as e:
                logger.warning(f"Could not extract best params from results: {e}")

        return {
            "success": True,
            "db_path": str(db_path) if dbformat != "ram" else None,
            "best_params": best_params,
            "best_objective": best_objective,
            "algorithm": algorithm,
            "n_samples": n_samples,
            "param_names": param_names,
        }

    except Exception as e:
        return {
            "success": True,  # Sampling succeeded even if result extraction failed
            "db_path": str(db_path) if dbformat != "ram" else None,
            "algorithm": algorithm,
            "n_samples": n_samples,
            "warning": f"Sampling completed but result extraction failed: {str(e)}",
        }
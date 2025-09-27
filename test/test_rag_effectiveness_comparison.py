"""
Author: zhuanglaihong
Date: 2024-09-26 17:00:00
LastEditTime: 2024-09-26 17:00:00
LastEditors: zhuanglaihong
Description: RAG系统效果对比测试 - 验证RAG对复杂任务处理能力的增强效果
FilePath: \HydroAgent\test\test_rag_effectiveness_comparison.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import json
import sys
import time
import os
from pathlib import Path
from typing import Dict, List, Tuple, Any
from datetime import datetime
import argparse

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from builder import WorkflowBuilder
from utils.logger_config import TestLoggerContext, LoggerConfig


class RAGEffectivenessComparison:
    """RAG效果对比测试类"""

    def __init__(self, enable_logging: bool = True):
        self.project_root = project_root
        self.enable_logging = enable_logging
        self.results = {
            "test_session_id": f"rag_comparison_{int(time.time())}",
            "test_timestamp": datetime.now().isoformat(),
            "test_cases": [],
            "summary": {}
        }

    def get_complex_test_cases(self) -> List[Dict[str, Any]]:
        """定义复杂任务测试用例"""
        return [
            {
                "case_id": "complex_multi_basin_comparison",
                "name": "多流域模型比较分析",
                "description": "对3个不同流域同时进行GR4J和XAJ模型比较，要求并行处理和性能对比",
                "query": "我需要对长江、黄河、珠江三个流域分别用GR4J和XAJ模型进行率定，然后比较哪个模型在每个流域表现更好。要求并行处理以节省时间，并生成详细的性能对比报告。",
                "complexity_level": "高",
                "required_knowledge": [
                    "多流域并行处理工作流设计",
                    "GR4J和XAJ模型参数配置差异",
                    "模型比较评估方法",
                    "并行执行模式配置"
                ],
                "expected_workflow_features": [
                    "包含至少6个率定任务（3个流域 × 2个模型）",
                    "使用parallel执行模式",
                    "包含模型性能比较逻辑",
                    "合理的依赖关系设计",
                    "适当的超时和重试配置"
                ]
            },
            {
                "case_id": "complex_monthly_prediction_pipeline",
                "name": "月尺度预测管道设计",
                "description": "构建完整的月尺度径流预测管道，包括数据预处理、模型选择、率定和长期预测",
                "query": "帮我设计一个月尺度的径流预测系统，需要处理30年的历史数据，自动选择最适合的月尺度模型（GR2M或其他），进行率定后用于未来2年的径流预测。要考虑季节性变化和不确定性分析。",
                "complexity_level": "高",
                "required_knowledge": [
                    "月尺度模型选择原则",
                    "长期时序数据处理",
                    "季节性径流预测方法",
                    "不确定性分析配置"
                ],
                "expected_workflow_features": [
                    "包含月尺度数据预处理",
                    "模型参数获取和比较",
                    "合适的预热期设置（≥12个月）",
                    "长时间序列处理配置",
                    "预测评估指标"
                ]
            },
            {
                "case_id": "complex_cross_validation_analysis",
                "name": "交叉验证稳定性分析",
                "description": "使用5折交叉验证分析模型在不同时期的稳定性和泛化能力",
                "query": "我要评估GR4J模型在某个流域的稳定性，使用5折交叉验证方法，分析模型在不同时间段的表现差异。同时要进行敏感性分析，测试不同算法参数对结果的影响。",
                "complexity_level": "高",
                "required_knowledge": [
                    "交叉验证配置方法",
                    "模型稳定性评估指标",
                    "敏感性分析设计",
                    "算法参数优化策略"
                ],
                "expected_workflow_features": [
                    "cv_fold参数设置为5",
                    "多组算法参数测试",
                    "稳定性指标计算",
                    "敏感性分析流程",
                    "结果对比和评估"
                ]
            },
            {
                "case_id": "complex_automated_calibration_pipeline",
                "name": "自动化率定管道",
                "description": "设计一个全自动的模型率定管道，能够根据数据特征自动选择模型和优化参数",
                "query": "创建一个智能化的水文模型率定系统，能够自动分析输入数据的特征，选择最合适的模型（GR4J、XAJ或GR5J），自动配置算法参数，并在率定失败时自动尝试不同的参数组合。",
                "complexity_level": "极高",
                "required_knowledge": [
                    "数据特征分析方法",
                    "模型适用性判断准则",
                    "自适应参数优化策略",
                    "错误处理和重试机制"
                ],
                "expected_workflow_features": [
                    "多模型参数获取",
                    "自适应算法配置",
                    "错误处理和重试逻辑",
                    "性能评估和模型选择",
                    "结果验证机制"
                ]
            },
            {
                "case_id": "complex_multi_objective_optimization",
                "name": "多目标优化率定",
                "description": "实现考虑多个评估指标的综合优化率定",
                "query": "我需要进行多目标优化的模型率定，不仅要优化NSE，还要同时考虑峰值流量的准确性（用RMSE衡量）和径流量平衡（用偏差衡量）。设计一个能够平衡这三个目标的率定工作流。",
                "complexity_level": "极高",
                "required_knowledge": [
                    "多目标优化算法配置",
                    "多指标权重设计",
                    "综合评估方法",
                    "帕累托最优解分析"
                ],
                "expected_workflow_features": [
                    "多目标函数配置",
                    "权重平衡策略",
                    "综合评估指标",
                    "多维度性能分析",
                    "最优解选择机制"
                ]
            },
            {
                "case_id": "complex_uncertainty_quantification",
                "name": "不确定性量化分析",
                "description": "系统性分析模型预测的不确定性来源和量化方法",
                "query": "设计一个完整的不确定性分析工作流，包括参数不确定性、模型结构不确定性和输入数据不确定性。使用蒙特卡罗方法生成不确定性区间，并提供置信度评估。",
                "complexity_level": "极高",
                "required_knowledge": [
                    "不确定性分析理论",
                    "蒙特卡罗模拟方法",
                    "置信区间计算",
                    "敏感性分析技术"
                ],
                "expected_workflow_features": [
                    "多次随机采样",
                    "参数扰动分析",
                    "置信区间计算",
                    "不确定性传播分析",
                    "风险评估指标"
                ]
            }
        ]

    def run_comparison_test(self, test_case: Dict[str, Any], logger_config: LoggerConfig = None) -> Dict[str, Any]:
        """运行单个对比测试"""
        case_id = test_case["case_id"]
        query = test_case["query"]

        result = {
            "case_id": case_id,
            "name": test_case["name"],
            "query": query,
            "complexity_level": test_case["complexity_level"],
            "timestamp": datetime.now().isoformat(),
            "with_rag": {},
            "without_rag": {},
            "comparison": {}
        }

        if logger_config:
            logger_config.log_step(f"开始测试用例: {test_case['name']}")
        else:
            print(f"\n{'='*80}")
            print(f"测试用例: {test_case['name']}")
            print(f"复杂度: {test_case['complexity_level']}")
            print(f"查询: {query}")
            print(f"{'='*80}")

        # 测试1: 使用RAG
        if logger_config:
            logger_config.log_step("执行带RAG测试")
        else:
            print("\n--- 测试1: 使用RAG ---")

        result["with_rag"] = self._test_with_rag(query, test_case, logger_config)

        # 测试2: 不使用RAG
        if logger_config:
            logger_config.log_step("执行不带RAG测试")
        else:
            print("\n--- 测试2: 不使用RAG ---")

        result["without_rag"] = self._test_without_rag(query, test_case, logger_config)

        # 对比分析
        result["comparison"] = self._compare_results(
            result["with_rag"],
            result["without_rag"],
            test_case,
            logger_config
        )

        return result

    def _test_with_rag(self, query: str, test_case: Dict[str, Any], logger_config: LoggerConfig = None) -> Dict[str, Any]:
        """测试使用RAG的情况"""
        start_time = time.time()

        try:
            # 创建启用RAG的构建器
            builder = WorkflowBuilder(enable_rag=True)

            if logger_config:
                logger_config.log_step("创建RAG构建器")
            else:
                print("  创建启用RAG的构建器...")

            # 检查构建器就绪状态
            readiness = builder.is_ready()
            if not readiness["overall_ready"]:
                return {
                    "success": False,
                    "error": "RAG构建器未就绪",
                    "readiness": readiness,
                    "execution_time": time.time() - start_time
                }

            # 构建工作流
            if logger_config:
                logger_config.log_step("构建工作流")
            else:
                print(f"  构建工作流: {query[:50]}...")

            result = builder.build_workflow(query, {"test_mode": True})

            execution_time = time.time() - start_time

            if result.success:
                workflow_analysis = self._analyze_workflow(result.workflow, test_case)

                return {
                    "success": True,
                    "workflow_generated": True,
                    "workflow": result.workflow,
                    "workflow_analysis": workflow_analysis,
                    "execution_time": execution_time,
                    "rag_retrieval_info": getattr(result, 'rag_info', None)
                }
            else:
                return {
                    "success": False,
                    "workflow_generated": False,
                    "error": result.error_message,
                    "execution_time": execution_time
                }

        except Exception as e:
            return {
                "success": False,
                "workflow_generated": False,
                "error": str(e),
                "execution_time": time.time() - start_time,
                "exception_type": type(e).__name__
            }

    def _test_without_rag(self, query: str, test_case: Dict[str, Any], logger_config: LoggerConfig = None) -> Dict[str, Any]:
        """测试不使用RAG的情况"""
        start_time = time.time()

        try:
            # 创建禁用RAG的构建器
            builder = WorkflowBuilder(enable_rag=False)

            if logger_config:
                logger_config.log_step("创建非RAG构建器")
            else:
                print("  创建禁用RAG的构建器...")

            # 检查构建器就绪状态
            readiness = builder.is_ready()
            if not readiness["overall_ready"]:
                return {
                    "success": False,
                    "error": "构建器未就绪",
                    "readiness": readiness,
                    "execution_time": time.time() - start_time
                }

            # 构建工作流
            if logger_config:
                logger_config.log_step("构建工作流")
            else:
                print(f"  构建工作流: {query[:50]}...")

            result = builder.build_workflow(query, {"test_mode": True})

            execution_time = time.time() - start_time

            if result.success:
                workflow_analysis = self._analyze_workflow(result.workflow, test_case)

                return {
                    "success": True,
                    "workflow_generated": True,
                    "workflow": result.workflow,
                    "workflow_analysis": workflow_analysis,
                    "execution_time": execution_time
                }
            else:
                return {
                    "success": False,
                    "workflow_generated": False,
                    "error": result.error_message,
                    "execution_time": execution_time
                }

        except Exception as e:
            return {
                "success": False,
                "workflow_generated": False,
                "error": str(e),
                "execution_time": time.time() - start_time,
                "exception_type": type(e).__name__
            }

    def _analyze_workflow(self, workflow: Dict[str, Any], test_case: Dict[str, Any]) -> Dict[str, Any]:
        """分析生成的工作流质量"""
        if not workflow:
            return {
                "task_count": 0,
                "has_dependencies": False,
                "execution_mode": None,
                "expected_features_score": 0,
                "quality_score": 0
            }

        tasks = workflow.get("tasks", [])
        task_count = len(tasks)

        # 分析依赖关系
        has_dependencies = any(task.get("dependencies", []) for task in tasks)

        # 检查执行模式
        execution_mode = workflow.get("mode", "sequential")

        # 检查是否包含预期特征
        expected_features = test_case.get("expected_workflow_features", [])
        features_found = 0

        workflow_str = json.dumps(workflow, ensure_ascii=False).lower()

        for feature in expected_features:
            if self._check_feature_in_workflow(feature, workflow, workflow_str):
                features_found += 1

        expected_features_score = features_found / len(expected_features) if expected_features else 0

        # 计算总体质量分数
        quality_components = [
            min(task_count / 4, 1.0),  # 任务数量合理性 (4个任务满分)
            1.0 if has_dependencies else 0.5,  # 依赖关系
            expected_features_score,  # 预期特征覆盖率
            1.0 if task_count > 0 else 0  # 基本可用性
        ]

        quality_score = sum(quality_components) / len(quality_components)

        return {
            "task_count": task_count,
            "has_dependencies": has_dependencies,
            "execution_mode": execution_mode,
            "expected_features_found": features_found,
            "expected_features_total": len(expected_features),
            "expected_features_score": expected_features_score,
            "quality_components": {
                "task_complexity": quality_components[0],
                "dependency_logic": quality_components[1],
                "feature_coverage": quality_components[2],
                "basic_usability": quality_components[3]
            },
            "quality_score": quality_score
        }

    def _check_feature_in_workflow(self, feature: str, workflow: Dict, workflow_str: str) -> bool:
        """检查工作流中是否包含特定特征"""
        feature_lower = feature.lower()

        # 直接文本匹配
        if feature_lower in workflow_str:
            return True

        # 特定特征检查
        if "并行" in feature_lower or "parallel" in feature_lower:
            return workflow.get("mode", "").lower() == "parallel"

        if "cv_fold" in feature_lower or "交叉验证" in feature_lower:
            return any(
                task.get("parameters", {}).get("cv_fold", 0) > 1
                for task in workflow.get("tasks", [])
            )

        if "超时" in feature_lower or "timeout" in feature_lower:
            return any(
                task.get("timeout", 0) > 0
                for task in workflow.get("tasks", [])
            )

        if "重试" in feature_lower or "retry" in feature_lower:
            return any(
                task.get("retry_count", 0) > 0
                for task in workflow.get("tasks", [])
            )

        # 任务数量检查
        if "任务" in feature_lower and any(char.isdigit() for char in feature_lower):
            import re
            numbers = re.findall(r'\d+', feature_lower)
            if numbers:
                expected_count = int(numbers[0])
                actual_count = len(workflow.get("tasks", []))
                return actual_count >= expected_count

        return False

    def _compare_results(self, with_rag: Dict, without_rag: Dict, test_case: Dict, logger_config: LoggerConfig = None) -> Dict[str, Any]:
        """对比RAG和非RAG的结果"""
        comparison = {
            "rag_advantage": {},
            "performance_metrics": {},
            "quality_improvement": 0,
            "success_improvement": False,
            "recommendation": ""
        }

        # 成功率对比
        rag_success = with_rag.get("success", False)
        no_rag_success = without_rag.get("success", False)

        comparison["success_improvement"] = rag_success and not no_rag_success

        # 执行时间对比
        rag_time = with_rag.get("execution_time", 0)
        no_rag_time = without_rag.get("execution_time", 0)

        comparison["performance_metrics"] = {
            "execution_time_rag": rag_time,
            "execution_time_no_rag": no_rag_time,
            "time_difference": rag_time - no_rag_time
        }

        # 工作流质量对比
        if rag_success and no_rag_success:
            rag_quality = with_rag.get("workflow_analysis", {}).get("quality_score", 0)
            no_rag_quality = without_rag.get("workflow_analysis", {}).get("quality_score", 0)
            comparison["quality_improvement"] = rag_quality - no_rag_quality
        elif rag_success:
            comparison["quality_improvement"] = 1.0  # RAG成功，非RAG失败
        elif no_rag_success:
            comparison["quality_improvement"] = -1.0  # RAG失败，非RAG成功
        else:
            comparison["quality_improvement"] = 0  # 都失败

        # RAG优势分析
        if rag_success:
            rag_analysis = with_rag.get("workflow_analysis", {})
            comparison["rag_advantage"] = {
                "workflow_generated": True,
                "task_count": rag_analysis.get("task_count", 0),
                "feature_coverage": rag_analysis.get("expected_features_score", 0),
                "quality_score": rag_analysis.get("quality_score", 0)
            }

        # 生成建议
        if comparison["success_improvement"]:
            comparison["recommendation"] = "RAG显著提升了复杂任务的处理能力，建议启用RAG"
        elif comparison["quality_improvement"] > 0.2:
            comparison["recommendation"] = "RAG明显提升了工作流质量，建议启用RAG"
        elif comparison["quality_improvement"] > 0:
            comparison["recommendation"] = "RAG略微提升了工作流质量"
        else:
            comparison["recommendation"] = "RAG在此测试用例中未显示明显优势"

        if logger_config:
            logger_config.log_result(f"对比结果: {test_case['name']}", comparison)
        else:
            print(f"\n--- 对比结果 ---")
            print(f"RAG成功: {rag_success}, 非RAG成功: {no_rag_success}")
            print(f"质量提升: {comparison['quality_improvement']:.3f}")
            print(f"建议: {comparison['recommendation']}")

        return comparison

    def run_full_comparison_suite(self, save_results: bool = True) -> Dict[str, Any]:
        """运行完整的对比测试套件"""
        test_cases = self.get_complex_test_cases()

        if self.enable_logging:
            test_name = "rag_effectiveness_comparison"
            test_description = "RAG系统效果对比测试 - 复杂任务处理能力验证"

            with TestLoggerContext(test_name, test_description) as logger_config:
                return self._run_tests_with_logging(test_cases, save_results, logger_config)
        else:
            return self._run_tests_without_logging(test_cases, save_results)

    def _run_tests_with_logging(self, test_cases: List[Dict], save_results: bool, logger_config: LoggerConfig) -> Dict[str, Any]:
        """使用日志记录运行测试"""
        logger_config.log_step("开始RAG效果对比测试")
        logger_config.log_step(f"测试用例数量: {len(test_cases)}")

        for i, test_case in enumerate(test_cases, 1):
            logger_config.log_step(f"执行测试用例 {i}/{len(test_cases)}: {test_case['name']}")

            try:
                case_result = self.run_comparison_test(test_case, logger_config)
                self.results["test_cases"].append(case_result)

                logger_config.log_step(f"测试用例 {i} 完成")

            except Exception as e:
                error_result = {
                    "case_id": test_case["case_id"],
                    "name": test_case["name"],
                    "error": str(e),
                    "success": False
                }
                self.results["test_cases"].append(error_result)
                logger_config.log_result(f"测试用例 {i} 错误", {"error": str(e)})

        # 生成总结
        self.results["summary"] = self._generate_summary()
        logger_config.log_result("测试总结", self.results["summary"])

        # 保存结果
        if save_results:
            self._save_results()
            logger_config.log_step("结果已保存")

        return self.results

    def _run_tests_without_logging(self, test_cases: List[Dict], save_results: bool) -> Dict[str, Any]:
        """不使用日志记录运行测试"""
        print("="*80)
        print("RAG效果对比测试套件")
        print(f"测试用例数量: {len(test_cases)}")
        print("="*80)

        for i, test_case in enumerate(test_cases, 1):
            print(f"\n[{i}/{len(test_cases)}] 执行测试用例: {test_case['name']}")

            try:
                case_result = self.run_comparison_test(test_case)
                self.results["test_cases"].append(case_result)
                print(f"✓ 测试用例 {i} 完成")

            except Exception as e:
                error_result = {
                    "case_id": test_case["case_id"],
                    "name": test_case["name"],
                    "error": str(e),
                    "success": False
                }
                self.results["test_cases"].append(error_result)
                print(f"✗ 测试用例 {i} 失败: {e}")

        # 生成总结
        self.results["summary"] = self._generate_summary()
        self._print_summary()

        # 保存结果
        if save_results:
            self._save_results()
            print(f"\n结果已保存到: {self._get_results_path()}")

        return self.results

    def _generate_summary(self) -> Dict[str, Any]:
        """生成测试总结"""
        total_cases = len(self.results["test_cases"])
        successful_cases = len([c for c in self.results["test_cases"] if c.get("with_rag", {}).get("success", False) or c.get("without_rag", {}).get("success", False)])

        rag_successes = len([c for c in self.results["test_cases"] if c.get("with_rag", {}).get("success", False)])
        no_rag_successes = len([c for c in self.results["test_cases"] if c.get("without_rag", {}).get("success", False)])

        rag_only_successes = len([
            c for c in self.results["test_cases"]
            if c.get("with_rag", {}).get("success", False) and not c.get("without_rag", {}).get("success", False)
        ])

        quality_improvements = [
            c.get("comparison", {}).get("quality_improvement", 0)
            for c in self.results["test_cases"]
            if c.get("comparison", {}).get("quality_improvement") is not None
        ]

        avg_quality_improvement = sum(quality_improvements) / len(quality_improvements) if quality_improvements else 0

        return {
            "total_test_cases": total_cases,
            "successful_cases": successful_cases,
            "rag_success_rate": rag_successes / total_cases if total_cases > 0 else 0,
            "no_rag_success_rate": no_rag_successes / total_cases if total_cases > 0 else 0,
            "rag_only_successes": rag_only_successes,
            "rag_advantage_cases": len([c for c in self.results["test_cases"] if c.get("comparison", {}).get("success_improvement", False)]),
            "average_quality_improvement": avg_quality_improvement,
            "rag_effectiveness_score": (rag_successes / total_cases + avg_quality_improvement) / 2 if total_cases > 0 else 0,
            "recommendation": self._get_overall_recommendation(rag_only_successes, avg_quality_improvement, total_cases)
        }

    def _get_overall_recommendation(self, rag_only_successes: int, avg_quality_improvement: float, total_cases: int) -> str:
        """生成总体建议"""
        if rag_only_successes > total_cases * 0.3:
            return "强烈建议启用RAG：RAG在大多数复杂任务中表现出显著优势"
        elif avg_quality_improvement > 0.3:
            return "建议启用RAG：RAG显著提升了工作流质量"
        elif avg_quality_improvement > 0.1:
            return "建议启用RAG：RAG在复杂任务中有明显改善"
        elif rag_only_successes > 0:
            return "建议启用RAG：RAG在部分复杂任务中发挥重要作用"
        else:
            return "RAG效果有限：在当前测试用例中未显示明显优势"

    def _print_summary(self):
        """打印测试总结"""
        summary = self.results["summary"]

        print("\n" + "="*80)
        print("测试总结")
        print("="*80)
        print(f"总测试用例: {summary['total_test_cases']}")
        print(f"RAG成功率: {summary['rag_success_rate']:.2%}")
        print(f"非RAG成功率: {summary['no_rag_success_rate']:.2%}")
        print(f"RAG独有成功: {summary['rag_only_successes']} 个")
        print(f"平均质量提升: {summary['average_quality_improvement']:.3f}")
        print(f"RAG效果评分: {summary['rag_effectiveness_score']:.3f}")
        print(f"\n总体建议: {summary['recommendation']}")
        print("="*80)

    def _save_results(self):
        """保存测试结果"""
        results_path = self._get_results_path()
        results_path.parent.mkdir(exist_ok=True)

        with open(results_path, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)

    def _get_results_path(self) -> Path:
        """获取结果保存路径"""
        return self.project_root / "test" / "results" / f"rag_comparison_{self.results['test_session_id']}.json"


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="RAG效果对比测试")
    parser.add_argument("--no-log-file", action="store_true", help="不使用日志文件，直接输出到控制台")
    parser.add_argument("--no-save", action="store_true", help="不保存测试结果")
    parser.add_argument("--case-id", type=str, help="只运行指定的测试用例ID")

    args = parser.parse_args()

    # 创建测试实例
    tester = RAGEffectivenessComparison(enable_logging=not args.no_log_file)

    if args.case_id:
        # 运行单个测试用例
        test_cases = tester.get_complex_test_cases()
        target_case = next((case for case in test_cases if case["case_id"] == args.case_id), None)

        if not target_case:
            print(f"错误: 未找到测试用例 {args.case_id}")
            print("可用的测试用例:")
            for case in test_cases:
                print(f"  - {case['case_id']}: {case['name']}")
            return 1

        print(f"运行单个测试用例: {target_case['name']}")
        result = tester.run_comparison_test(target_case)

        if not args.no_save:
            tester.results["test_cases"] = [result]
            tester.results["summary"] = tester._generate_summary()
            tester._save_results()
            print(f"结果已保存到: {tester._get_results_path()}")
    else:
        # 运行完整测试套件
        tester.run_full_comparison_suite(save_results=not args.no_save)

    return 0


if __name__ == "__main__":
    sys.exit(main())
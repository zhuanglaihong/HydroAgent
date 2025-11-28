"""
Author: Claude
Date: 2025-01-27 21:30:00
LastEditTime: 2025-01-27 21:30:00
LastEditors: Claude
Description: Report generation utilities for HydroAgent
             通用报告生成工具，供DeveloperAgent调用
FilePath: /HydroAgent/hydroagent/utils/report_generator.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

核心功能：
1. 生成Markdown格式的分析报告
2. 支持不同实验类型（重复率定、迭代优化等）
3. 清晰地展示指标、参数、建议等信息
"""

from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    报告生成器 - 生成Markdown格式的分析报告

    设计原则：
    1. 只负责报告生成，不做数据分析
    2. 提供通用的报告模板方法
    3. 由DeveloperAgent调用，传入分析结果

    核心方法：
    - generate_repeated_calibration_report(): 重复率定报告
    - generate_iterative_optimization_report(): 迭代优化报告
    - generate_multi_basin_report(): 多流域报告
    """

    @staticmethod
    def generate_repeated_calibration_report(
        analysis: Dict[str, Any],
        data_summary: str,
        plots: List[str],
        n_repeats: int,
        output_path: Path
    ) -> Path:
        """
        生成重复率定实验分析报告

        Args:
            analysis: LLM分析结果
                {
                    "stability_level": "优秀/良好/不稳定",
                    "stability_comment": "...",
                    "key_findings": ["发现1", "发现2", ...],
                    "recommendations": ["建议1", "建议2", ...]
                }
            data_summary: 数据摘要文本
            plots: 生成的图表路径列表
            n_repeats: 重复次数
            output_path: 输出路径（目录）

        Returns:
            报告文件路径
        """
        report_path = output_path / "analysis_report.md"

        # 生成报告内容
        report_lines = []
        report_lines.append("# 重复率定实验分析报告")
        report_lines.append("# Repeated Calibration Analysis Report")
        report_lines.append("")
        report_lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"**重复次数**: {n_repeats}")
        report_lines.append("")
        report_lines.append("---")
        report_lines.append("")

        # 1. 稳定性评估
        stability_level = analysis.get("stability_level", "未知")
        stability_comment = analysis.get("stability_comment", "")
        report_lines.append("## 1. 稳定性评估 (Stability Assessment)")
        report_lines.append("")
        report_lines.append(f"**评级**: {stability_level}")
        report_lines.append("")
        if stability_comment:
            report_lines.append(f"**说明**: {stability_comment}")
            report_lines.append("")

        # 2. 关键发现
        key_findings = analysis.get("key_findings", [])
        if key_findings:
            report_lines.append("## 2. 关键发现 (Key Findings)")
            report_lines.append("")
            for i, finding in enumerate(key_findings, 1):
                report_lines.append(f"{i}. {finding}")
            report_lines.append("")

        # 3. 改进建议
        recommendations = analysis.get("recommendations", [])
        if recommendations:
            report_lines.append("## 3. 改进建议 (Recommendations)")
            report_lines.append("")
            for i, rec in enumerate(recommendations, 1):
                report_lines.append(f"{i}. {rec}")
            report_lines.append("")

        # 4. 数据摘要
        report_lines.append("## 4. 数据摘要 (Data Summary)")
        report_lines.append("")
        report_lines.append("```")
        report_lines.append(data_summary)
        report_lines.append("```")
        report_lines.append("")

        # 5. 生成的图表
        if plots:
            report_lines.append("## 5. 可视化图表 (Visualization)")
            report_lines.append("")
            for plot_path in plots:
                plot_name = Path(plot_path).name
                report_lines.append(f"- `{plot_name}`")
            report_lines.append("")

        # 写入文件
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))

        logger.info(f"[ReportGenerator] 重复率定报告已生成: {report_path}")
        return report_path

    @staticmethod
    def generate_iterative_optimization_report(
        analysis: Dict[str, Any],
        iteration_history: List[Dict],
        plots: List[str],
        converged: bool,
        total_iterations: int,
        output_path: Path
    ) -> Path:
        """
        生成迭代优化实验分析报告

        Args:
            analysis: 分析结果
                {
                    "convergence": {...},
                    "summary": {"quality": "优秀"},
                    "final_metrics": {...},
                    "final_params": {...},
                    "recommendations": [...]
                }
            iteration_history: 迭代历史
                [{"iteration": 1, "nse": 0.65, "status": "..."}, ...]
            plots: 生成的图表路径列表
            converged: 是否收敛
            total_iterations: 总迭代次数
            output_path: 输出路径（目录）

        Returns:
            报告文件路径
        """
        report_path = output_path / "analysis_report.md"

        # 生成报告内容
        report_lines = []
        report_lines.append("# 迭代优化实验分析报告")
        report_lines.append("# Iterative Optimization Analysis Report")
        report_lines.append("")
        report_lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"**迭代次数**: {total_iterations}")
        report_lines.append(f"**收敛状态**: {'✅ 已收敛' if converged else '❌ 未收敛'}")
        report_lines.append("")
        report_lines.append("---")
        report_lines.append("")

        # 1. 收敛性分析
        convergence = analysis.get("convergence", {})
        report_lines.append("## 1. 收敛性分析 (Convergence Analysis)")
        report_lines.append("")
        if convergence:
            report_lines.append(f"- **初始NSE**: {convergence.get('initial_nse', 0):.3f}")
            report_lines.append(f"- **最终NSE**: {convergence.get('final_nse', 0):.3f}")
            report_lines.append(f"- **最佳NSE**: {convergence.get('best_nse', 0):.3f}")
            report_lines.append(f"- **改进幅度**: {convergence.get('improvement', 0):.3f}")
            report_lines.append(f"- **改进率**: {convergence.get('improvement_rate', 0):.1f}%")
            report_lines.append(f"- **趋势**: {convergence.get('trend', 'unknown')}")
        report_lines.append("")

        # 2. 质量评估
        quality = analysis.get("summary", {}).get("quality", "未知")
        report_lines.append("## 2. 质量评估 (Quality Assessment)")
        report_lines.append("")
        report_lines.append(f"**评级**: {quality}")
        report_lines.append("")

        # 3. 最终指标
        final_metrics = analysis.get("final_metrics", {})
        if final_metrics:
            report_lines.append("## 3. 最终性能指标 (Final Metrics)")
            report_lines.append("")
            for metric_name, value in final_metrics.items():
                report_lines.append(f"- **{metric_name}**: {value:.4f}" if isinstance(value, float) else f"- **{metric_name}**: {value}")
            report_lines.append("")

        # 4. 最优参数
        final_params = analysis.get("final_params", {})
        if final_params:
            report_lines.append("## 4. 最优参数 (Optimal Parameters)")
            report_lines.append("")
            for param_name, value in final_params.items():
                report_lines.append(f"- **{param_name}**: {value:.6f}" if isinstance(value, float) else f"- **{param_name}**: {value}")
            report_lines.append("")

        # 5. 改进建议
        recommendations = analysis.get("recommendations", [])
        if recommendations:
            report_lines.append("## 5. 改进建议 (Recommendations)")
            report_lines.append("")
            for i, rec in enumerate(recommendations, 1):
                report_lines.append(f"{i}. {rec}")
            report_lines.append("")

        # 6. 迭代历史
        if iteration_history:
            report_lines.append("## 6. 迭代历史 (Iteration History)")
            report_lines.append("")
            report_lines.append("| 迭代 | NSE | 状态 |")
            report_lines.append("|------|-----|------|")
            for h in iteration_history:
                iter_num = h.get("iteration", 0)
                nse = h.get("nse", 0)
                status = h.get("status", "")
                report_lines.append(f"| {iter_num} | {nse:.4f} | {status} |")
            report_lines.append("")

        # 7. 生成的图表
        if plots:
            report_lines.append("## 7. 可视化图表 (Visualization)")
            report_lines.append("")
            for plot_path in plots:
                plot_name = Path(plot_path).name
                report_lines.append(f"- `{plot_name}`")
            report_lines.append("")

        # 写入文件
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))

        logger.info(f"[ReportGenerator] 迭代优化报告已生成: {report_path}")
        return report_path

    @staticmethod
    def generate_multi_basin_report(
        analysis: Dict[str, Any],
        basin_results: Dict[str, Dict],
        plots: List[str],
        output_path: Path
    ) -> Path:
        """
        生成多流域实验分析报告

        Args:
            analysis: 分析结果
            basin_results: 流域结果
                {"basin_id": {"metrics": {...}, "best_params": {...}}, ...}
            plots: 生成的图表路径列表
            output_path: 输出路径（目录）

        Returns:
            报告文件路径
        """
        report_path = output_path / "analysis_report.md"

        report_lines = []
        report_lines.append("# 多流域实验分析报告")
        report_lines.append("# Multi-Basin Analysis Report")
        report_lines.append("")
        report_lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"**流域数量**: {len(basin_results)}")
        report_lines.append("")
        report_lines.append("---")
        report_lines.append("")

        # 1. 流域性能对比
        report_lines.append("## 1. 流域性能对比 (Basin Performance)")
        report_lines.append("")
        report_lines.append("| Basin ID | NSE | RMSE | Status |")
        report_lines.append("|----------|-----|------|--------|")

        for basin_id, result in basin_results.items():
            metrics = result.get("metrics", {})
            nse = metrics.get("NSE", "N/A")
            rmse = metrics.get("RMSE", "N/A")
            status = "✅" if (isinstance(nse, (int, float)) and nse > 0.65) else "⚠️"
            report_lines.append(f"| {basin_id} | {nse:.3f if isinstance(nse, (int, float)) else nse} | {rmse:.3f if isinstance(rmse, (int, float)) else rmse} | {status} |")

        report_lines.append("")

        # 2. 分析建议
        recommendations = analysis.get("recommendations", [])
        if recommendations:
            report_lines.append("## 2. 分析建议 (Recommendations)")
            report_lines.append("")
            for i, rec in enumerate(recommendations, 1):
                report_lines.append(f"{i}. {rec}")
            report_lines.append("")

        # 3. 可视化图表
        if plots:
            report_lines.append("## 3. 可视化图表 (Visualization)")
            report_lines.append("")
            for plot_path in plots:
                plot_name = Path(plot_path).name
                report_lines.append(f"- `{plot_name}`")
            report_lines.append("")

        # 写入文件
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))

        logger.info(f"[ReportGenerator] 多流域报告已生成: {report_path}")
        return report_path

    @staticmethod
    def generate_summary_report(
        title: str,
        sections: Dict[str, Any],
        output_path: Path
    ) -> Path:
        """
        生成通用摘要报告（灵活模板）

        Args:
            title: 报告标题
            sections: 章节内容
                {
                    "section_name": {
                        "type": "text" | "list" | "table" | "code",
                        "content": ...
                    },
                    ...
                }
            output_path: 输出路径（目录）

        Returns:
            报告文件路径
        """
        report_path = output_path / "analysis_report.md"

        report_lines = []
        report_lines.append(f"# {title}")
        report_lines.append("")
        report_lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")
        report_lines.append("---")
        report_lines.append("")

        for section_name, section_data in sections.items():
            report_lines.append(f"## {section_name}")
            report_lines.append("")

            section_type = section_data.get("type", "text")
            content = section_data.get("content", "")

            if section_type == "text":
                report_lines.append(content)
            elif section_type == "list":
                for i, item in enumerate(content, 1):
                    report_lines.append(f"{i}. {item}")
            elif section_type == "table":
                # content应该是 {"headers": [...], "rows": [[...], ...]}
                headers = content.get("headers", [])
                rows = content.get("rows", [])
                report_lines.append(f"| {' | '.join(headers)} |")
                report_lines.append(f"|{'|'.join(['---' for _ in headers])}|")
                for row in rows:
                    report_lines.append(f"| {' | '.join([str(cell) for cell in row])} |")
            elif section_type == "code":
                report_lines.append("```")
                report_lines.append(content)
                report_lines.append("```")

            report_lines.append("")

        # 写入文件
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))

        logger.info(f"[ReportGenerator] 通用报告已生成: {report_path}")
        return report_path

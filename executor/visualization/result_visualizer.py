"""
结果可视化器 - 生成工作流执行结果的可视化图表
"""

import logging
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from ..models.result import WorkflowResult, ExecutionStatus
from ..models.workflow import Workflow, WorkflowMode
from .chart_generator import ChartGenerator


class ResultVisualizer:
    """结果可视化器"""

    def __init__(self, output_dir: str = "output/visualizations", enable_debug: bool = False):
        """
        初始化可视化器

        Args:
            output_dir: 输出目录
            enable_debug: 是否启用调试模式
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.enable_debug = enable_debug
        self.logger = logging.getLogger(__name__)

        # 初始化图表生成器
        self.chart_generator = ChartGenerator(enable_debug=enable_debug)

        self.logger.info("结果可视化器初始化完成")

    def visualize_workflow_result(
        self,
        result: WorkflowResult,
        workflow: Optional[Workflow] = None,
        generate_charts: bool = True
    ) -> Dict[str, Any]:
        """
        可视化工作流执行结果

        Args:
            result: 工作流执行结果
            workflow: 工作流定义（可选，用于更详细的可视化）
            generate_charts: 是否生成图表文件

        Returns:
            Dict: 可视化结果信息
        """
        try:
            visualization_result = {
                "summary": self._generate_summary(result, workflow),
                "charts": {},
                "output_files": []
            }

            if generate_charts:
                # 生成执行概览图
                overview_chart = self._generate_execution_overview(result, workflow)
                if overview_chart:
                    visualization_result["charts"]["execution_overview"] = overview_chart

                # 生成任务执行时间线图
                timeline_chart = self._generate_task_timeline(result, workflow)
                if timeline_chart:
                    visualization_result["charts"]["task_timeline"] = timeline_chart

                # 生成成功率饼图
                success_chart = self._generate_success_rate_chart(result)
                if success_chart:
                    visualization_result["charts"]["success_rate"] = success_chart

                # 如果是React模式，生成迭代图表
                if result.react_iterations:
                    react_chart = self._generate_react_iterations_chart(result, workflow)
                    if react_chart:
                        visualization_result["charts"]["react_iterations"] = react_chart

                # 生成水文模型相关图表（如果存在）
                hydro_charts = self._generate_hydro_model_charts(result)
                if hydro_charts:
                    visualization_result["charts"].update(hydro_charts)

            self.logger.info(f"工作流结果可视化完成，生成了 {len(visualization_result['charts'])} 个图表")
            return visualization_result

        except Exception as e:
            self.logger.error(f"工作流结果可视化失败: {e}")
            return {
                "summary": {"error": str(e)},
                "charts": {},
                "output_files": []
            }

    def _generate_summary(self, result: WorkflowResult, workflow: Optional[Workflow]) -> Dict[str, Any]:
        """生成执行概览"""
        summary = {
            "execution_id": result.execution_id,
            "workflow_id": result.workflow_id,
            "status": result.status.value,
            "start_time": result.start_time.isoformat() if result.start_time else None,
            "end_time": result.end_time.isoformat() if result.end_time else None,
            "total_duration": result.total_duration,
            "task_count": len(result.task_results),
            "success_rate": result.metrics.success_rate if hasattr(result, 'metrics') else 0.0,
            "mode": workflow.mode.value if workflow else "unknown"
        }

        # React模式特殊信息
        if result.react_iterations:
            summary.update({
                "react_mode": True,
                "iterations": len(result.react_iterations),
                "target_achieved": result.target_achieved,
                "final_metric": result.react_iterations[-1].current_metric if result.react_iterations else None
            })

        return summary

    def _generate_execution_overview(self, result: WorkflowResult, workflow: Optional[Workflow]) -> Optional[str]:
        """生成执行概览图"""
        try:
            # 准备数据
            chart_data = {
                "title": f"工作流执行概览 - {result.workflow_id}",
                "execution_id": result.execution_id,
                "status": result.status.value,
                "task_results": []
            }

            for task_id, task_result in result.task_results.items():
                chart_data["task_results"].append({
                    "task_id": task_id,
                    "status": task_result.status.value,
                    "duration": task_result.duration,
                    "start_time": task_result.start_time.isoformat() if task_result.start_time else None,
                    "end_time": task_result.end_time.isoformat() if task_result.end_time else None
                })

            # 生成图表文件
            output_file = self.output_dir / f"execution_overview_{result.execution_id}.html"
            chart_html = self.chart_generator.generate_execution_overview_chart(chart_data)

            if chart_html:
                output_file.write_text(chart_html, encoding='utf-8')
                return str(output_file)

        except Exception as e:
            self.logger.error(f"生成执行概览图失败: {e}")

        return None

    def _generate_task_timeline(self, result: WorkflowResult, workflow: Optional[Workflow]) -> Optional[str]:
        """生成任务执行时间线图"""
        try:
            # 准备时间线数据
            timeline_data = {
                "title": f"任务执行时间线 - {result.workflow_id}",
                "tasks": []
            }

            for task_id, task_result in result.task_results.items():
                if task_result.start_time and task_result.end_time:
                    timeline_data["tasks"].append({
                        "task_id": task_id,
                        "start": task_result.start_time.isoformat(),
                        "end": task_result.end_time.isoformat(),
                        "status": task_result.status.value,
                        "duration": task_result.duration
                    })

            if not timeline_data["tasks"]:
                return None

            # 生成时间线图
            output_file = self.output_dir / f"task_timeline_{result.execution_id}.html"
            chart_html = self.chart_generator.generate_timeline_chart(timeline_data)

            if chart_html:
                output_file.write_text(chart_html, encoding='utf-8')
                return str(output_file)

        except Exception as e:
            self.logger.error(f"生成任务时间线图失败: {e}")

        return None

    def _generate_success_rate_chart(self, result: WorkflowResult) -> Optional[str]:
        """生成成功率饼图"""
        try:
            # 统计成功和失败的任务
            success_count = 0
            failed_count = 0

            for task_result in result.task_results.values():
                if task_result.status == ExecutionStatus.COMPLETED:
                    success_count += 1
                else:
                    failed_count += 1

            if success_count == 0 and failed_count == 0:
                return None

            # 准备饼图数据
            pie_data = {
                "title": f"任务执行成功率 - {result.workflow_id}",
                "data": [
                    {"name": "成功", "value": success_count, "color": "#28a745"},
                    {"name": "失败", "value": failed_count, "color": "#dc3545"}
                ]
            }

            # 生成饼图
            output_file = self.output_dir / f"success_rate_{result.execution_id}.html"
            chart_html = self.chart_generator.generate_pie_chart(pie_data)

            if chart_html:
                output_file.write_text(chart_html, encoding='utf-8')
                return str(output_file)

        except Exception as e:
            self.logger.error(f"生成成功率饼图失败: {e}")

        return None

    def _generate_react_iterations_chart(self, result: WorkflowResult, workflow: Optional[Workflow]) -> Optional[str]:
        """生成React迭代图表"""
        try:
            if not result.react_iterations:
                return None

            # 准备迭代数据
            iterations_data = {
                "title": f"React模式迭代过程 - {result.workflow_id}",
                "target": workflow.target.dict() if workflow and workflow.target else None,
                "iterations": []
            }

            for iteration in result.react_iterations:
                iterations_data["iterations"].append({
                    "iteration": iteration.iteration,
                    "current_metric": iteration.current_metric,
                    "target_metric": iteration.target_metric,
                    "target_achieved": iteration.target_achieved,
                    "start_time": iteration.start_time.isoformat() if iteration.start_time else None,
                    "end_time": iteration.end_time.isoformat() if iteration.end_time else None
                })

            # 生成迭代图表
            output_file = self.output_dir / f"react_iterations_{result.execution_id}.html"
            chart_html = self.chart_generator.generate_react_iterations_chart(iterations_data)

            if chart_html:
                output_file.write_text(chart_html, encoding='utf-8')
                return str(output_file)

        except Exception as e:
            self.logger.error(f"生成React迭代图表失败: {e}")

        return None

    def _generate_hydro_model_charts(self, result: WorkflowResult) -> Dict[str, str]:
        """生成水文模型相关图表"""
        hydro_charts = {}

        try:
            # 检查是否有水文模型相关的任务结果
            for task_id, task_result in result.task_results.items():
                # 模型率定结果图表
                if "calibrate" in task_id.lower() or "calibration" in task_id.lower():
                    calibration_chart = self._generate_calibration_result_chart(task_result, result.execution_id)
                    if calibration_chart:
                        hydro_charts["calibration_result"] = calibration_chart

                # 模型评估结果图表
                if "evaluate" in task_id.lower() or "evaluation" in task_id.lower():
                    evaluation_chart = self._generate_evaluation_result_chart(task_result, result.execution_id)
                    if evaluation_chart:
                        hydro_charts["evaluation_result"] = evaluation_chart

                # 模型性能指标图表
                if task_result.metrics:
                    metrics_chart = self._generate_metrics_chart(task_result, result.execution_id, task_id)
                    if metrics_chart:
                        hydro_charts[f"metrics_{task_id}"] = metrics_chart

        except Exception as e:
            self.logger.error(f"生成水文模型图表失败: {e}")

        return hydro_charts

    def _generate_calibration_result_chart(self, task_result, execution_id: str) -> Optional[str]:
        """生成率定结果图表"""
        try:
            # 这里是占位符实现，实际需要根据具体的率定结果数据结构来实现
            chart_data = {
                "title": "模型率定结果",
                "type": "calibration",
                "placeholder": True,  # 标记为占位符
                "message": "率定结果图表功能待实现，将根据实际率定算法输出的数据格式来生成对应的图表"
            }

            output_file = self.output_dir / f"calibration_result_{execution_id}.html"
            chart_html = self.chart_generator.generate_placeholder_chart(chart_data)

            if chart_html:
                output_file.write_text(chart_html, encoding='utf-8')
                return str(output_file)

        except Exception as e:
            self.logger.error(f"生成率定结果图表失败: {e}")

        return None

    def _generate_evaluation_result_chart(self, task_result, execution_id: str) -> Optional[str]:
        """生成评估结果图表"""
        try:
            # 这里是占位符实现
            chart_data = {
                "title": "模型评估结果",
                "type": "evaluation",
                "placeholder": True,
                "message": "模型评估图表功能待实现，将包括观测值vs模拟值对比图、误差分析图等"
            }

            output_file = self.output_dir / f"evaluation_result_{execution_id}.html"
            chart_html = self.chart_generator.generate_placeholder_chart(chart_data)

            if chart_html:
                output_file.write_text(chart_html, encoding='utf-8')
                return str(output_file)

        except Exception as e:
            self.logger.error(f"生成评估结果图表失败: {e}")

        return None

    def _generate_metrics_chart(self, task_result, execution_id: str, task_id: str) -> Optional[str]:
        """生成性能指标图表"""
        try:
            if not task_result.metrics:
                return None

            # 准备指标数据
            metrics_data = {
                "title": f"性能指标 - {task_id}",
                "metrics": task_result.metrics
            }

            output_file = self.output_dir / f"metrics_{task_id}_{execution_id}.html"
            chart_html = self.chart_generator.generate_metrics_chart(metrics_data)

            if chart_html:
                output_file.write_text(chart_html, encoding='utf-8')
                return str(output_file)

        except Exception as e:
            self.logger.error(f"生成指标图表失败: {e}")

        return None

    def generate_summary_report(self, result: WorkflowResult, workflow: Optional[Workflow] = None) -> str:
        """生成总结报告HTML"""
        try:
            # 获取可视化结果
            viz_result = self.visualize_workflow_result(result, workflow, generate_charts=True)

            # 生成总结报告HTML
            report_html = self._build_summary_report_html(viz_result, result, workflow)

            # 保存报告
            report_file = self.output_dir / f"summary_report_{result.execution_id}.html"
            report_file.write_text(report_html, encoding='utf-8')

            self.logger.info(f"总结报告已生成: {report_file}")
            return str(report_file)

        except Exception as e:
            self.logger.error(f"生成总结报告失败: {e}")
            return ""

    def _build_summary_report_html(self, viz_result: Dict[str, Any], result: WorkflowResult, workflow: Optional[Workflow]) -> str:
        """构建总结报告HTML"""
        summary = viz_result["summary"]
        charts = viz_result["charts"]

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>工作流执行报告 - {result.workflow_id}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .status-success {{ color: #28a745; }}
        .status-failed {{ color: #dc3545; }}
        .status-running {{ color: #ffc107; }}
        .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
        .summary-card {{ background: #f8f9fa; padding: 15px; border-radius: 5px; text-align: center; }}
        .chart-section {{ margin: 30px 0; }}
        .chart-links {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; }}
        .chart-link {{ display: block; padding: 15px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; text-align: center; }}
        .chart-link:hover {{ background: #0056b3; }}
        .placeholder {{ background: #e9ecef; color: #6c757d; font-style: italic; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>工作流执行报告</h1>
            <h2>{result.workflow_id}</h2>
            <p class="status-{summary['status'].lower()}">执行状态: {summary['status']}</p>
        </div>

        <div class="summary-grid">
            <div class="summary-card">
                <h4>执行ID</h4>
                <p>{summary['execution_id']}</p>
            </div>
            <div class="summary-card">
                <h4>执行模式</h4>
                <p>{summary['mode']}</p>
            </div>
            <div class="summary-card">
                <h4>任务数量</h4>
                <p>{summary['task_count']}</p>
            </div>
            <div class="summary-card">
                <h4>成功率</h4>
                <p>{summary['success_rate']:.1%}</p>
            </div>
            <div class="summary-card">
                <h4>总耗时</h4>
                <p>{summary.get('total_duration', 0):.2f}秒</p>
            </div>
        """

        # React模式信息
        if summary.get('react_mode'):
            html += f"""
            <div class="summary-card">
                <h4>React迭代</h4>
                <p>{summary['iterations']}次</p>
            </div>
            <div class="summary-card">
                <h4>目标达成</h4>
                <p class="status-{'success' if summary['target_achieved'] else 'failed'}">
                    {'是' if summary['target_achieved'] else '否'}
                </p>
            </div>
            """

        html += """
        </div>

        <div class="chart-section">
            <h3>可视化图表</h3>
            <div class="chart-links">
        """

        # 图表链接
        chart_titles = {
            "execution_overview": "执行概览",
            "task_timeline": "任务时间线",
            "success_rate": "成功率分布",
            "react_iterations": "React迭代过程",
            "calibration_result": "率定结果",
            "evaluation_result": "评估结果"
        }

        for chart_key, chart_file in charts.items():
            if chart_file:
                title = chart_titles.get(chart_key, chart_key)
                # 获取相对路径
                chart_filename = Path(chart_file).name
                html += f'<a href="{chart_filename}" class="chart-link" target="_blank">{title}</a>'

        # 占位符提示
        if not charts:
            html += '<p class="placeholder">暂无生成的图表</p>'

        html += """
            </div>
        </div>

        <div class="chart-section">
            <h3>说明</h3>
            <p>点击上方链接可查看详细的可视化图表。所有图表文件保存在同一目录下。</p>
            <p>带有"待实现"标记的图表是占位符，将在后续版本中根据具体的数据格式进行完善。</p>
        </div>
    </div>
</body>
</html>
        """

        return html
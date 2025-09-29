"""
Author: zhuanglaihong
Date: 2024-09-26 16:40:00
LastEditTime: 2024-09-26 16:40:00
LastEditors: zhuanglaihong
Description: 图表生成器 - 使用各种图表库生成可视化图表
FilePath: \HydroAgent\executor\visualization\chart_generator.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import logging
from typing import Dict, Any, List, Optional
import json


class ChartGenerator:
    """图表生成器"""

    def __init__(self, enable_debug: bool = False):
        """
        初始化图表生成器

        Args:
            enable_debug: 是否启用调试模式
        """
        self.enable_debug = enable_debug
        self.logger = logging.getLogger(__name__)

        self.logger.info("图表生成器初始化完成")

    def generate_execution_overview_chart(self, data: Dict[str, Any]) -> Optional[str]:
        """生成执行概览图表"""
        try:
            html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{data['title']}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1000px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .chart-container {{ position: relative; height: 400px; margin: 20px 0; }}
        .info {{ background: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{data['title']}</h1>

        <div class="info">
            <p><strong>执行ID:</strong> {data['execution_id']}</p>
            <p><strong>整体状态:</strong> {data['status']}</p>
        </div>

        <div class="chart-container">
            <canvas id="overviewChart"></canvas>
        </div>

        <h3>任务详情</h3>
        <table border="1" cellpadding="5" cellspacing="0" style="width:100%; border-collapse: collapse;">
            <tr style="background-color: #f8f9fa;">
                <th>任务ID</th>
                <th>状态</th>
                <th>执行时间(秒)</th>
                <th>开始时间</th>
                <th>结束时间</th>
            </tr>
            """

            # 添加任务详情表格
            for task in data["task_results"]:
                status_color = "#28a745" if task["status"] == "COMPLETED" else "#dc3545"
                html += f"""
            <tr>
                <td>{task['task_id']}</td>
                <td style="color: {status_color}; font-weight: bold;">{task['status']}</td>
                <td>{task.get('duration', 0) or 0:.2f}</td>
                <td>{task.get('start_time') or 'N/A'}</td>
                <td>{task.get('end_time') or 'N/A'}</td>
            </tr>
                """

            # 准备图表数据
            task_labels = [task["task_id"] for task in data["task_results"]]
            task_durations = [
                task.get("duration", 0) or 0 for task in data["task_results"]
            ]
            task_colors = [
                "#28a745" if task["status"] == "COMPLETED" else "#dc3545"
                for task in data["task_results"]
            ]

            html += f"""
        </table>
    </div>

    <script>
        const ctx = document.getElementById('overviewChart').getContext('2d');
        new Chart(ctx, {{
            type: 'bar',
            data: {{
                labels: {json.dumps(task_labels)},
                datasets: [{{
                    label: '执行时间(秒)',
                    data: {json.dumps(task_durations)},
                    backgroundColor: {json.dumps(task_colors)},
                    borderColor: {json.dumps(task_colors)},
                    borderWidth: 1
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    title: {{
                        display: true,
                        text: '任务执行时间分布'
                    }},
                    legend: {{
                        display: false
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        title: {{
                            display: true,
                            text: '执行时间 (秒)'
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
            """

            return html

        except Exception as e:
            self.logger.error(f"生成执行概览图表失败: {e}")
            return None

    def generate_timeline_chart(self, data: Dict[str, Any]) -> Optional[str]:
        """生成时间线图表"""
        try:
            html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{data['title']}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .timeline {{ margin: 20px 0; }}
        .timeline-item {{ display: flex; align-items: center; margin: 10px 0; padding: 10px; border-radius: 5px; }}
        .timeline-success {{ background-color: #d4edda; border-left: 4px solid #28a745; }}
        .timeline-failed {{ background-color: #f8d7da; border-left: 4px solid #dc3545; }}
        .timeline-running {{ background-color: #fff3cd; border-left: 4px solid #ffc107; }}
        .task-id {{ font-weight: bold; min-width: 120px; }}
        .task-time {{ flex: 1; margin: 0 20px; }}
        .task-duration {{ min-width: 100px; text-align: right; }}
        .placeholder {{ background: #e9ecef; color: #6c757d; font-style: italic; text-align: center; padding: 40px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{data['title']}</h1>

        <div class="timeline">
            """

            if data["tasks"]:
                for task in data["tasks"]:
                    status_class = {
                        "COMPLETED": "timeline-success",
                        "FAILED": "timeline-failed",
                        "RUNNING": "timeline-running",
                    }.get(task["status"], "timeline-failed")

                    html += f"""
            <div class="timeline-item {status_class}">
                <div class="task-id">{task['task_id']}</div>
                <div class="task-time">
                    <div>开始: {task['start']}</div>
                    <div>结束: {task['end']}</div>
                </div>
                <div class="task-duration">{task.get('duration', 0) or 0:.2f}秒</div>
            </div>
                    """
            else:
                html += '<div class="placeholder">暂无时间线数据</div>'

            html += """
        </div>
    </div>
</body>
</html>
            """

            return html

        except Exception as e:
            self.logger.error(f"生成时间线图表失败: {e}")
            return None

    def generate_pie_chart(self, data: Dict[str, Any]) -> Optional[str]:
        """生成饼图"""
        try:
            html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{data['title']}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .chart-container {{ position: relative; height: 400px; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{data['title']}</h1>

        <div class="chart-container">
            <canvas id="pieChart"></canvas>
        </div>
    </div>

    <script>
        const ctx = document.getElementById('pieChart').getContext('2d');
        new Chart(ctx, {{
            type: 'pie',
            data: {{
                labels: {json.dumps([item['name'] for item in data['data']])},
                datasets: [{{
                    data: {json.dumps([item['value'] for item in data['data']])},
                    backgroundColor: {json.dumps([item['color'] for item in data['data']])},
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'bottom'
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
            """

            return html

        except Exception as e:
            self.logger.error(f"生成饼图失败: {e}")
            return None

    def generate_react_iterations_chart(self, data: Dict[str, Any]) -> Optional[str]:
        """生成React迭代图表"""
        try:
            iterations = data.get("iterations", [])
            target = data.get("target", {})

            html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{data['title']}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1000px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .chart-container {{ position: relative; height: 400px; margin: 20px 0; }}
        .info {{ background: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{data['title']}</h1>

        <div class="info">
            <p><strong>目标:</strong> {target.get('metric', 'N/A')} {target.get('comparison', '>=')} {target.get('threshold', 'N/A')}</p>
            <p><strong>最大迭代次数:</strong> {target.get('max_iterations', 'N/A')}</p>
        </div>

        <div class="chart-container">
            <canvas id="reactChart"></canvas>
        </div>

        <h3>迭代详情</h3>
        <table border="1" cellpadding="5" cellspacing="0" style="width:100%; border-collapse: collapse;">
            <tr style="background-color: #f8f9fa;">
                <th>迭代</th>
                <th>当前指标值</th>
                <th>目标值</th>
                <th>目标达成</th>
                <th>开始时间</th>
                <th>结束时间</th>
            </tr>
            """

            for iteration in iterations:
                achieved_color = (
                    "#28a745" if iteration.get("target_achieved") else "#dc3545"
                )
                achieved_text = "是" if iteration.get("target_achieved") else "否"

                html += f"""
            <tr>
                <td>{iteration.get('iteration', 'N/A')}</td>
                <td>{iteration.get('current_metric', 'N/A')}</td>
                <td>{iteration.get('target_metric', 'N/A')}</td>
                <td style="color: {achieved_color}; font-weight: bold;">{achieved_text}</td>
                <td>{iteration.get('start_time', 'N/A')}</td>
                <td>{iteration.get('end_time', 'N/A')}</td>
            </tr>
                """

            # 准备图表数据
            iteration_labels = [f"迭代{iter['iteration']}" for iter in iterations]
            current_metrics = [iter.get("current_metric") for iter in iterations]
            target_value = target.get("threshold") if target else None

            html += f"""
        </table>
    </div>

    <script>
        const ctx = document.getElementById('reactChart').getContext('2d');

        const datasets = [{{
            label: '当前指标值',
            data: {json.dumps(current_metrics)},
            borderColor: '#007bff',
            backgroundColor: 'rgba(0, 123, 255, 0.1)',
            fill: true,
            tension: 0.4
        }}];

        // 添加目标线
        if ({target_value} !== null) {{
            datasets.push({{
                label: '目标值',
                data: Array({len(iterations)}).fill({target_value}),
                borderColor: '#28a745',
                backgroundColor: 'transparent',
                borderDash: [5, 5],
                fill: false,
                pointRadius: 0
            }});
        }}

        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: {json.dumps(iteration_labels)},
                datasets: datasets
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    title: {{
                        display: true,
                        text: 'React模式指标变化趋势'
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: false,
                        title: {{
                            display: true,
                            text: '指标值'
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
            """

            return html

        except Exception as e:
            self.logger.error(f"生成React迭代图表失败: {e}")
            return None

    def generate_metrics_chart(self, data: Dict[str, Any]) -> Optional[str]:
        """生成指标图表"""
        try:
            metrics = data.get("metrics", {})

            if not metrics:
                return self.generate_placeholder_chart(
                    {"title": data["title"], "message": "暂无性能指标数据"}
                )

            html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{data['title']}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .chart-container {{ position: relative; height: 400px; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{data['title']}</h1>

        <div class="chart-container">
            <canvas id="metricsChart"></canvas>
        </div>
    </div>

    <script>
        const ctx = document.getElementById('metricsChart').getContext('2d');
        new Chart(ctx, {{
            type: 'bar',
            data: {{
                labels: {json.dumps(list(metrics.keys()))},
                datasets: [{{
                    label: '指标值',
                    data: {json.dumps(list(metrics.values()))},
                    backgroundColor: 'rgba(0, 123, 255, 0.6)',
                    borderColor: '#007bff',
                    borderWidth: 1
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        display: false
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        title: {{
                            display: true,
                            text: '指标值'
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
            """

            return html

        except Exception as e:
            self.logger.error(f"生成指标图表失败: {e}")
            return None

    def generate_placeholder_chart(self, data: Dict[str, Any]) -> Optional[str]:
        """生成占位符图表"""
        try:
            html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{data['title']}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .placeholder {{
            background: #e9ecef;
            color: #6c757d;
            font-style: italic;
            text-align: center;
            padding: 60px 20px;
            border-radius: 8px;
            border: 2px dashed #dee2e6;
        }}
        .placeholder h3 {{ margin-top: 0; color: #495057; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{data['title']}</h1>

        <div class="placeholder">
            <h3>📊 图表功能开发中</h3>
            <p>{data.get('message', '此图表功能正在开发中，将在后续版本中提供。')}</p>
            <p>图表类型: {data.get('type', '未指定')}</p>
        </div>
    </div>
</body>
</html>
            """

            return html

        except Exception as e:
            self.logger.error(f"生成占位符图表失败: {e}")
            return None

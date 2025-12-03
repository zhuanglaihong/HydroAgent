"""
Author: Claude
Date: 2025-12-03 10:00:00
LastEditTime: 2025-12-03 10:00:00
LastEditors: Claude
Description: Session summary utilities for generating intelligent session reports
             会话总结工具 - 生成智能会话总结报告
FilePath: /HydroAgent/hydroagent/utils/session_summary.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

核心功能:
1. SessionSummaryCollector: 收集会话信息(任务、时间、路径等)
2. SessionSummaryGenerator: 使用LLM生成会话总结报告
"""

from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)


class SessionSummaryCollector:
    """
    会话信息收集器

    职责:
    - 收集会话执行过程中的所有关键信息
    - 统计时间信息(各阶段耗时)
    - 记录文件路径(日志、结果、配置等)
    - 汇总任务执行情况
    """

    def __init__(self, session_id: str, workspace_dir: Path):
        """
        初始化会话信息收集器

        Args:
            session_id: 会话ID
            workspace_dir: 工作目录
        """
        self.session_id = session_id
        self.workspace_dir = Path(workspace_dir)
        self.start_time = datetime.now()
        self.end_time = None

        # 任务信息
        self.query = ""
        self.task_type = "unknown"
        self.subtasks = []

        # 时间统计
        self.phase_times = {
            "intent": 0.0,
            "planning": 0.0,
            "configuration": 0.0,
            "execution": 0.0,
            "analysis": 0.0,
        }

        # 执行结果
        self.success_count = 0
        self.failure_count = 0
        self.execution_results = []

        # 文件路径
        self.log_files = []
        self.result_files = []
        self.config_files = []
        self.report_files = []

    def set_query(self, query: str):
        """设置用户查询"""
        self.query = query

    def set_task_type(self, task_type: str):
        """设置任务类型"""
        self.task_type = task_type

    def add_subtask(self, subtask: Dict[str, Any]):
        """添加子任务信息"""
        self.subtasks.append(subtask)

    def set_phase_time(self, phase: str, duration: float):
        """设置阶段耗时"""
        if phase in self.phase_times:
            self.phase_times[phase] = duration

    def add_execution_result(self, result: Dict[str, Any]):
        """添加执行结果"""
        self.execution_results.append(result)
        if result.get("success", False):
            self.success_count += 1
        else:
            self.failure_count += 1

    def add_log_file(self, log_file: Path):
        """添加日志文件路径"""
        self.log_files.append(str(log_file))

    def add_result_file(self, result_file: Path):
        """添加结果文件路径"""
        self.result_files.append(str(result_file))

    def add_config_file(self, config_file: Path):
        """添加配置文件路径"""
        self.config_files.append(str(config_file))

    def add_report_file(self, report_file: Path):
        """添加报告文件路径"""
        self.report_files.append(str(report_file))

    def mark_completed(self):
        """标记会话完成"""
        self.end_time = datetime.now()

    def get_total_time(self) -> float:
        """获取总耗时(秒)"""
        if self.end_time is None:
            return (datetime.now() - self.start_time).total_seconds()
        return (self.end_time - self.start_time).total_seconds()

    def collect_workspace_files(self):
        """
        自动收集工作目录中的文件

        扫描workspace_dir,找到所有相关文件:
        - *.log: 日志文件
        - *.json: 结果文件
        - *.yaml: 配置文件
        - *.csv: 汇总文件
        - *.md: 报告文件
        - *.png: 图表文件
        """
        if not self.workspace_dir.exists():
            logger.warning(f"[SessionSummaryCollector] Workspace does not exist: {self.workspace_dir}")
            return

        # 递归搜索所有相关文件
        for pattern in ["*.log", "*.json", "*.yaml", "*.csv", "*.md", "*.png"]:
            for file_path in self.workspace_dir.rglob(pattern):
                # 分类添加
                if file_path.suffix == ".log":
                    self.add_log_file(file_path)
                elif file_path.suffix == ".json":
                    self.add_result_file(file_path)
                elif file_path.suffix in [".yaml", ".yml"]:
                    self.add_config_file(file_path)
                elif file_path.suffix in [".md", ".csv", ".png"]:
                    self.add_report_file(file_path)

        logger.info(f"[SessionSummaryCollector] Collected {len(self.log_files)} logs, "
                   f"{len(self.result_files)} results, {len(self.config_files)} configs, "
                   f"{len(self.report_files)} reports")

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式,供LLM分析使用

        Returns:
            会话信息字典
        """
        return {
            "session_id": self.session_id,
            "workspace": str(self.workspace_dir),
            "query": self.query,
            "task_type": self.task_type,
            "start_time": self.start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": self.end_time.strftime("%Y-%m-%d %H:%M:%S") if self.end_time else None,
            "total_time": self.get_total_time(),
            "phase_times": self.phase_times,
            "subtasks": {
                "total": len(self.subtasks),
                "success": self.success_count,
                "failure": self.failure_count,
                "details": self.subtasks,
            },
            "execution_results": self.execution_results,
            "files": {
                "logs": self.log_files,
                "results": self.result_files,
                "configs": self.config_files,
                "reports": self.report_files,
            }
        }


class SessionSummaryGenerator:
    """
    会话总结生成器(使用LLM)

    职责:
    - 接收SessionSummaryCollector收集的信息
    - 使用LLM生成智能的会话总结报告
    - 保存报告到Markdown文件
    """

    def __init__(self, llm_interface):
        """
        初始化会话总结生成器

        Args:
            llm_interface: LLM接口
        """
        self.llm = llm_interface

    def generate_summary(
        self,
        session_info: Dict[str, Any],
        analysis_result: Optional[Dict[str, Any]] = None,
        output_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        生成会话总结报告

        Args:
            session_info: 会话信息(来自SessionSummaryCollector.to_dict())
            analysis_result: DeveloperAgent的分析结果(可选)
            output_path: 报告输出路径(可选,默认为workspace/session_summary.md)

        Returns:
            {
                "success": bool,
                "report_content": str,  # Markdown格式的报告内容
                "report_path": str,     # 报告文件路径
                "summary_text": str     # 简短摘要(用于终端显示)
            }
        """
        logger.info("[SessionSummaryGenerator] Generating session summary with LLM...")

        try:
            # 构建LLM提示词
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(session_info, analysis_result)

            # 调用LLM生成总结
            llm_response = self.llm.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.3,  # 较低的温度,生成更稳定的报告
            )

            # 解析LLM响应
            report_content = self._parse_llm_response(llm_response)

            # 保存报告到文件
            if output_path is None:
                workspace_dir = Path(session_info.get("workspace", "."))
                output_path = workspace_dir / "session_summary.md"
            else:
                output_path = Path(output_path)

            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(report_content)

            logger.info(f"[SessionSummaryGenerator] Session summary saved to: {output_path}")

            # 提取简短摘要(用于终端显示)
            summary_text = self._extract_summary_text(report_content)

            return {
                "success": True,
                "report_content": report_content,
                "report_path": str(output_path),
                "summary_text": summary_text,
            }

        except Exception as e:
            logger.error(f"[SessionSummaryGenerator] Failed to generate summary: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "fallback_summary": self._generate_fallback_summary(session_info),
            }

    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        return """你是HydroAgent系统的会话总结专家。你的任务是根据会话执行信息,生成一份清晰、专业的总结报告。

报告要求:
1. **Markdown格式**: 使用标题、列表、表格等格式化元素
2. **结构清晰**: 包含执行概述、任务详情、时间统计、完成情况、建议、文件路径等章节
3. **专业准确**: 使用水文模型领域术语,准确描述执行情况
4. **实用性强**: 提供可操作的建议和改进方向

报告结构:
# HydroAgent 会话总结报告

## 1. 执行概述 (Executive Summary)
- 会话ID、时间、查询内容
- 任务类型、总体完成情况

## 2. 任务详情 (Task Details)
- 子任务列表及状态
- 关键指标(如NSE、RMSE等)

## 3. 时间统计 (Time Statistics)
- 各阶段耗时
- 总耗时

## 4. 完成情况与质量评估 (Results & Quality)
- 成功/失败任务数
- 质量评价(基于性能指标)

## 5. 改进建议 (Recommendations)
- 基于执行结果的具体建议

## 6. 文件路径 (File Paths)
- 日志文件
- 结果文件
- 配置文件
- 报告文件

注意:
- 使用中英文双语标题
- 数值保留2-3位小数
- 时间使用人类可读格式(如"2分30秒")
- 突出重点信息(使用加粗、emoji等)
"""

    def _build_user_prompt(self, session_info: Dict[str, Any], analysis_result: Optional[Dict[str, Any]]) -> str:
        """构建用户提示词"""
        # 构建会话信息摘要
        info_summary = json.dumps(session_info, indent=2, ensure_ascii=False)

        # 构建分析结果摘要(如果有)
        analysis_summary = ""
        if analysis_result:
            analysis_summary = f"\n\n## 分析结果 (Analysis Result)\n```json\n{json.dumps(analysis_result, indent=2, ensure_ascii=False)}\n```"

        prompt = f"""请根据以下会话信息,生成一份完整的会话总结报告:

## 会话信息 (Session Information)
```json
{info_summary}
```
{analysis_summary}

请按照系统提示中的结构生成Markdown格式的报告。确保:
1. 准确总结执行的任务和结果
2. 清晰展示时间统计
3. 提供实用的改进建议
4. 列出所有相关文件路径

直接输出Markdown格式的报告内容,不要包含额外的解释。"""

        return prompt

    def _parse_llm_response(self, llm_response: str) -> str:
        """
        解析LLM响应,提取Markdown内容

        Args:
            llm_response: LLM的原始响应

        Returns:
            Markdown格式的报告内容
        """
        # 如果LLM响应包含代码块,提取代码块内容
        import re

        # 匹配 ```markdown ... ``` 或 ``` ... ```
        code_block_pattern = r"```(?:markdown)?\s*\n(.*?)\n```"
        match = re.search(code_block_pattern, llm_response, re.DOTALL)

        if match:
            return match.group(1).strip()
        else:
            # 直接返回原始响应(假设LLM直接输出了Markdown)
            return llm_response.strip()

    def _extract_summary_text(self, report_content: str) -> str:
        """
        从报告内容中提取简短摘要(用于终端显示)

        Args:
            report_content: 完整的Markdown报告内容

        Returns:
            简短摘要文本
        """
        # 提取"执行概述"章节的内容
        import re

        # 匹配 ## 1. 执行概述 到下一个 ## 之间的内容
        summary_pattern = r"## 1\. 执行概述.*?\n(.*?)(?=\n##|\Z)"
        match = re.search(summary_pattern, report_content, re.DOTALL)

        if match:
            summary_section = match.group(1).strip()
            # 移除Markdown格式,只保留文本
            summary_text = re.sub(r"[*_`#\[\]\(\)]", "", summary_section)
            # 限制长度(最多5行)
            lines = summary_text.split("\n")[:5]
            return "\n".join(lines)
        else:
            # 降级:返回报告的前200个字符
            return report_content[:200] + "..."

    def _generate_fallback_summary(self, session_info: Dict[str, Any]) -> str:
        """
        生成降级总结(当LLM失败时使用)

        Args:
            session_info: 会话信息

        Returns:
            简单的文本总结
        """
        subtasks = session_info.get("subtasks", {})
        total = subtasks.get("total", 0)
        success = subtasks.get("success", 0)
        total_time = session_info.get("total_time", 0)

        summary = f"""会话总结(降级模式):
- 会话ID: {session_info.get('session_id', 'N/A')}
- 查询: {session_info.get('query', 'N/A')}
- 任务类型: {session_info.get('task_type', 'N/A')}
- 完成情况: {success}/{total} 个任务成功
- 总耗时: {total_time:.1f}秒
- 工作目录: {session_info.get('workspace', 'N/A')}

注: LLM总结生成失败,这是降级模式的简单总结。
"""
        return summary

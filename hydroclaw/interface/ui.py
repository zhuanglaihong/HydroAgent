"""
Author: HydroClaw Team
Date: 2026-03-06
Description: Terminal UI for HydroClaw.
             Two modes:
               user  - clean chat-like interface, hides debug noise
               dev   - full execution details + live log stream
"""

import contextlib
import io
import json
import time
from contextlib import contextmanager

from rich.console import Console
from rich.markdown import Markdown
from rich.padding import Padding
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich import box
from rich.columns import Columns

# ── Human-readable labels for each tool ─────────────────────────────
_TOOL_LABELS: dict[str, str] = {
    "validate_basin":    "验证流域数据",
    "calibrate_model":   "执行模型率定",
    "evaluate_model":    "评估模型性能",
    "visualize":         "生成可视化图形",
    "llm_calibrate":     "LLM 智能率定",
    "batch_calibrate":   "批量率定流域",
    "compare_models":    "多模型对比",
    "generate_code":     "生成分析代码",
    "run_code":          "执行分析脚本",
    "run_simulation":    "运行模型模拟",
    "create_skill":      "创建新技能",
    "create_task_list":  "创建任务计划",
    "get_pending_tasks": "获取待执行任务",
    "update_task":       "更新任务状态",
    "add_task":          "追加新任务",
    "read_file":         "读取文件",
    "inspect_dir":       "查看目录",
    "ask_user":          "向用户提问",
    "record_error_solution": "记录错误解决方案",
}



def _tool_context(name: str, args: dict) -> str:
    """从工具参数里提取关键信息，在 ▶ 行显示给用户。"""
    if name == "validate_basin":
        basins = args.get("basin_ids", [])
        s = ", ".join(str(b) for b in basins[:3])
        return f"流域: {s}" + (" ..." if len(basins) > 3 else "")

    if name in ("calibrate_model", "llm_calibrate"):
        model = args.get("model_name", "").upper()
        alg   = args.get("algorithm", "SCE_UA")
        basins = args.get("basin_ids", [])
        bs = ", ".join(str(b) for b in basins[:2]) + (" ..." if len(basins) > 2 else "")
        parts = [p for p in [model, alg, bs] if p]
        return "  |  ".join(parts)

    if name == "evaluate_model":
        d = args.get("calibration_dir", "")
        # 只显示最后一级目录名，避免路径过长
        return d.replace("\\", "/").rstrip("/").split("/")[-1][:50] if d else ""

    if name == "batch_calibrate":
        n = len(args.get("basin_ids", []))
        model = args.get("model_name", "").upper()
        repeat = args.get("repeat_runs", 1)
        s = f"{n} 个流域  |  {model}"
        if repeat > 1:
            s += f"  |  重复 {repeat} 次"
        return s

    if name == "compare_models":
        models = args.get("model_names", [])
        basins = args.get("basin_ids", [])
        return f"{', '.join(str(m).upper() for m in models)}  |  {len(basins)} 个流域"

    if name == "visualize":
        types = args.get("plot_types") or ["timeseries", "scatter"]
        return ", ".join(types)

    if name == "generate_code":
        desc = args.get("task_description", "")
        return (desc[:50] + "...") if len(desc) > 50 else desc

    if name == "run_code":
        fp = args.get("file_path", "")
        return fp.replace("\\", "/").split("/")[-1]

    if name == "create_skill":
        return args.get("skill_name", "")

    if name == "read_file":
        p = args.get("path", "")
        # show only last two path components to keep it concise
        parts = p.replace("\\", "/").split("/")
        return "/".join(parts[-2:]) if len(parts) >= 2 else p

    if name == "inspect_dir":
        p = args.get("path", "")
        parts = p.replace("\\", "/").split("/")
        return "/".join(parts[-2:]) if len(parts) >= 2 else p

    return ""


def _nse_color(nse) -> str:
    """Return Rich color tag for a NSE value."""
    if not isinstance(nse, (int, float)):
        return "dim"
    if nse >= 0.75:
        return "green"
    if nse >= 0.65:
        return "yellow"
    if nse >= 0.5:
        return "dark_orange"
    return "red"


def _result_summary(name: str, result: dict) -> str:
    """工具成功时显示的简要结果（用户模式）。"""
    if name == "validate_basin":
        valid = result.get("valid_basins", result.get("valid", "?"))
        return f"[dim]valid={valid}[/dim]"
    if name in ("calibrate_model", "llm_calibrate"):
        metrics = result.get("metrics", {})
        nse = metrics.get("NSE")
        if nse is not None:
            color = _nse_color(nse)
            return f"[{color}]NSE={nse:.3f}[/{color}]"
        return ""
    if name == "evaluate_model":
        metrics = result.get("metrics", {})
        nse = metrics.get("NSE")
        if nse is not None:
            color = _nse_color(nse)
            return f"[{color}]NSE={nse:.3f}[/{color}]"
        return ""
    if name == "visualize":
        n = result.get("plot_count", 0)
        return f"[dim]{n} 张图片[/dim]"
    if name == "batch_calibrate":
        s = result.get("summary", {})
        mean = s.get("NSE_mean")
        return f"[dim]NSE 均值={mean:.3f}[/dim]" if mean is not None else ""
    if name == "compare_models":
        best = result.get("best_model")
        nse  = result.get("best_nse")
        return f"[dim]最优={best}  NSE={nse:.3f}[/dim]" if best else ""
    if name == "generate_code":
        fp = result.get("file_path", "")
        return f"[dim]{fp.replace(chr(92), '/').split('/')[-1]}[/dim]" if fp else ""
    if name == "run_code":
        rc = result.get("return_code", "?")
        return f"[dim]exit={rc}[/dim]"
    if name == "create_skill":
        sn = result.get("skill_name", "")
        return f"[dim]{sn}[/dim]" if sn else ""
    return ""


class ConsoleUI:
    """Terminal UI for HydroClaw.

    mode="user"  → clean chat interface, essential info only
    mode="dev"   → full execution trace, tool args/results, log output
    """

    def __init__(self, mode: str = "user"):
        assert mode in ("user", "dev"), f"Unknown mode: {mode}"
        self.mode = mode
        self.console = Console(highlight=False)
        self._t0: float = 0.0
        self._step: int = 0
        self._turn: int = 0
        self._current_tool_name: str = ""
        self._current_tool_args: dict = {}

    # ── Banner ────────────────────────────────────────────────────────

    def print_banner(self, tools_count: int, skills: list[dict], model: str):
        self.console.print()

        # Two-column header: branding left, stats right
        left  = Text()
        left.append("HydroClaw", style="bold cyan")
        left.append("  v0.3", style="cyan")
        left.append(f"\n{model}", style="dim")

        right = Text(justify="right")
        right.append(f"{tools_count} tools", style="dim")
        right.append("  |  ", style="dim")
        right.append(f"{len(skills)} skills", style="dim")
        if self.mode == "dev":
            right.append("  |  ", style="dim")
            right.append("DEV MODE", style="bold yellow")

        header_table = Table.grid(expand=True)
        header_table.add_column(ratio=1)
        header_table.add_column(ratio=1, justify="right")
        header_table.add_row(left, right)
        self.console.print(Panel(header_table, border_style="cyan", padding=(0, 2)))

        if skills:
            self.console.print(Padding("[dim]可用技能:[/dim]", (0, 2)))
            skill_table = Table(box=None, show_header=False, padding=(0, 2))
            skill_table.add_column("idx",  style="dim",  width=4)
            skill_table.add_column("name", style="bold cyan", width=22)
            skill_table.add_column("desc", style="dim")
            for i, s in enumerate(skills, 1):
                skill_table.add_row(f"[{i}]", s["name"], s.get("description", "")[:60])
            self.console.print(Padding(skill_table, (0, 2)))

        self.console.print(Rule(style="dim"))
        self.console.print(Padding(
            "[dim]/tasks  /pause  /resume  /help  quit  |  Ctrl+C 中断当前任务[/dim]",
            (0, 2),
        ))
        self.console.print()

    # ── Query ─────────────────────────────────────────────────────────

    def on_query(self, query: str):
        self._step = 0
        self._turn = 0
        self.console.print()
        if self.mode == "user":
            self.console.print(Panel(
                f"[bold]{query}[/bold]",
                border_style="blue",
                title="[blue]You[/blue]",
                title_align="left",
                padding=(0, 1),
            ))
        else:
            self.console.rule("[bold blue]New Query[/bold blue]")
            self.console.print(f"[bold blue]Query:[/bold blue] {query}\n")

    # ── LLM Thinking ─────────────────────────────────────────────────

    @contextmanager
    def thinking(self, turn: int):
        """LLM 思考阶段：用户模式显示 spinner，开发者模式显示分隔线。"""
        self._turn = turn
        if self.mode == "user":
            with self.console.status(
                "[cyan]HydroClaw 正在分析...[/cyan]",
                spinner="dots",
                spinner_style="cyan",
            ):
                yield
        else:
            self.console.rule(
                f"[dim]Turn {turn}  |  LLM thinking...[/dim]",
                style="dim",
            )
            t = time.time()
            yield
            self.console.print(f"  [dim]LLM responded in {time.time()-t:.2f}s[/dim]")

    def on_thought(self, text: str, turn: int):
        """Called when LLM emits reasoning/thinking content."""
        if not text:
            return
        if self.mode == "dev":
            # Show full thinking in a dim panel (collapsible visually)
            preview = text if len(text) <= 800 else text[:800] + f"\n... ({len(text)} chars total)"
            self.console.print(
                Panel(
                    preview,
                    title=f"[dim]Turn {turn} | Thinking[/dim]",
                    border_style="dim",
                    expand=False,
                )
            )
        else:
            # user mode: show a one-line hint that the model is reasoning
            self.console.print(f"  [dim italic]( 推理中... {len(text)} chars )[/dim italic]")

    # ── Tool calls ───────────────────────────────────────────────────

    def on_tool_start(self, name: str, args: dict):
        """工具开始执行前调用。"""
        self._step += 1
        self._t0 = time.time()

        if self.mode == "user":
            # user 模式：spinner 在 suppress_tool_output 里显示，这里只存储信息
            self._current_tool_name = name
            self._current_tool_args = args
        else:
            label  = _TOOL_LABELS.get(name, name)
            ctx    = _tool_context(name, args)
            args_str = json.dumps(args, ensure_ascii=False, indent=2)
            self.console.print(
                f"\n[yellow][CALL][/yellow] [bold]{name}[/bold]"
                + (f"  [dim]{ctx}[/dim]" if ctx else "")
                + f"\n[dim]{args_str}[/dim]"
            )

    def on_tool_end(self, name: str, result: dict, elapsed: float | None = None):
        """工具执行完毕后调用。"""
        if elapsed is None:
            elapsed = time.time() - self._t0
        label   = _TOOL_LABELS.get(name, name)
        success = not result.get("error")

        if self.mode == "user":
            icon = "[green]✓[/green]" if success else "[red]✗[/red]"
            if success:
                summary = _result_summary(name, result)
                self.console.print(
                    f"  {icon}  [bold]{label}[/bold]"
                    f"  [dim]{elapsed:.1f}s[/dim]"
                    + (f"  {summary}" if summary else "")
                )
                # Structured result card for calibration tools
                if name in ("calibrate_model", "llm_calibrate"):
                    self._print_calibration_card(result)
                elif name == "evaluate_model":
                    self._print_eval_card(result)
            else:
                self.console.print(
                    f"  {icon}  [bold]{label}[/bold]"
                    f"  [dim]{elapsed:.1f}s  (LLM 将自动处理)[/dim]"
                )
        else:
            result_str = json.dumps(result, ensure_ascii=False, default=str)
            if len(result_str) > 800:
                result_str = result_str[:800] + " ...(truncated)"
            icon = "[green][OK] [/green]" if success else "[red][ERR][/red]"
            self.console.print(
                f"[bold]{icon} {name}[/bold]  [dim]({elapsed:.2f}s)[/dim]\n"
                f"[dim]{result_str}[/dim]\n"
            )

    def _print_calibration_card(self, result: dict):
        """Print a structured parameter + metric card after calibration."""
        params  = result.get("best_params") or {}
        metrics = result.get("metrics") or {}
        if not params and not metrics:
            return

        # Build two side-by-side mini-tables using Table.grid
        grid = Table.grid(expand=False, padding=(0, 3))
        grid.add_column()
        grid.add_column()

        # Params table
        if params:
            p_table = Table(
                box=box.SIMPLE, show_header=True, header_style="dim",
                padding=(0, 1), min_width=22,
            )
            p_table.add_column("参数", style="cyan",  width=8)
            p_table.add_column("最优值",              width=12, justify="right")
            for k, v in params.items():
                p_table.add_row(k, f"{v:.4f}" if isinstance(v, float) else str(v))
        else:
            p_table = Text()

        # Metrics table
        if metrics:
            m_table = Table(
                box=box.SIMPLE, show_header=True, header_style="dim",
                padding=(0, 1), min_width=22,
            )
            m_table.add_column("指标", style="cyan", width=8)
            m_table.add_column("值",                  width=10, justify="right")
            show_keys = ["NSE", "KGE", "RMSE", "Bias"]
            for k in show_keys:
                v = metrics.get(k)
                if v is None:
                    continue
                color = _nse_color(v) if k == "NSE" else "default"
                m_table.add_row(k, f"[{color}]{v:.4f}[/{color}]")
        else:
            m_table = Text()

        grid.add_row(p_table, m_table)
        self.console.print(Padding(grid, (0, 6)))

    def _print_eval_card(self, result: dict):
        """Print compact evaluation metrics card."""
        metrics = result.get("metrics") or {}
        if not metrics:
            return
        parts = []
        for k in ("NSE", "KGE", "RMSE"):
            v = metrics.get(k)
            if v is None:
                continue
            color = _nse_color(v) if k == "NSE" else "dim"
            parts.append(f"[dim]{k}=[/dim][{color}]{v:.3f}[/{color}]")
        if parts:
            self.console.print(Padding("  ".join(parts), (0, 8)))

    def ask_user(self, question: str, context: str | None = None) -> str:
        """Display a question panel and read one line of user input.

        Works correctly even when called from inside suppress_tool_output
        (which redirects sys.stdout), because rich Console holds a reference
        to the original stdout and sys.__stdin__ is never redirected.
        """
        import sys
        self.console.print()
        body = f"[bold]{question}[/bold]"
        if context:
            body = f"[dim]{context}[/dim]\n\n" + body
        self.console.print(Panel(
            body,
            title="[yellow]需要确认[/yellow]",
            border_style="yellow",
            padding=(0, 1),
        ))
        self.console.print("[yellow]  > [/yellow]", end="")
        try:
            answer = sys.__stdin__.readline().strip()
        except (AttributeError, EOFError):
            answer = ""
        self.console.print()
        return answer

    @contextmanager
    def suppress_tool_output(self, name: str):
        """用户模式：屏蔽工具执行期间的第三方输出，并显示旋转 spinner。

        - 用 console.status() 显示旋转 spinner（与 LLM thinking 体验一致）
        - 将 sys.stdout/stderr 重定向到 StringIO，拦截 hydromodel tqdm/print
        - rich Console 在初始化时绑定原始 stdout，不受重定向影响
        - ask_user 工具必须直接访问终端 I/O，永远不压制
        开发者模式：直接放行所有输出，hydromodel 进度条完整可见。
        """
        if self.mode != "user" or name == "ask_user":
            yield
            return

        null_io = io.StringIO()
        label   = _TOOL_LABELS.get(name, name)
        args    = getattr(self, "_current_tool_args", {}) or {}
        ctx     = _tool_context(name, args)
        status_text = f"[cyan]{label}[/cyan]" + (f"  [dim]{ctx}[/dim]" if ctx else "")

        with contextlib.redirect_stdout(null_io), contextlib.redirect_stderr(null_io):
            with self.console.status(status_text, spinner="dots", spinner_style="cyan"):
                yield

    # ── Final answer ─────────────────────────────────────────────────

    def on_answer(self, text: str, total_turns: int):
        self.console.print()
        if self.mode == "user":
            self.console.print(Rule(style="cyan"))
            self.console.print(Padding(Markdown(text), (0, 2)))
            self.console.print(Rule(style="cyan"))
        else:
            self.console.print(Panel(
                Markdown(text),
                title=f"[green]Answer[/green]  [dim]({total_turns} turns)[/dim]",
                border_style="green",
                padding=(0, 1),
            ))
        self.console.print()

    def on_session_summary(self, total_turns: int, elapsed_s: float, tokens: dict):
        """Print a compact session stats footer (user mode only)."""
        if self.mode != "user":
            return
        total_tok = tokens.get("total_tokens", 0)
        prompt    = tokens.get("prompt_tokens", 0)
        compl     = tokens.get("completion_tokens", 0)
        tok_str   = (
            f"[dim]tokens:[/dim] [cyan]{total_tok:,}[/cyan]"
            f" [dim](prompt {prompt:,} / compl {compl:,})[/dim]"
        )
        time_str  = f"[dim]time:[/dim] [cyan]{elapsed_s:.1f}s[/cyan]"
        turns_str = f"[dim]turns:[/dim] [cyan]{total_turns}[/cyan]"
        self.console.print(
            Padding(f"  {turns_str}    {time_str}    {tok_str}", (0, 2))
        )

    # ── Errors ───────────────────────────────────────────────────────

    def on_error(self, msg: str):
        self.console.print(f"\n[red bold]Error:[/red bold] {msg}\n")

    def on_max_turns(self):
        self.console.print(
            "\n[yellow]已达到最大步骤数限制，请检查已有结果。[/yellow]\n"
        )

    # ── Task progress ────────────────────────────────────────────────

    def on_task_progress(self, workspace):
        """Print a compact task progress bar after task state changes."""
        import json
        from pathlib import Path
        state_file = Path(workspace) / "task_state.json"
        if not state_file.exists():
            return
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
        except Exception:
            return

        tasks = data.get("tasks", [])
        if not tasks:
            return

        total   = len(tasks)
        done    = sum(1 for t in tasks if t["status"] == "done")
        failed  = sum(1 for t in tasks if t["status"] == "failed")
        pending = sum(1 for t in tasks if t["status"] == "pending")

        # Build compact bar: [+++..---...   ]
        bar_w = 20
        done_w    = round(done    / total * bar_w)
        failed_w  = round(failed  / total * bar_w)
        pending_w = bar_w - done_w - failed_w

        bar = (
            f"[green]{'+'*done_w}[/green]"
            f"[red]{'-'*failed_w}[/red]"
            f"[dim]{'.'*pending_w}[/dim]"
        )
        pct = done / total * 100
        status_str = f"[green]{done}[/green] 完成"
        if failed:
            status_str += f" / [red]{failed}[/red] 失败"
        if pending:
            status_str += f" / [dim]{pending}[/dim] 待执行"

        self.console.print(
            f"  [dim]任务进度[/dim] [{bar}] {pct:.0f}%  {status_str}  "
            f"[dim]共 {total} 个[/dim]"
        )

    def show_task_list(self, workspace):
        """Print full task list table (used by /tasks command)."""
        import json
        from pathlib import Path
        from rich.table import Table

        state_file = Path(workspace) / "task_state.json"
        if not state_file.exists():
            self.console.print("[dim]当前没有活跃的任务列表。[/dim]")
            return
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
        except Exception:
            self.console.print("[red]task_state.json 读取失败。[/red]")
            return

        tasks = data.get("tasks", [])
        goal  = data.get("goal", "")
        total = len(tasks)
        done  = sum(1 for t in tasks if t["status"] == "done")

        self.console.print()
        self.console.print(f"  [bold cyan]任务列表[/bold cyan]  [dim]{done}/{total} 完成[/dim]")
        if goal:
            self.console.print(f"  [dim]目标：{goal}[/dim]")
        self.console.print()

        table = Table(box=None, show_header=True, padding=(0, 2))
        table.add_column("",       width=3,  style="dim")
        table.add_column("ID",     width=10, style="dim")
        table.add_column("描述",   min_width=30)
        table.add_column("状态",   width=8)
        table.add_column("NSE",    width=7, justify="right")

        icons = {"done": "[green]+[/green]", "failed": "[red]x[/red]",
                 "running": "[cyan]~[/cyan]", "pending": " "}
        colors = {"done": "green", "failed": "red", "running": "cyan", "pending": "dim"}

        for t in tasks:
            st  = t["status"]
            nse = ""
            if st == "done" and t.get("result"):
                v = t["result"].get("NSE") or t["result"].get("nse")
                if isinstance(v, (int, float)):
                    nse = f"{v:.3f}"
            desc = t.get("description", t["id"])
            if len(desc) > 50:
                desc = desc[:48] + ".."
            table.add_row(
                icons.get(st, "?"),
                t["id"],
                f"[{colors.get(st,'default')}]{desc}[/{colors.get(st,'default')}]",
                st,
                nse,
            )
        self.console.print(table)
        self.console.print()

    # ── Dev-only ─────────────────────────────────────────────────────

    def dev_log(self, msg: str):
        if self.mode == "dev":
            self.console.print(f"[dim magenta][DBG][/dim magenta] {msg}")

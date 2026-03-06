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
import threading
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

# ── Human-readable labels for each tool ─────────────────────────────
_TOOL_LABELS: dict[str, str] = {
    "validate_basin":   "验证流域数据",
    "calibrate_model":  "执行模型率定",
    "evaluate_model":   "评估模型性能",
    "visualize":        "生成可视化图形",
    "llm_calibrate":    "LLM 智能率定",
    "batch_calibrate":  "批量率定流域",
    "compare_models":   "多模型对比",
    "generate_code":    "生成分析代码",
    "run_code":         "执行分析脚本",
    "run_simulation":   "运行模型模拟",
    "create_skill":     "创建新技能",
}

# 这些工具运行时间长，需要周期性心跳提示
_LONG_RUNNING_TOOLS = {
    "calibrate_model", "llm_calibrate", "batch_calibrate",
    "compare_models", "run_code", "run_simulation",
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

    return ""


def _result_summary(name: str, result: dict) -> str:
    """工具成功时显示的简要结果（用户模式）。"""
    if name == "validate_basin":
        valid = result.get("valid_basins", result.get("valid", "?"))
        return f"[dim]valid={valid}[/dim]"
    if name in ("calibrate_model", "llm_calibrate"):
        metrics = result.get("metrics", {})
        nse = metrics.get("NSE")
        return f"[dim]训练期 NSE={nse:.3f}[/dim]" if nse is not None else ""
    if name == "evaluate_model":
        metrics = result.get("metrics", {})
        nse = metrics.get("NSE")
        return f"[dim]测试期 NSE={nse:.3f}[/dim]" if nse is not None else ""
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

    # ── Banner ────────────────────────────────────────────────────────

    def print_banner(self, tools_count: int, skills: list[dict], model: str):
        self.console.print()
        title = Text()
        title.append("HydroClaw v0.3", style="bold cyan")
        title.append(f"  |  {model}", style="dim")
        title.append(f"  |  {tools_count} Tools", style="dim")
        title.append(f"  |  {len(skills)} Skills", style="dim")
        self.console.print(Panel(title, border_style="cyan", padding=(0, 2)))

        if skills:
            table = Table(box=None, show_header=False, padding=(0, 2))
            table.add_column("idx",  style="dim", width=4)
            table.add_column("name", style="bold", width=28)
            table.add_column("desc")
            for i, s in enumerate(skills, 1):
                table.add_row(f"[{i}]", s["name"], s["description"])
            self.console.print(Padding(table, (0, 2)))
            self.console.print(Padding(
                "[dim]Tip: 如需以上技能无法覆盖的功能，直接描述需求，系统将自动生成新技能。[/dim]",
                (0, 4),
            ))

        self.console.print(Rule(style="dim"))
        self.console.print("[dim]输入你的问题（中文或英文）。输入 quit 退出，Ctrl+C 中断当前任务。[/dim]")
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

    # ── Tool calls ───────────────────────────────────────────────────

    def on_tool_start(self, name: str, args: dict):
        """工具开始执行前调用。"""
        self._step += 1
        self._t0 = time.time()
        label = _TOOL_LABELS.get(name, name)
        ctx   = _tool_context(name, args)

        if self.mode == "user":
            # 静态行：不用 spinner，避免与 hydromodel tqdm/print 冲突
            ctx_part = f"  [dim]{ctx}[/dim]" if ctx else ""
            self.console.print(f"  [cyan]▶[/cyan]  [bold]{label}[/bold]{ctx_part}")
        else:
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
            else:
                # 用户界面不暴露原始错误，LLM 会自行处理重试
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

    @contextmanager
    def suppress_tool_output(self, name: str):
        """用户模式：屏蔽工具执行期间的所有第三方 stdout/stderr 输出。

        - 将 sys.stdout / sys.stderr 重定向到 StringIO，拦截 hydromodel 的
          print() 和 tqdm 进度条（tqdm 在初始化时绑定 sys.stderr）。
        - rich 的 Console 在创建时已绑定原始 stdout，不受影响，仍可正常渲染。
        - 对于长耗时工具，后台线程每 30s 打印一次计时心跳。
        开发者模式：直接放行所有输出，hydromodel 进度条完整可见。
        """
        if self.mode != "user":
            yield
            return

        null_io    = io.StringIO()
        stop_event = threading.Event()
        label      = _TOOL_LABELS.get(name, name)
        start_time = time.time()
        is_long    = name in _LONG_RUNNING_TOOLS

        def _heartbeat():
            """每 30s 打印一次计时行，避免用户以为程序卡死。

            使用 sys.__stdout__（Python 原始 stdout，不受 redirect_stdout 影响）
            直接写入，绕过 rich Console 可能在运行时读 sys.stdout 的问题。
            """
            import sys as _sys
            out = _sys.__stdout__
            while not stop_event.wait(30):
                elapsed = time.time() - start_time
                mins, secs = divmod(int(elapsed), 60)
                t_str = f"{mins}m {secs:02d}s" if mins else f"{secs}s"
                try:
                    out.write(f"  ◷  {label} 运行中 {t_str}...\n")
                    out.flush()
                except Exception:
                    pass

        # 重定向 stdout/stderr 到 null，拦截所有第三方 print/tqdm
        with contextlib.redirect_stdout(null_io), contextlib.redirect_stderr(null_io):
            timer = None
            if is_long:
                timer = threading.Thread(target=_heartbeat, daemon=True)
                timer.start()
            try:
                yield
            finally:
                stop_event.set()
                if timer:
                    timer.join(timeout=2)

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

    # ── Errors ───────────────────────────────────────────────────────

    def on_error(self, msg: str):
        self.console.print(f"\n[red bold]Error:[/red bold] {msg}\n")

    def on_max_turns(self):
        self.console.print(
            "\n[yellow]已达到最大步骤数限制，请检查已有结果。[/yellow]\n"
        )

    # ── Dev-only ─────────────────────────────────────────────────────

    def dev_log(self, msg: str):
        if self.mode == "dev":
            self.console.print(f"[dim magenta][DBG][/dim magenta] {msg}")

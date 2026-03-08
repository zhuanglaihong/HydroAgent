"""
Author: HydroClaw Team
Date: 2026-02-08
Description: CLI entry point for HydroClaw.

Usage:
  python -m hydroclaw                      # user mode (interactive)
  python -m hydroclaw "rate GR4J basin X"  # user mode (single query)
  python -m hydroclaw --dev                # developer mode (interactive)
  python -m hydroclaw --dev "query"        # developer mode (single query)
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="HydroClaw - LLM-driven hydrological model calibration agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  (default)  User mode    - clean chat interface, essential info only
  --dev      Developer mode - full tool args/results, log output

Examples:
  python -m hydroclaw
  python -m hydroclaw "率定GR4J模型，流域12025000"
  python -m hydroclaw --dev "批量率定三个流域"
        """,
    )
    parser.add_argument("query", nargs="?", help="Query to run (omit for interactive mode)")
    parser.add_argument("--dev", action="store_true", help="Developer mode: show full execution details and logs")
    parser.add_argument("--config", "-c", default=None, help="Path to config.json")
    parser.add_argument("--workspace", "-w", default=None, help="Working directory for results")
    parser.add_argument("--log-file", default=None, help="Log file path (dev mode default: logs/)")

    args = parser.parse_args()

    mode = "dev" if args.dev else "user"

    # Create UI first so we can use its console for logging in dev mode
    from hydroclaw.ui import ConsoleUI
    ui = ConsoleUI(mode=mode)

    # Setup logging: visible in dev mode, suppressed in user mode
    _setup_logging(dev=args.dev, log_file=args.log_file, console=ui.console)

    workspace = Path(args.workspace) if args.workspace else Path(".")

    # ── 首次启动配置向导 ──────────────────────────────────────────────
    # 在创建 Agent（会触发 LLM 初始化）之前检测配置是否完整
    _maybe_run_setup_wizard(ui, args.config)

    # Import agent here to avoid slow startup for --help
    from hydroclaw.agent import HydroClaw
    agent = HydroClaw(config_path=args.config, workspace=workspace, ui=ui)

    # Test LLM connectivity before anything else
    _test_llm_connection(ui, agent)

    if args.query:
        agent.run(args.query)
    else:
        _print_banner(ui, agent)
        _interactive_loop(ui, agent)


def _print_banner(ui, agent):
    """Print startup banner with skill list and tips."""
    from hydroclaw.tools import discover_tools
    tools = discover_tools()
    skills = agent.skill_registry.list_all()
    model = agent.cfg.get("llm", {}).get("model", "unknown")
    ui.print_banner(tools_count=len(tools), skills=skills, model=model)


def _interactive_loop(ui, agent):
    """Interactive REPL loop with slash commands and safe exit."""
    while True:
        try:
            query = ui.console.input("[bold cyan]You>[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            _safe_exit(ui, agent)
            break

        if not query:
            continue

        # ── Slash commands ─────────────────────────────────────────
        if query.startswith("/"):
            cmd = query.lower().split()[0]

            if cmd in ("/quit", "/exit", "/q"):
                if _safe_exit(ui, agent):
                    break
                continue

            if cmd in ("/tasks", "/status"):
                ui.show_task_list(agent.workspace)
                continue

            if cmd == "/pause":
                agent.request_pause()
                ui.console.print(
                    "[yellow]已请求暂停。[/yellow] "
                    "[dim]Agent 将在当前任务完成后暂停，任务状态已自动保存。[/dim]"
                )
                continue

            if cmd == "/resume":
                _resume_tasks(ui, agent)
                continue

            if cmd in ("/help", "/?"):
                _print_help(ui)
                continue

            ui.console.print(f"[dim]未知命令 {cmd}，输入 /help 查看可用命令。[/dim]")
            continue

        # ── Exit keywords ──────────────────────────────────────────
        if query.lower() in ("quit", "exit", "q", "bye"):
            if _safe_exit(ui, agent):
                break
            continue

        # ── Normal query ───────────────────────────────────────────
        try:
            agent.run(query)
        except KeyboardInterrupt:
            ui.console.print(
                "\n[yellow]已中断。[/yellow] [dim]任务状态已保存，输入 /resume 可继续。[/dim]"
            )
        except Exception as e:
            ui.on_error(str(e))
            logging.getLogger(__name__).error(f"Unhandled error: {e}", exc_info=True)


def _safe_exit(ui, agent) -> bool:
    """Check for pending tasks and confirm before exit. Returns True if should exit."""
    import json
    from pathlib import Path

    state_file = Path(agent.workspace) / "task_state.json"
    if state_file.exists():
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
            pending = sum(1 for t in data.get("tasks", []) if t["status"] == "pending")
            if pending > 0:
                ui.console.print(
                    f"\n[yellow]注意：[/yellow] 还有 [bold]{pending}[/bold] 个任务未完成。"
                    f"任务状态已保存，下次运行输入 /resume 可继续。"
                )
                answer = ui.console.input(
                    "[dim]确认退出？(y/N)>[/dim] "
                ).strip().lower()
                if answer not in ("y", "yes"):
                    return False
        except Exception:
            pass

    ui.console.print("[dim]Bye![/dim]")
    return True


def _resume_tasks(ui, agent):
    """Resume pending tasks from task_state.json via a new agent run."""
    import json
    from pathlib import Path

    state_file = Path(agent.workspace) / "task_state.json"
    if not state_file.exists():
        ui.console.print("[dim]没有找到可恢复的任务。[/dim]")
        return

    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        ui.console.print("[red]task_state.json 读取失败。[/red]")
        return

    pending = [t for t in data.get("tasks", []) if t["status"] == "pending"]
    goal    = data.get("goal", "之前的批量任务")
    done    = sum(1 for t in data.get("tasks", []) if t["status"] == "done")
    total   = len(data.get("tasks", []))

    if not pending:
        ui.console.print("[green]所有任务已完成，无需恢复。[/green]")
        return

    ui.console.print(
        f"[cyan]恢复任务：[/cyan] {len(pending)} 个待执行 / {done}/{total} 已完成"
    )
    resume_query = f"继续执行之前的批量任务（{goal}），跳过已完成的部分，继续剩余 {len(pending)} 个任务。"
    try:
        agent.run(resume_query)
    except KeyboardInterrupt:
        ui.console.print("\n[yellow]已中断。[/yellow] [dim]进度已保存。[/dim]")


def _print_help(ui):
    """Print available slash commands."""
    from rich.table import Table
    table = Table(box=None, show_header=False, padding=(0, 2))
    table.add_column("cmd",  style="bold cyan", width=16)
    table.add_column("desc")
    cmds = [
        ("/tasks",  "显示当前任务列表和进度"),
        ("/pause",  "请求在当前任务完成后暂停（任务状态自动保存）"),
        ("/resume", "恢复上次未完成的批量任务"),
        ("/help",   "显示此帮助"),
        ("/quit",   "安全退出（有未完成任务时提示确认）"),
    ]
    for cmd, desc in cmds:
        table.add_row(cmd, desc)
    ui.console.print()
    ui.console.print(table)
    ui.console.print("[dim]  普通文本直接发送给 AI。Ctrl+C 中断当前运行中的任务。[/dim]")
    ui.console.print()


def _setup_logging(dev: bool, log_file: str | None, console=None):
    """Configure logging.

    User mode: only write to log file, suppress stderr output.
    Dev mode:  write to both rich console (stderr) and log file.
    """
    handlers = []

    # Always write to a log file
    log_path = None
    if log_file:
        log_path = Path(log_file)
    else:
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = logs_dir / f"hydroclaw_{ts}.log"

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    handlers.append(file_handler)

    if dev:
        # Rich handler: logs appear in the terminal as structured output
        from rich.logging import RichHandler
        rich_handler = RichHandler(
            console=console,
            show_time=True,
            show_level=True,
            show_path=False,
            rich_tracebacks=True,
            markup=False,
            level=logging.DEBUG,
        )
        handlers.append(rich_handler)
        root_level = logging.DEBUG
    else:
        # User mode: logs go to file only, nothing on terminal
        root_level = logging.INFO

    logging.basicConfig(level=root_level, handlers=handlers, force=True)

    # Always quiet noisy third-party libraries
    for noisy in (
        "httpx", "openai", "urllib3", "matplotlib", "PIL",
        "markdown_it",           # rich 的 markdown 解析器，debug 日志极多
        "rich",                  # rich 内部日志
        "asyncio",
        "charset_normalizer",
        "h11", "h2", "httpcore",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _maybe_run_setup_wizard(ui, explicit_config_path: str | None):
    """如果配置不完整，运行首次启动向导。

    检测逻辑：
    - 先用当前配置源（含 ~/.hydroclaw/config.json + hydroagent legacy）加载
    - 若 api_key 或 dataset_dir 缺失，触发向导
    - 显式指定了 --config 则跳过（用户已手动管理配置）
    """
    if explicit_config_path:
        return  # 用户已明确指定配置，信任他

    from hydroclaw.config import load_config
    from hydroclaw.setup_wizard import needs_setup, run_wizard

    cfg = load_config()
    if needs_setup(cfg):
        ui.console.print()
        ui.console.print(
            "[yellow]⚠  未检测到完整配置（API Key 或数据集路径缺失），"
            "需要完成初始化设置。[/yellow]"
        )
        run_wizard(ui.console)


def _test_llm_connection(ui, agent):
    """Test LLM API connectivity once at startup."""
    ui.console.print("[dim]正在测试 LLM 连接...[/dim]", end="")
    ok, err = agent.llm.test_connection()
    if ok:
        model = agent.cfg.get("llm", {}).get("model", "")
        ui.console.print(f"\r[green]✓[/green] LLM 连接正常  [dim]{model}[/dim]")
    else:
        ui.console.print(f"\r[red]✗[/red] LLM 连接失败: [dim]{err[:120]}[/dim]")


if __name__ == "__main__":
    main()

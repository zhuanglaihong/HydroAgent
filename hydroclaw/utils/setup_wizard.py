"""
Author: HydroClaw Team
Date: 2026-03-06
Description: 首次启动配置向导 (First-run setup wizard).

当检测到必要配置缺失时自动触发，通过交互式问答引导用户完成基础配置，
保存到 ~/.hydroclaw/config.json，后续启动直接读取，无需重复配置。
"""

import json
import os
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.text import Text

# 配置文件保存在项目根目录（hydroclaw 包的上一级）
USER_CONFIG_PATH = Path(__file__).parent.parent / "hydroclaw_config.json"

# 必填字段缺失则触发向导
_REQUIRED_CHECKS = [
    lambda cfg: bool(cfg.get("llm", {}).get("api_key")),
    lambda cfg: bool(cfg.get("paths", {}).get("dataset_dir")),
]


def needs_setup(cfg: dict) -> bool:
    """检查是否需要运行配置向导。"""
    return not all(check(cfg) for check in _REQUIRED_CHECKS)


def run_wizard(console: Console) -> dict:
    """运行交互式配置向导，返回用户填写的配置 dict。

    向导结束后自动保存到 ~/.hydroclaw/config.json。
    """
    console.print()
    console.print(Panel(
        Text("HydroClaw 首次配置向导", style="bold cyan", justify="center"),
        subtitle="[dim]配置完成后自动保存，后续启动无需重复设置[/dim]",
        border_style="cyan",
        padding=(0, 4),
    ))
    console.print()
    console.print("[dim]按 Enter 使用方括号内的默认值，带 * 的字段为必填项。[/dim]")
    console.print()

    cfg: dict = {}

    # ── LLM 配置 ──────────────────────────────────────────────────────
    console.print(Rule("[bold]LLM 配置[/bold]", style="blue"))
    console.print()

    llm_presets = {
        "1": {
            "name": "Qwen/DeepSeek (阿里云 DashScope)",
            "model": "deepseek-v3.1",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        },
        "2": {
            "name": "DeepSeek 官方",
            "model": "deepseek-chat",
            "base_url": "https://api.deepseek.com/v1",
        },
        "3": {
            "name": "OpenAI",
            "model": "gpt-4o",
            "base_url": "https://api.openai.com/v1",
        },
        "4": {
            "name": "本地 Ollama",
            "model": "qwen2.5:7b",
            "base_url": "http://localhost:11434/v1",
        },
        "5": {
            "name": "自定义",
            "model": "",
            "base_url": "",
        },
    }

    console.print("请选择 LLM 服务商：")
    for k, v in llm_presets.items():
        console.print(f"  [{k}] {v['name']}")
    console.print()

    preset_choice = Prompt.ask(
        "  选择", choices=list(llm_presets.keys()), default="1", console=console
    )
    preset = llm_presets[preset_choice]
    console.print()

    model = Prompt.ask(
        "  模型名称",
        default=preset["model"] or "deepseek-v3.1",
        console=console,
    )
    base_url = Prompt.ask(
        "  API Base URL",
        default=preset["base_url"] or "https://api.openai.com/v1",
        console=console,
    )

    # API Key 不回显
    console.print("  [bold]* API Key[/bold] [dim](输入后不显示)[/dim]")
    api_key = ""
    while not api_key.strip():
        api_key = console.input("    ").strip()
        if not api_key:
            console.print("  [red]API Key 不能为空，请重新输入。[/red]")

    cfg["llm"] = {
        "model": model,
        "base_url": base_url,
        "api_key": api_key,
        "temperature": 0.1,
        "max_tokens": 20000,
        "timeout": 60,
    }

    # ── 路径配置 ───────────────────────────────────────────────────────
    console.print()
    console.print(Rule("[bold]数据路径配置[/bold]", style="blue"))
    console.print()

    dataset_dir = ""
    while not dataset_dir.strip():
        dataset_dir = Prompt.ask(
            "  [bold]* CAMELS 数据集根目录[/bold] [dim](含 basin_mean_forcing 等子目录)[/dim]",
            default="",
            console=console,
        ).strip()
        if not dataset_dir:
            console.print("  [red]数据集路径不能为空，请输入实际路径。[/red]")
        elif not Path(dataset_dir).exists():
            console.print(f"  [yellow]警告：路径 {dataset_dir} 不存在，请确认后继续。[/yellow]")
            if not Confirm.ask("  仍然使用此路径？", default=False, console=console):
                dataset_dir = ""

    results_dir = Prompt.ask(
        "  结果输出目录",
        default="results",
        console=console,
    ).strip() or "results"

    cfg["paths"] = {
        "dataset_dir": dataset_dir,
        "results_dir": results_dir,
    }

    # ── 可选：默认模型和训练期 ────────────────────────────────────────
    console.print()
    if Confirm.ask(
        "[dim]是否配置默认模型和训练期？（可跳过，直接在对话中指定）[/dim]",
        default=False,
        console=console,
    ):
        console.print()
        console.print(Rule("[bold]默认运行参数[/bold] [dim]（可选）[/dim]", style="dim"))
        console.print()

        default_model = Prompt.ask(
            "  默认水文模型",
            choices=["xaj", "gr4j", "gr5j", "gr6j"],
            default="xaj",
            console=console,
        )
        train_start = Prompt.ask(
            "  训练期开始", default="2000-01-01", console=console
        )
        train_end = Prompt.ask(
            "  训练期结束", default="2009-12-31", console=console
        )
        test_start = Prompt.ask(
            "  测试期开始", default="2010-01-01", console=console
        )
        test_end = Prompt.ask(
            "  测试期结束", default="2014-12-31", console=console
        )

        cfg["defaults"] = {
            "model": default_model,
            "algorithm": "SCE_UA",
            "train_period": [train_start, train_end],
            "test_period": [test_start, test_end],
            "warmup": 365,
        }

    # ── 保存 ─────────────────────────────────────────────────────────
    save_path = _save_config(cfg, console)

    console.print()
    console.print(Panel(
        f"[green]✓[/green] 配置已保存至 [bold]{save_path}[/bold]\n\n"
        "[dim]如需修改，直接编辑该文件或删除后重新运行向导。[/dim]",
        border_style="green",
        padding=(0, 2),
    ))
    console.print()

    return cfg


def _save_config(cfg: dict, console: Console) -> Path:
    """保存配置到 ~/.hydroclaw/config.json，API Key 提示是否也保存到环境变量。"""
    USER_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

    # 不把 API Key 明文写进文件，改成存环境变量名的引用
    save_cfg = json.loads(json.dumps(cfg))  # deep copy
    api_key = save_cfg.get("llm", {}).pop("api_key", "")

    # 询问保存方式
    console.print()
    console.print(Rule("[bold]API Key 保存方式[/bold]", style="dim"))
    console.print()
    console.print("  [1] 明文写入配置文件 [dim]（方便，但有泄露风险）[/dim]")
    console.print("  [2] 仅保存环境变量名引用，Key 需自行设置环境变量 [dim]（推荐）[/dim]")
    console.print()

    choice = Prompt.ask("  选择", choices=["1", "2"], default="1", console=console)

    if choice == "1":
        save_cfg["llm"]["api_key"] = api_key
    else:
        env_var = Prompt.ask(
            "  环境变量名",
            default="HYDROCLAW_API_KEY",
            console=console,
        )
        save_cfg["llm"]["api_key_env"] = env_var
        console.print(
            f"\n  [yellow]请在系统环境变量中设置：[/yellow]\n"
            f"  [bold]  {env_var}={api_key[:8]}...[/bold]  [dim]（完整 Key 请自行填写）[/dim]"
        )

    USER_CONFIG_PATH.write_text(
        json.dumps(save_cfg, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return USER_CONFIG_PATH


def load_user_config_path() -> Path | None:
    """返回用户配置文件路径（如果存在）。"""
    return USER_CONFIG_PATH if USER_CONFIG_PATH.exists() else None

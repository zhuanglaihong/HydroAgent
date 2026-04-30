"""
Exp3 绘图脚本 — Agent Capability Breadth
输出目录：plot/exp3/

图表清单：
  fig6_tool_sequence_gantt.png  — 工具调用序列甘特图（A01-A06 6个场景）

核心结论：
  - 6个不同自然语言表达的场景，Agent 全部正确识别工具调用序列（tool_match=6/6）
  - 不同场景下工具序列差异巨大（A03 LLM率定19次调用, A05 代码分析29次）
    ——证明 Agent 能根据任务类型自适应规划，而非固定模板
  - A04 batch_planning 出现了 create_task_list / get_pending_tasks / update_task
    ——展示了 Agent 的批量任务管理能力

数据来源：results/paper/exp3/exp3_results.json
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

ROOT   = Path(__file__).parent.parent
DATA   = ROOT / "results/paper/exp3/exp3_results.json"
OUTDIR = Path(__file__).parent / "exp3"
OUTDIR.mkdir(exist_ok=True)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.spines.top":   False,
    "axes.spines.right": False,
})

# 工具颜色映射（不依赖红绿区分，色盲友好）
TOOL_COLORS = {
    "validate_basin":   "#4878CF",   # 蓝
    "calibrate_model":  "#D65F5F",   # 红
    "evaluate_model":   "#6ACC65",   # 绿
    "llm_calibrate":    "#FF9F40",   # 橙
    "read_file":        "#C4AD66",   # 黄棕
    "inspect_dir":      "#BBBBBB",   # 灰
    "generate_code":    "#82C4E0",   # 浅蓝
    "run_code":         "#956CB4",   # 紫
    "visualize":        "#8172B2",   # 深紫
    "create_task_list": "#FFD700",   # 金
    "get_pending_tasks":"#FFA500",   # 暗橙
    "update_task":      "#FF6347",   # 番茄红
}
DEFAULT_COLOR = "#DDDDDD"

# 场景描述（替换 JSON 中的乱码）
SCENARIO_LABELS = {
    "A01": "A01 Standard\ncalibration",
    "A02": "A02 Custom\nalgo params",
    "A03": "A03 LLM\ncalibration",
    "A04": "A04 Batch\nplanning",
    "A05": "A05 Code\nanalysis",
    "A06": "A06 Missing\ninfo handling",
}


def load_data():
    with open(DATA, encoding="utf-8") as f:
        return json.load(f)


# ─────────────────────────────────────────────────────────────────────────────
# Fig.6  Tool call sequence Gantt chart
# ─────────────────────────────────────────────────────────────────────────────
def fig6_tool_sequence_gantt(data: dict):
    results = data["sections"]["A"]["results"]

    fig, ax = plt.subplots(figsize=(14, 5.0))

    y_ticks = []
    y_labels_list = []
    all_tools = set()

    for yi, r in enumerate(results):
        sid = r["id"]
        tools = r["actual_tools"]
        tool_match = r["tool_match"]
        success = r["success"]

        y = len(results) - 1 - yi  # top to bottom
        y_ticks.append(y)
        y_labels_list.append(SCENARIO_LABELS.get(sid, sid))

        for xi, tool in enumerate(tools):
            color = TOOL_COLORS.get(tool, DEFAULT_COLOR)
            rect = plt.Rectangle((xi, y - 0.38), 1, 0.76,
                                  facecolor=color, edgecolor="white",
                                  linewidth=0.5, zorder=3)
            ax.add_patch(rect)
            # Label inside block if wide enough
            ax.text(xi + 0.5, y, tool.replace("_", "\n"),
                    ha="center", va="center", fontsize=4.5,
                    color="white" if color not in ("#BBBBBB", "#DDDDDD",
                                                   "#C4AD66", "#FFD700") else "#333",
                    zorder=4)
            all_tools.add(tool)

        # Right-side annotation: tool count + match check
        total = len(tools)
        check = "✓" if tool_match else "✗"
        color_check = "#2ca02c" if tool_match else "#d62728"
        ax.text(total + 0.3, y,
                f"{check} {total} calls",
                va="center", fontsize=8, color=color_check, fontweight="bold")

    ax.set_yticks(y_ticks)
    ax.set_yticklabels(y_labels_list, fontsize=8.5)
    ax.set_xlabel("Tool call step", fontsize=9)
    ax.set_xlim(0, max(len(r["actual_tools"]) for r in results) + 4)
    ax.set_ylim(-0.7, len(results) - 0.3)
    ax.xaxis.set_major_locator(plt.MultipleLocator(2))
    ax.tick_params(labelsize=8)
    ax.grid(axis="x", ls=":", lw=0.4, alpha=0.4)
    ax.axvline(0, color="#ccc", lw=0.5)

    # Legend
    legend_tools = [t for t in TOOL_COLORS if t in all_tools]
    handles = [mpatches.Patch(facecolor=TOOL_COLORS[t],
                               edgecolor="white", label=t.replace("_", " "))
               for t in legend_tools]
    ax.legend(handles=handles, fontsize=7, loc="lower right",
              ncol=3, framealpha=0.9, title="Tool", title_fontsize=7.5)

    ax.set_title(
        "Figure 6. Agent Tool Call Sequences — 6 Natural Language Scenarios (Exp. 3-A)\n"
        "Each row = one scenario; each block = one tool call; ✓ = correct tool sequence",
        fontsize=9.5, fontweight="bold")

    out = OUTDIR / "fig6_tool_sequence_gantt.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {out.name}")


# ── main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Exp3 figures →", OUTDIR)
    data = load_data()
    fig6_tool_sequence_gantt(data)
    print("Done.")

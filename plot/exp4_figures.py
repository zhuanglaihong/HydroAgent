"""
Exp4 绘图脚本 — Knowledge Layer Ablation (K0-K4) + Cognitive Evaluation (T4)
输出目录：plot/exp4/

图表清单：
  fig7_knowledge_ablation.png  — 双面板：
    (a) K0-K4 token 效率柱 + tool_match_rate 折线（T1-T3 均值）
    (b) T4 认知评估对比（K0/K3/K4，physical_reasoning_score + correct_conclusion）
  fig8_per_task_tokens.png     — K0-K4 逐场景 token 明细分组柱状图

核心结论：
  K0-K3 tool_match_rate = 1.0（知识注入不影响工具选择准确率）
  K2 < K1 token（领域知识引导更直接推理路径，减少无效轮次）
  K3 token 激增 4.2x（记忆注入代价高，但不提升准确率）
  K4 token 增量较小（认知框架简洁，注入代价低）
  K4 在 T4 physical_reasoning_score / correct_conclusion 上显著优于 K0/K3

数据来源：results/paper/exp4/exp4_results.json
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

ROOT   = Path(__file__).parent.parent
DATA   = ROOT / "results/paper/exp4/exp4_results.json"
OUTDIR = Path(__file__).parent / "exp4"
OUTDIR.mkdir(exist_ok=True)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.spines.top":   False,
    "axes.spines.right": False,
})

COND_LABELS = {
    "K0": "K0\nNo knowledge",
    "K1": "K1\n+Skill manual",
    "K2": "K2\n+Domain\nknowledge",
    "K3": "K3\n+Memory\n(Full)",
    "K4": "K4\n+Cognitive\nframework",
}
# K0-K3 existing colors, K4 gets a distinct warm color
COND_COLORS = ["#D9D9D9", "#AEC6E8", "#8DB4D6", "#4878CF", "#FF9F40"]


def load_data():
    with open(DATA, encoding="utf-8") as f:
        return json.load(f)


def _safe_stat(stats: dict, cond: str, key: str, default=0.0):
    """Safely extract a stat value, returning default if missing."""
    return stats.get(cond, {}).get(key, default) or default


# ─────────────────────────────────────────────────────────────────────────────
# Fig.7  Two-panel: (a) token efficiency K0-K4, (b) T4 cognitive evaluation
# ─────────────────────────────────────────────────────────────────────────────
def fig7_knowledge_ablation(data: dict):
    stats   = data["main_ablation"]["stats_by_condition"]
    results = data["main_ablation"]["results"]

    # ── Panel (a): K0-K4 token efficiency ─────────────────────────────────
    conds_ab  = ["K0", "K1", "K2", "K3", "K4"]
    # Filter to T1-T3 only for token/time stats (exclude T4 cognitive scenario)
    task_results = [r for r in results if r.get("scenario_id", "").startswith("T")
                    and r.get("scenario_id") != "T4"]

    # Build per-condition T1-T3 averages (fallback to stats_by_condition)
    def t1t3_avg(cond):
        rows = [r for r in task_results if r.get("condition_id") == cond]
        vals = [r.get("total_tokens") for r in rows if r.get("total_tokens") is not None]
        if vals:
            return float(np.mean(vals))
        return _safe_stat(stats, cond, "avg_tokens", 0.0)

    tokens = [t1t3_avg(c) or _safe_stat(stats, c, "avg_tokens", 0)
              for c in conds_ab]
    match  = [_safe_stat(stats, c, "tool_match_rate", 1.0) for c in conds_ab]

    # ── Panel (b): T4 cognitive evaluation ────────────────────────────────
    t4_conds = ["K0", "K3", "K4"]
    t4_rows  = {r["condition_id"]: r for r in results
                if r.get("scenario_id") == "T4"}

    phys_scores = [t4_rows.get(c, {}).get("physical_reasoning_score", 0.0) or 0.0
                   for c in t4_conds]
    correct     = [float(t4_rows.get(c, {}).get("correct_conclusion", False) or False)
                   for c in t4_conds]

    # ── Layout ────────────────────────────────────────────────────────────
    fig, (ax_a, ax_b) = plt.subplots(
        1, 2,
        figsize=(13, 5.0),
        gridspec_kw={"width_ratios": [3, 2]},
    )
    fig.subplots_adjust(wspace=0.45, top=0.85)

    # ── (a) Token efficiency bars ──────────────────────────────────────────
    x_a = np.arange(len(conds_ab))
    colors_a = [COND_COLORS[i] for i in range(len(conds_ab))]

    bars = ax_a.bar(x_a, tokens, 0.55, color=colors_a, zorder=3, alpha=0.9)
    for bar, v in zip(bars, tokens):
        if v > 0:
            ax_a.text(bar.get_x() + bar.get_width() / 2,
                      bar.get_height() + max(tokens) * 0.01,
                      f"{v/1000:.1f}K",
                      ha="center", va="bottom", fontsize=8, fontweight="bold")

    ax_a.set_ylabel("Avg. tokens (T1–T3)", fontsize=9)
    ax_a.set_ylim(0, max(tokens) * 1.35 if max(tokens) > 0 else 200000)
    ax_a.set_xticks(x_a)
    ax_a.set_xticklabels([COND_LABELS[c] for c in conds_ab], fontsize=8)
    ax_a.tick_params(labelsize=8)
    ax_a.grid(axis="y", ls=":", lw=0.4, alpha=0.5, zorder=0)
    ax_a.set_title("(a) Token Efficiency by Knowledge Condition", fontsize=9, fontweight="bold", pad=8)

    # K2 < K1 annotation
    if len(tokens) >= 3 and tokens[2] > 0 and tokens[1] > 0 and tokens[2] < tokens[1]:
        ax_a.annotate(
            "K2 < K1\n(domain knowledge\nreduces redundant calls)",
            xy=(2, tokens[2]),
            xytext=(1.5, tokens[2] + max(tokens) * 0.28),
            arrowprops=dict(arrowstyle="->", color="#cc3333", lw=1.2),
            fontsize=7.5, color="#cc3333", ha="center",
            bbox=dict(boxstyle="round,pad=0.3", fc="#FFF0F0", ec="#cc3333", alpha=0.9)
        )

    # Right axis: tool_match_rate
    ax_a2 = ax_a.twinx()
    ax_a2.plot(x_a, match, "s--", color="#2ca02c", lw=1.5, ms=7,
               zorder=5, alpha=0.85)
    ax_a2.axhline(1.0, color="#2ca02c", lw=0.8, ls=":", alpha=0.5, zorder=4)
    ax_a2.set_ylim(0, 1.35)
    ax_a2.set_yticks([0.0, 0.5, 1.0])
    ax_a2.set_ylabel("Tool match rate (T1–T3)", fontsize=9, color="#2ca02c")
    ax_a2.tick_params(labelsize=8, colors="#2ca02c")
    ax_a2.spines["right"].set_edgecolor("#2ca02c")
    ax_a2.text(len(conds_ab) - 0.6, 1.02, "= 1.0", fontsize=7, color="#2ca02c", va="bottom")

    # Legend for (a)
    bar_patch  = mpatches.Patch(color="#AEC6E8", alpha=0.9, label="Avg. tokens (bar)")
    match_line = plt.Line2D([0], [0], color="#2ca02c", lw=1.5,
                            marker="s", ms=6, ls="--", label="Tool match rate")
    ax_a.legend(handles=[bar_patch, match_line],
                fontsize=7.5, loc="upper left", framealpha=0.9)

    # ── (b) T4 cognitive evaluation bars ──────────────────────────────────
    x_b   = np.arange(len(t4_conds))
    bar_w = 0.3
    t4_colors = {"K0": COND_COLORS[0], "K3": COND_COLORS[3], "K4": COND_COLORS[4]}

    bars_phys = ax_b.bar(x_b - bar_w / 2, phys_scores, bar_w,
                         color=[t4_colors[c] for c in t4_conds],
                         label="Physical reasoning score", alpha=0.9, zorder=3)
    bars_corr = ax_b.bar(x_b + bar_w / 2, correct, bar_w,
                         color=[t4_colors[c] for c in t4_conds],
                         hatch="///", label="Correct conclusion (0/1)", alpha=0.7, zorder=3)

    for bar, v in list(zip(bars_phys, phys_scores)) + list(zip(bars_corr, correct)):
        if v >= 0:
            ax_b.text(bar.get_x() + bar.get_width() / 2,
                      bar.get_height() + 0.02,
                      f"{v:.2f}",
                      ha="center", va="bottom", fontsize=8, fontweight="bold")

    ax_b.set_ylim(0, 1.35)
    ax_b.set_yticks([0.0, 0.25, 0.5, 0.75, 1.0])
    ax_b.set_xticks(x_b)
    ax_b.set_xticklabels([COND_LABELS[c] for c in t4_conds], fontsize=8.5)
    ax_b.set_ylabel("Score (0–1)", fontsize=9)
    ax_b.tick_params(labelsize=8)
    ax_b.grid(axis="y", ls=":", lw=0.4, alpha=0.5, zorder=0)
    ax_b.set_title("(b) T4 Cognitive Diagnosis Evaluation\n(K0 / K3 / K4)", fontsize=9, fontweight="bold", pad=8)

    phys_patch = mpatches.Patch(color="#AEC6E8", alpha=0.9, label="Physical reasoning score")
    corr_patch = mpatches.Patch(color="#AEC6E8", alpha=0.7, hatch="///", label="Correct conclusion")
    ax_b.legend(handles=[phys_patch, corr_patch], fontsize=7.5,
                loc="upper left", framealpha=0.9)

    fig.suptitle(
        "Figure 7. Knowledge Layer Ablation: Token Efficiency and Cognitive Reasoning Quality\n"
        "K0-K4: incremental knowledge injection | K4 (+cognitive framework) improves reasoning without high token cost",
        fontsize=9.5, fontweight="bold", y=0.97)

    out = OUTDIR / "fig7_knowledge_ablation.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {out.name}")


# ─────────────────────────────────────────────────────────────────────────────
# Fig.8  Per-task detail: token count by condition K0-K4 and scenario T1-T3
# ─────────────────────────────────────────────────────────────────────────────
def fig8_per_task_tokens(data: dict):
    results = data["main_ablation"]["results"]

    conds = ["K0", "K1", "K2", "K3", "K4"]

    # Only T1-T3 task scenarios (exclude T4 cognitive evaluation)
    scenario_ids   = []
    scenario_names = {}
    seen = set()
    for r in results:
        sid = r.get("scenario_id", "")
        if sid and sid != "T4" and sid not in seen:
            scenario_ids.append(sid)
            scenario_names[sid] = r.get("scenario_name", sid).replace("_", " ")
            seen.add(sid)

    if not scenario_ids:
        print("  [skip] fig8: no T1-T3 scenario data found")
        return

    # Matrix: (n_conds, n_scenarios)
    matrix = np.full((len(conds), len(scenario_ids)), np.nan)
    for r in results:
        cid = r.get("condition_id")
        sid = r.get("scenario_id", "")
        if cid in conds and sid in scenario_ids:
            ci = conds.index(cid)
            si = scenario_ids.index(sid)
            val = r.get("total_tokens")
            if val is not None:
                matrix[ci, si] = float(val)

    fig, ax = plt.subplots(figsize=(10, 4.5))
    x = np.arange(len(scenario_ids))
    n   = len(conds)
    bar_w = 0.14
    offset_base = -(n - 1) / 2 * bar_w

    for ci, (cond, color) in enumerate(zip(conds, COND_COLORS)):
        offset = offset_base + ci * bar_w
        vals = matrix[ci]
        ax.bar(x + offset, vals, bar_w, color=color,
               label=COND_LABELS[cond].replace("\n", " "),
               alpha=0.9, zorder=3)

    ax.set_xticks(x)
    ax.set_xticklabels([scenario_names[s] for s in scenario_ids], fontsize=8.5)
    ax.set_ylabel("Token count", fontsize=9)
    ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda v, _: f"{int(v/1000)}K" if v >= 1000 else str(int(v))))
    ax.tick_params(labelsize=8)
    ax.grid(axis="y", ls=":", lw=0.4, alpha=0.5)
    ax.legend(fontsize=7.5, loc="upper left", ncol=3, framealpha=0.9)
    ax.set_title(
        "Figure 8. Per-Scenario Token Count by Knowledge Condition (K0-K4, T1-T3 only)\n"
        "K3 memory overhead dominates; K2 consistently lower than K1; K4 adds minimal token cost",
        fontsize=9, fontweight="bold")

    out = OUTDIR / "fig8_per_task_tokens.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {out.name}")


# ── main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Exp4 figures ->", OUTDIR)
    data = load_data()
    fig7_knowledge_ablation(data)
    fig8_per_task_tokens(data)
    print("Done.")

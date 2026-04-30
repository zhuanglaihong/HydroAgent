"""
Exp2 绘图脚本 — LLM Calibration A/B/C Comparison
输出目录：plot/exp2/

图表清单：
  fig4_method_comparison.png   — 三路方法 KGE/NSE 对比柱状图（3流域×3方法）
  fig5_nse_trajectory.png      — 方法C NSE 迭代轨迹（LLM 参数范围调控过程）

实验设计：
  方法A — SCE-UA 基线（传统优化，对照组）
  方法B — Zhu 方法（LLM 直接提议参数，外部对照）
  方法C — HydroAgent LLM 率定（智能参数范围迭代调控，主角）

核心结论：
  - 三路方法在好流域（12025000/11532500）NSE 相当——自动化不损失精度
  - 方法C 在难流域（03439000）的 NSE 迭代轨迹显示流域先验知识带来的改善
  - 方法C 的工具调用链（validate->llm_calibrate->evaluate）展示了智能决策路径

数据来源：results/paper/exp2/exp2_results.json
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

ROOT   = Path(__file__).parent.parent
DATA   = ROOT / "results/paper/exp2/exp2_results.json"
OUTDIR = Path(__file__).parent / "exp2"
OUTDIR.mkdir(exist_ok=True)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.spines.top":   False,
    "axes.spines.right": False,
})

METHOD_COLORS = {
    "A": "#4878CF",   # 蓝 — SCE-UA 基线
    "B": "#D65F5F",   # 红 — Zhu 方法
    "C": "#6ACC65",   # 绿 — HydroAgent LLM 率定
}
METHOD_LABELS = {
    "A": "Method A\n(SCE-UA baseline)",
    "B": "Method B\n(Zhu: direct proposal)",
    "C": "Method C\n(HydroAgent LLM)",
}

BASIN_LABELS = {
    "12025000": "12025000\nFish R., ME\n(humid-cold)",
    "11532500": "11532500\nSmith R., CA\n(mediterranean)",
    "03439000": "03439000\nFrench Broad, NC\n(humid-warm)",
}


def load_data():
    with open(DATA, encoding="utf-8") as f:
        return json.load(f)


# ─────────────────────────────────────────────────────────────────────────────
# Fig.4  Method comparison bar chart
# ─────────────────────────────────────────────────────────────────────────────
def fig4_method_comparison(data: dict):
    results = data["results"]

    basins = [r["basin_id"] for r in results]
    n = len(basins)

    # Collect metrics: test KGE and test NSE for each method
    # A uses method_A_agg (mean+/-std); B uses method_B; C uses method_C1
    metrics = {m: {"kge": [], "nse": []} for m in ["A", "B", "C"]}
    for r in results:
        # Method A: aggregate stats
        a_agg = r.get("method_A_agg", {})
        metrics["A"]["nse"].append(a_agg.get("nse_test", {}).get("mean", np.nan))
        metrics["A"]["kge"].append(a_agg.get("kge_test", {}).get("mean", np.nan))
        # Method B
        b = r.get("method_B", {})
        b_te = b.get("test_metrics") or {}
        metrics["B"]["nse"].append(b_te.get("NSE", np.nan))
        metrics["B"]["kge"].append(b_te.get("KGE", np.nan))
        # Method C (C1)
        c = r.get("method_C1", {})
        c_te = c.get("test_metrics") or {}
        metrics["C"]["nse"].append(c_te.get("NSE", np.nan))
        metrics["C"]["kge"].append(c_te.get("KGE", np.nan))

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8),
                              gridspec_kw={"wspace": 0.35})

    for ax, metric_key, metric_name, sub in zip(
            axes, ["kge", "nse"], ["KGE (test)", "NSE (test)"], ["a", "b"]):

        bar_w = 0.22
        x = np.arange(n)
        offsets = [-bar_w, 0, bar_w]

        for m, off in zip(["A", "B", "C"], offsets):
            vals = metrics[m][metric_key]
            bars = ax.bar(x + off, vals, bar_w,
                          color=METHOD_COLORS[m], alpha=0.85,
                          label=METHOD_LABELS[m], zorder=3)
            for bar, v in zip(bars, vals):
                if not np.isnan(v):
                    va = "bottom" if v >= 0 else "top"
                    ypos = bar.get_height() + bar.get_y() + (0.01 if v >= 0 else -0.01)
                    ax.text(bar.get_x() + bar.get_width() / 2, ypos,
                            f"{v:.3f}", ha="center", va=va, fontsize=6.5,
                            rotation=90)

        # Reference line at 0
        ax.axhline(0, color="#999", lw=0.8, ls="--")

        ax.set_xticks(x)
        ax.set_xticklabels([BASIN_LABELS[b] for b in basins],
                           fontsize=7.5, va="center")
        ax.set_ylabel(metric_name, fontsize=9)
        ax.set_ylim(min(-0.25,
                        min(v for m in ["A","B","C"]
                            for v in metrics[m][metric_key]
                            if not np.isnan(v))) * 1.3,
                    1.05)
        ax.tick_params(labelsize=8)
        ax.grid(axis="y", ls=":", lw=0.4, alpha=0.5)
        ax.set_title(f"({sub}) {metric_name}", fontsize=9,
                     fontweight="bold", pad=5)
        if sub == "a":
            ax.legend(fontsize=7.5, loc="upper right", framealpha=0.85)

    fig.suptitle(
        "Figure 4. Three-Method Calibration Comparison — Test Period Performance\n"
        "Model: XAJ | Basins: 3 | A=SCE-UA baseline, B=Zhu LLM direct, C=HydroAgent basin-aware LLM",
        fontsize=9.5, fontweight="bold")

    out = OUTDIR / "fig4_method_comparison.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {out.name}")


# ─────────────────────────────────────────────────────────────────────────────
# Fig.5  Method C NSE iteration trajectory
# ─────────────────────────────────────────────────────────────────────────────
def fig5_nse_trajectory(data: dict):
    results = data["results"]

    # Filter basins that have nse_history
    has_history = [(r["basin_id"], r["method_C1"].get("nse_history", []))
                   for r in results
                   if r.get("method_C1", {}).get("nse_history")]
    if not has_history:
        print("  [skip] fig5: no nse_history data")
        return

    fig, ax = plt.subplots(figsize=(7, 4.2))

    basin_colors = {
        "12025000": "#4878CF",
        "11532500": "#D65F5F",
        "03439000": "#6ACC65",
    }
    basin_names = {
        "12025000": "12025000 Fish R., ME (humid-cold)",
        "11532500": "11532500 Smith R., CA (mediterranean)",
        "03439000": "03439000 French Broad, NC (humid-warm) <- prior knowledge test case",
    }

    for basin_id, history in has_history:
        rounds = list(range(1, len(history) + 1))
        color = basin_colors.get(basin_id, "#888")
        ax.plot(rounds, history, "o-", color=color, lw=1.8, ms=6,
                label=basin_names.get(basin_id, basin_id), zorder=3)

        # Annotate best round if improvement exists
        best_val = max(history)
        best_rnd = history.index(best_val) + 1
        if history[-1] != history[0]:  # actual improvement
            ax.annotate(f"Best: {best_val:.3f}",
                        xy=(best_rnd, best_val),
                        xytext=(best_rnd + 0.2, best_val + 0.01),
                        fontsize=7.5, color=color, fontweight="bold")

    # y limits: tight around data with small margin, avoid huge gap
    all_vals = [v for _, h in has_history for v in h]
    y_min, y_max = min(all_vals), max(all_vals)
    margin = (y_max - y_min) * 0.15
    ax.set_ylim(y_min - margin, y_max + margin)

    ax.axhline(0, color="#bbb", lw=0.8, ls="--")
    ax.set_xlabel("LLM Iteration Round", fontsize=9)
    ax.set_ylabel("Train NSE", fontsize=9)
    ax.set_xticks(range(1, max(len(h) for _, h in has_history) + 1))
    ax.tick_params(labelsize=8)
    ax.grid(ls=":", lw=0.4, alpha=0.5)
    ax.legend(fontsize=7.5, loc="upper left", framealpha=0.85)

    # Annotation box — placed in the empty region between negative basin and upper basins
    info = (
        "Method C: LLM iteratively adjusts parameter bounds,\n"
        "re-runs SCE-UA each round. Flat curves = near-optimal\n"
        "from round 1. 03439000 tests basin-aware initialization."
    )
    ax.text(0.98, 0.05, info, transform=ax.transAxes,
            fontsize=7, va="bottom", ha="right",
            bbox=dict(boxstyle="round,pad=0.4", fc="#FFFFF0", ec="#ccc", alpha=0.9))

    ax.set_title(
        "Figure 5. Method C — LLM Parameter Range Adjustment Trajectory\n"
        "Train NSE across 5 iteration rounds (GR4J model, 3 basins)",
        fontsize=9, fontweight="bold")

    out = OUTDIR / "fig5_nse_trajectory.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {out.name}")


# ── main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Exp2 figures →", OUTDIR)
    data = load_data()
    fig4_method_comparison(data)
    fig5_nse_trajectory(data)
    print("Done.")

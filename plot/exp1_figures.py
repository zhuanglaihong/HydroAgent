"""
Exp1 绘图脚本 — Standard Calibration Baseline
输出目录：plot/exp1/

图表清单：
  fig2_performance_heatmap.png  — 5流域 KGE/NSE 热力图（train vs test）
  fig3_hydrograph.png           — 过程线（降水+流量，3时间窗口×2流域）
  figS1_token_comparison.png    — ReAct vs Pipeline token 对比（补充图）

数据来源：results/paper/exp1/exp1_results.json
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.dates as mdates
import numpy as np
import xarray as xr

# ── 路径 ──────────────────────────────────────────────────────────────────────
ROOT    = Path(__file__).parent.parent
DATA    = ROOT / "results/paper/exp1/exp1_results.json"
OUTDIR  = Path(__file__).parent / "exp1"
OUTDIR.mkdir(exist_ok=True)

# ── 全局样式 ──────────────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.family":  "DejaVu Sans",
    "font.size":    9,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "figure.dpi":   150,
})

TOOL_COLORS = {
    "validate_basin":  "#4878CF",
    "calibrate_model": "#D65F5F",
    "evaluate_model":  "#6ACC65",
    "llm_calibrate":   "#FF9F40",
    "read_file":       "#C4AD66",
    "inspect_dir":     "#d9d9d9",
    "generate_code":   "#82C4E0",
    "run_code":        "#956CB4",
    "visualize":       "#8172B2",
}


# ── 数据加载 ──────────────────────────────────────────────────────────────────
def load_data():
    with open(DATA, encoding="utf-8") as f:
        return json.load(f)


def load_nc(basin_id: str, run: int = 1) -> xr.Dataset:
    path = (ROOT / "results/paper/exp1"
            / f"xaj_{basin_id}" / f"run{run}" / "eval_test"
            / "xaj_evaluation_results.nc")
    return xr.open_dataset(path)


# ─────────────────────────────────────────────────────────────────────────────
# Fig.2  Performance heatmap
# ─────────────────────────────────────────────────────────────────────────────
def fig2_performance_heatmap(data: dict):
    agg = data["results_agg"]
    agg_sorted = sorted(agg, key=lambda r: r["kge_train"]["mean"] or -999, reverse=True)

    BASIN_LABELS = {
        "12025000": "12025000\nFish R., ME\n(humid-cold)",
        "03439000": "03439000\nFrench Broad, NC\n(humid-warm)",
        "06043500": "06043500\nGallatin R., MT\n(semiarid-mtn)",
        "08101000": "08101000\nCowhouse Ck., TX\n(semiarid-flashy)",
        "11532500": "11532500\nSmith R., CA\n(mediterranean)",
    }
    y_labels = [BASIN_LABELS[r["basin_id"]] for r in agg_sorted]

    CLIP_LOW = -1.0

    def get(r, key):
        v = r[key]["mean"]
        return v if v is not None else np.nan

    def clip(vals):
        return [max(v, CLIP_LOW) if not np.isnan(v) else np.nan for v in vals]

    kge_tr_raw = [get(r, "kge_train") for r in agg_sorted]
    kge_te_raw = [get(r, "kge_test")  for r in agg_sorted]
    nse_tr_raw = [get(r, "nse_train") for r in agg_sorted]
    nse_te_raw = [get(r, "nse_test")  for r in agg_sorted]

    KGE = np.array([clip(kge_tr_raw), clip(kge_te_raw)]).T
    NSE = np.array([clip(nse_tr_raw), clip(nse_te_raw)]).T
    KGE_raw = np.array([kge_tr_raw, kge_te_raw]).T
    NSE_raw = np.array([nse_tr_raw, nse_te_raw]).T

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5),
                              gridspec_kw={"wspace": 0.35})

    CMAP = "RdYlGn"
    VMIN, VMAX = -1.0, 1.0
    COL_LABELS = ["Training\n(1985–2000)", "Test\n(2001–2014)"]

    def draw(ax, mat, raw, label, sub):
        im = ax.imshow(mat, cmap=CMAP, vmin=VMIN, vmax=VMAX, aspect="auto")
        ax.set_xticks([0, 1])
        ax.set_xticklabels(COL_LABELS, fontsize=8)
        ax.set_yticks(range(len(y_labels)))
        ax.set_yticklabels(y_labels, fontsize=7.5, va="center")
        ax.tick_params(length=0)

        for i in range(mat.shape[0]):
            for j in range(mat.shape[1]):
                rv = raw[i, j]
                if np.isnan(rv):
                    txt = "N/A"
                elif rv < CLIP_LOW:
                    txt = f"{rv:.2f}*"
                else:
                    txt = f"{rv:.3f}"
                bright = (mat[i, j] - VMIN) / (VMAX - VMIN)
                color = "white" if bright < 0.25 or bright > 0.85 else "black"
                weight = "bold" if not np.isnan(rv) and rv < 0 else "normal"
                ax.text(j, i, txt, ha="center", va="center",
                        fontsize=8.5, color=color, fontweight=weight)
            if any(not np.isnan(raw[i, j]) and raw[i, j] < 0 for j in range(2)):
                for j in range(2):
                    ax.add_patch(mpatches.FancyBboxPatch(
                        (j - 0.48, i - 0.48), 0.96, 0.96,
                        boxstyle="square,pad=0", lw=1.2,
                        edgecolor="#cc3333", fill=False, zorder=3))

        ax.set_title(f"({sub}) {label}", fontsize=9, fontweight="bold", pad=6)
        cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.04)
        cb.ax.tick_params(labelsize=7.5)
        cb.set_label(label, fontsize=8)
        cb.set_ticks([-1.0, -0.5, 0, 0.5, 1.0])

    draw(axes[0], KGE, KGE_raw, "KGE", "a")
    draw(axes[1], NSE, NSE_raw, "NSE", "b")

    fig.text(0.5, 0.01,
             "* clipped to -1.0 for display; actual KGE_test(08101000) = -8.696  |"
             "  Red borders: at least one negative value  |  Model: XAJ  |  Algorithm: SCE-UA",
             ha="center", fontsize=7, color="#555", style="italic")
    fig.suptitle(
        "Figure 2. Standard Calibration Performance — 5 Basins, XAJ Model (3 independent runs)",
        fontsize=10, fontweight="bold", y=1.02)

    out = OUTDIR / "fig2_performance_heatmap.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {out.name}")


# ─────────────────────────────────────────────────────────────────────────────
# Fig.3  Hydrograph with precipitation
# ─────────────────────────────────────────────────────────────────────────────
def fig3_hydrograph():
    BASINS = [
        {"id": "12025000", "label": "(a) Basin 12025000 — Fish River, ME (humid-cold)",
         "kge": 0.679, "nse": 0.735},
        {"id": "08101000", "label": "(b) Basin 08101000 — Cowhouse Creek, TX (semiarid-flashy)",
         "kge": -8.696, "nse": -1.034},
    ]
    WINDOWS = [
        ("Autumn peak\n(Oct–Dec 2012)",    "2012-10-01", "2012-12-31"),
        ("Spring rising\n(Mar–May 2013)",   "2013-03-01", "2013-05-15"),
        ("Summer recession\n(Jul–Sep 2013)","2013-07-01", "2013-09-30"),
    ]

    fig, axes = plt.subplots(2, 3, figsize=(14, 6.5),
                              gridspec_kw={"hspace": 0.55, "wspace": 0.28})

    for ri, bc in enumerate(BASINS):
        ds = load_nc(bc["id"])
        bid = bc["id"]
        qobs_s = ds["qobs"].sel(basin=bid).to_series()
        qsim_s = ds["qsim"].sel(basin=bid).to_series()
        prcp_s = ds["prcp"].sel(basin=bid).to_series()

        for ci, (wlabel, t0, t1) in enumerate(WINDOWS):
            ax = axes[ri][ci]
            qo = qobs_s[t0:t1]
            qs = qsim_s[t0:t1]
            pr = prcp_s[t0:t1]
            tm = qo.index

            ax.plot(tm, qo, color="#222", lw=0.9, label="Observed", zorder=3)
            ax.plot(tm, qs, color="#2166AC", lw=1.0, alpha=0.88,
                    label="Simulated (XAJ)", zorder=2)
            ax.fill_between(tm, qo, qs, where=(qs > qo), alpha=0.12, color="#2166AC")
            ax.fill_between(tm, qo, qs, where=(qs < qo), alpha=0.18, color="#D6604D")

            qmax = max(qo.max(), qs.max()) * 1.1
            ax.set_ylim(0, qmax if qmax > 0 else 1)
            ax.set_ylabel("Q (mm/d)", fontsize=7.5)
            ax.tick_params(labelsize=7)

            ax2 = ax.twinx()
            ax2.bar(tm, pr, width=0.9, color="#5B9BD5", alpha=0.45,
                    label="Precip.")
            pmax = pr.max() if pr.max() > 0 else 10
            ax2.set_ylim(pmax * 4, 0)
            ax2.set_ylabel("P (mm/d)", fontsize=7, color="#5B9BD5")
            ax2.tick_params(labelsize=6.5, colors="#5B9BD5")
            ax2.spines["right"].set_edgecolor("#5B9BD5")

            ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
            ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=3))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=30,
                     ha="right", fontsize=7)
            ax.grid(axis="y", ls=":", lw=0.4, alpha=0.5)

            if ri == 0:
                ax.set_title(wlabel, fontsize=8.5, fontweight="bold", pad=4)
            if ci == 0:
                kge_str = (f"{bc['kge']:.3f}" if bc['kge'] > -5
                           else f"{bc['kge']:.2f}")
                bbox = dict(boxstyle="round,pad=0.25",
                            fc="#FFFFF0" if bc["nse"] > 0 else "#FFF0F0",
                            ec="#aaa", alpha=0.9)
                ax.text(0.02, 0.96,
                        f"KGE={kge_str}  NSE={bc['nse']:.3f}",
                        transform=ax.transAxes, fontsize=7.5,
                        va="top", bbox=bbox)
                ax.set_ylabel(f"Q (mm/d)\n{bc['label']}", fontsize=7.5)
            if ri == 0 and ci == 2:
                h1, l1 = ax.get_legend_handles_labels()
                h2, l2 = ax2.get_legend_handles_labels()
                ax.legend(h1 + h2, l1 + l2, fontsize=7, loc="upper right",
                          framealpha=0.85, handlelength=1.2)
        ds.close()

    fig.suptitle(
        "Figure 3. Observed vs. Simulated Streamflow — Test Period (XAJ, SCE-UA)\n"
        "Three representative flow regimes | Precipitation as inverted bars (right axis)",
        fontsize=9.5, fontweight="bold", y=1.01)

    out = OUTDIR / "fig3_hydrograph.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {out.name}")


# ─────────────────────────────────────────────────────────────────────────────
# Fig.S1  Token comparison (supplementary)
# ─────────────────────────────────────────────────────────────────────────────
def figS1_token_comparison(data: dict):
    tc = data.get("token_comparison", {})
    if not tc:
        print("  [skip] figS1: no token_comparison data")
        return

    react    = tc["modes"]["react"]["tokens"]
    pipeline = tc["modes"]["pipeline"]["tokens"]
    savings  = tc.get("savings_pct", 0)

    fig, ax = plt.subplots(figsize=(5.5, 4.0))
    x = np.array([0, 1])
    labels = ["ReAct\n(N LLM calls)", "Pipeline\n(1 LLM call)"]
    c_prompt = ["#4878CF", "#91b8e8"]
    c_compl  = ["#D65F5F", "#f0a0a0"]

    ax.bar(x, [react["prompt_tokens"], pipeline["prompt_tokens"]], 0.45,
           color=c_prompt, label="Prompt tokens", zorder=3)
    ax.bar(x, [react["completion_tokens"], pipeline["completion_tokens"]], 0.45,
           bottom=[react["prompt_tokens"], pipeline["prompt_tokens"]],
           color=c_compl, label="Completion tokens", zorder=3)

    for i, (rk, tok) in enumerate(
            [("react", react), ("pipeline", pipeline)]):
        total = tok["total_tokens"]
        calls = tc["modes"][rk]["api_calls"]
        ax.text(x[i], total + 500, f"{total:,}",
                ha="center", va="bottom", fontsize=9, fontweight="bold")
        ax.text(x[i], -2800, f"{calls} API call{'s' if calls>1 else ''}",
                ha="center", va="top", fontsize=8, color="#555")

    ax.annotate(f"-{savings:.0f}% tokens",
                xy=(1, pipeline["total_tokens"] + 800),
                xytext=(0.45, react["total_tokens"] * 0.55),
                arrowprops=dict(arrowstyle="->", color="#cc3333", lw=1.5),
                fontsize=10, color="#cc3333", fontweight="bold", ha="center")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("Token count", fontsize=9)
    ax.set_ylim(-4000,
                max(react["total_tokens"], pipeline["total_tokens"]) * 1.2)
    ax.set_xlim(-0.45, 1.45)
    ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda v, _: f"{int(v):,}" if v >= 0 else ""))
    ax.tick_params(labelsize=8)
    ax.grid(axis="y", ls="--", lw=0.4, alpha=0.5, zorder=0)
    ax.legend(fontsize=8, loc="upper right", framealpha=0.85)
    ax.set_title(
        "Figure S1. Token Efficiency: ReAct vs. Pipeline Mode\n"
        f"Basin 12025000 × XAJ — identical task, 1 representative run",
        fontsize=9, fontweight="bold")
    fig.text(0.5, -0.04,
             "ReAct: full message history sent every LLM call  |"
             "  Pipeline: 1 planning call + local execution without LLM",
             ha="center", fontsize=7.5, color="#666", style="italic")

    plt.tight_layout()
    out = OUTDIR / "figS1_token_comparison.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {out.name}")


# ── main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Exp1 figures →", OUTDIR)
    data = load_data()
    fig2_performance_heatmap(data)
    fig3_hydrograph()
    figS1_token_comparison(data)
    print("Done.")

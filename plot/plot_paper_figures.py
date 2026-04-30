"""
Plot Paper Figures - HydroAgent
==============================
Reads all 4 experiment result JSONs and generates publication-quality figures.

Output: results/paper/figures/
  Fig1a_exp1_nse_heatmap.png    - Exp1: NSE heatmap (basin x model)
  Fig1b_exp1_nse_bar.png        - Exp1: Train/Test NSE grouped bar
  Fig2a_exp2_comparison.png     - Exp2: A/B/C NSE comparison bars
  Fig2b_exp2_trajectory.png     - Exp2: Method-C NSE convergence trajectory
  Fig3_exp3_capability.png      - Exp3: Capability breadth (A/B/C sections)
  Fig4a_exp4_ablation.png       - Exp4: Knowledge ablation token/match heatmap
  Fig4b_exp4_adversarial.png    - Exp4: Adversarial prior detection

Usage:
  python experiment/plot_paper_figures.py          # generate all
  python experiment/plot_paper_figures.py --exp 2  # only exp2 figures
  python experiment/plot_paper_figures.py --show   # also display interactively
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import json
import warnings
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
RESULTS_DIR = Path("results/paper")
FIG_DIR     = RESULTS_DIR / "figures"

# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------
COLORS = {
    "A":    "#4878CF",   # blue:  Method A / gr4j
    "B":    "#D65F5F",   # red:   Method B / Zhu et al.
    "C":    "#6ACC65",   # green: Method C / HydroAgent
    "K0":   "#d9d9d9",
    "K1":   "#a6bddb",
    "K2":   "#3690c0",
    "K3":   "#034e7b",
    "pass": "#4dac26",
    "fail": "#d01c8b",
    "gray": "#888888",
}

ZONE_LABELS = {
    "humid_cold":        "Humid-Cold",
    "mediterranean":     "Mediterranean",
    "semiarid_mountain": "Semiarid-Mtn",
    "humid_temperate":   "Humid-Temperate",
    "humid_subtropical": "Humid-Sub.",
}

TRAJ_COLORS = ["#1b7837", "#762a83", "#e08214"]


def _style():
    plt.rcParams.update({
        "font.family":       "DejaVu Sans",
        "font.size":         10,
        "axes.titlesize":    11,
        "axes.labelsize":    10,
        "xtick.labelsize":   9,
        "ytick.labelsize":   9,
        "legend.fontsize":   9,
        "figure.dpi":        150,
        "axes.spines.top":   False,
        "axes.spines.right": False,
        "axes.grid":         True,
        "grid.alpha":        0.3,
        "grid.linestyle":    "--",
        "savefig.dpi":       300,
        "savefig.bbox":      "tight",
    })


def _save(fig, name: str, show: bool = False):
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    p = FIG_DIR / f"{name}.png"
    fig.savefig(p)
    print(f"  Saved: {name}.png")
    if show:
        plt.show()
    plt.close(fig)


def _load(exp_num: int) -> dict | None:
    p = RESULTS_DIR / f"exp{exp_num}" / f"exp{exp_num}_results.json"
    if not p.exists():
        print(f"  [skip] {p} not found")
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _short_basin(basin_id: str, zone: str = "") -> str:
    label = ZONE_LABELS.get(zone, zone)
    return f"{basin_id}\n({label})" if label else basin_id


# ===========================================================================
# Exp1: Standard Calibration
# ===========================================================================

def fig_exp1(data: dict, show: bool = False):
    results = data["results"]
    basins_ordered = []
    seen = set()
    for r in results:
        bid = r["basin_id"]
        if bid not in seen:
            basins_ordered.append((bid, r.get("climate_zone", "")))
            seen.add(bid)
    models = sorted({r["model_name"] for r in results})

    basins = [bid for bid, _ in basins_ordered]

    # --- Fig1a: NSE heatmap ---
    train_mat = np.full((len(basins), len(models)), np.nan)
    test_mat  = np.full((len(basins), len(models)), np.nan)
    for r in results:
        i = basins.index(r["basin_id"])
        j = models.index(r["model_name"])
        if r.get("success"):
            train_mat[i, j] = (r.get("train_metrics") or {}).get("NSE", np.nan)
            test_mat[i, j]  = (r.get("test_metrics")  or {}).get("NSE", np.nan)

    fig, axes = plt.subplots(1, 2, figsize=(9, 4.5))
    for ax, mat, title in zip(axes, [train_mat, test_mat], ["Train NSE", "Test NSE"]):
        im = ax.imshow(mat, vmin=0.3, vmax=1.0, cmap="RdYlGn", aspect="auto")
        ax.set_xticks(range(len(models)))
        ax.set_xticklabels([m.upper() for m in models])
        ax.set_yticks(range(len(basins)))
        ax.set_yticklabels([_short_basin(bid, zone) for bid, zone in basins_ordered],
                           fontsize=8)
        ax.set_title(title, fontweight="bold")
        ax.grid(False)
        for i in range(len(basins)):
            for j in range(len(models)):
                v = mat[i, j]
                if not np.isnan(v):
                    ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                            fontsize=9, color="black" if v > 0.55 else "white")
        fig.colorbar(im, ax=ax, shrink=0.8)
    fig.suptitle("Exp1: Standard Calibration — NSE Heatmap", fontweight="bold")
    fig.tight_layout()
    _save(fig, "Fig1a_exp1_nse_heatmap", show)

    # --- Fig1b: grouped bar ---
    fig, ax = plt.subplots(figsize=(11, 4.5))
    n_basins = len(basins)
    n_models = len(models)
    width    = 0.35
    x        = np.arange(n_basins)
    model_colors = [COLORS["A"], COLORS["B"], COLORS["C"], "#FF9F40"]

    for j, model in enumerate(models):
        train_vals, test_vals = [], []
        for bid, _ in basins_ordered:
            r = next((r for r in results if r["basin_id"] == bid and r["model_name"] == model), {})
            train_vals.append((r.get("train_metrics") or {}).get("NSE", 0) if r.get("success") else 0)
            test_vals.append((r.get("test_metrics")   or {}).get("NSE", 0) if r.get("success") else 0)
        offset = (j - (n_models - 1) / 2) * width
        ax.bar(x + offset,              train_vals, width * 0.47,
               color=model_colors[j], alpha=0.85, label=f"{model.upper()} Train")
        ax.bar(x + offset + width*0.47, test_vals,  width * 0.47,
               color=model_colors[j], alpha=0.45, label=f"{model.upper()} Test")

    ax.axhline(0.75, color="gray", ls="--", lw=1, alpha=0.7, label="NSE=0.75 (Good)")
    ax.set_xticks(x)
    ax.set_xticklabels([_short_basin(bid, zone) for bid, zone in basins_ordered],
                       fontsize=8)
    ax.set_ylabel("NSE")
    ax.set_ylim(0, 1.05)
    ax.set_title("Exp1: Standard Calibration — Train vs Test NSE", fontweight="bold")
    ax.legend(ncol=n_models, loc="upper right", fontsize=8)
    fig.tight_layout()
    _save(fig, "Fig1b_exp1_nse_bar", show)


# ===========================================================================
# Exp2: LLM Calibration Comparison
# ===========================================================================

def fig_exp2(data: dict, show: bool = False):
    results = data["results"]
    basins  = [(r["basin_id"], r.get("climate_zone", "")) for r in results]
    n       = len(basins)
    x       = np.arange(n)
    width   = 0.25

    def _get(r, path, default=np.nan):
        """Safely traverse nested dict using dot notation."""
        cur = r
        for key in path.split("."):
            if not isinstance(cur, dict):
                return default
            cur = cur.get(key, default)
        return cur if cur is not None else default

    a_train = [_get(r, "method_A.train_metrics.NSE") for r in results]
    b_train = [_get(r, "method_B.nse_train")          for r in results]
    c_train = [_get(r, "method_C.best_nse")            for r in results]
    a_test  = [_get(r, "method_A.test_metrics.NSE")   for r in results]
    b_test  = [_get(r, "method_B.nse_test")            for r in results]
    c_test  = [_get(r, "method_C.test_metrics.NSE")   for r in results]

    def _safe(vals):
        return [v if isinstance(v, (int, float)) and not (isinstance(v, float) and np.isnan(v)) else 0
                for v in vals]

    # --- Fig2a: A/B/C bar comparison (train + test side by side) ---
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    for ax, yA, yB, yC, split in [
        (axes[0], a_train, b_train, c_train, "Train"),
        (axes[1], a_test,  b_test,  c_test,  "Test"),
    ]:
        bars = [
            ax.bar(x - width, _safe(yA), width, color=COLORS["A"], alpha=0.85, label="A: SCE-UA"),
            ax.bar(x,         _safe(yB), width, color=COLORS["B"], alpha=0.85, label="B: Zhu 2026"),
            ax.bar(x + width, _safe(yC), width, color=COLORS["C"], alpha=0.85, label="C: HydroAgent"),
        ]
        # annotate delta C-A
        for i, (va, vc) in enumerate(zip(yA, yC)):
            if isinstance(va, float) and isinstance(vc, float) and not np.isnan(va + vc):
                delta = vc - va
                sign  = "+" if delta >= 0 else ""
                ax.text(x[i] + width, max(_safe([vc])[0], 0.02) + 0.02,
                        f"{sign}{delta:.3f}", ha="center", fontsize=7.5,
                        color=COLORS["C"] if delta >= 0 else COLORS["B"], fontweight="bold")
        ax.axhline(0.75, color="gray", ls="--", lw=1, alpha=0.6, label="NSE=0.75")
        ax.axhline(0,    color="black", lw=0.5)
        ax.set_xticks(x)
        ax.set_xticklabels([_short_basin(bid, zone) for bid, zone in basins], fontsize=8)
        ax.set_ylabel("NSE")
        y_min = min([v for v in _safe(yA) + _safe(yB) + _safe(yC)] + [-0.05]) - 0.05
        ax.set_ylim(y_min, 1.0)
        ax.set_title(f"{split} NSE", fontweight="bold")
        ax.legend(fontsize=8, loc="lower right")

    fig.suptitle("Exp2: Autonomous LLM Calibration — A/B/C Comparison", fontweight="bold")
    fig.tight_layout()
    _save(fig, "Fig2a_exp2_comparison", show)

    # --- Fig2b: Method C NSE trajectory ---
    fig, ax = plt.subplots(figsize=(7, 4))
    max_rounds = 0
    for i, r in enumerate(results):
        hist = r.get("method_C", {}).get("nse_history", [])
        hist = [v for v in hist if isinstance(v, (int, float))]
        if not hist:
            continue
        max_rounds = max(max_rounds, len(hist))
        bid, zone = basins[i]
        label = _short_basin(bid, zone)
        ax.plot(range(1, len(hist) + 1), hist, "o-",
                color=TRAJ_COLORS[i % len(TRAJ_COLORS)], lw=2, ms=6, label=label)
        # Method A baseline (dotted)
        a_val = _get(r, "method_A.train_metrics.NSE")
        if isinstance(a_val, float) and not np.isnan(a_val):
            ax.axhline(a_val, color=TRAJ_COLORS[i % len(TRAJ_COLORS)],
                       ls=":", lw=1.2, alpha=0.5)
        ax.text(len(hist) + 0.1, hist[-1], f"{hist[-1]:.3f}", va="center", fontsize=8)

    ax.axhline(0.75, color="gray", ls="--", lw=1, alpha=0.7, label="NSE=0.75 target")
    ax.set_xlabel("LLM Round")
    ax.set_ylabel("NSE (train)")
    ax.set_title("Exp2: Method C — NSE Convergence Trajectory\n(dotted = Method A baseline)",
                 fontweight="bold")
    if max_rounds > 0:
        ax.set_xticks(range(1, max_rounds + 1))
    ax.legend(fontsize=8.5)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    _save(fig, "Fig2b_exp2_trajectory", show)


# ===========================================================================
# Exp3: Capability Breadth (A: NL Robustness, B: Dynamic Skill, C: Self-Driven)
# ===========================================================================

def fig_exp3(data: dict, show: bool = False):
    secs = data["sections"]

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))

    # --- Section A: NL Robustness ---
    ax = axes[0]
    results_a = secs["A"]["results"]
    categories = list(dict.fromkeys(r["category"] for r in results_a))  # preserve order
    cat_match = [sum(r.get("tool_match", False)        for r in results_a if r["category"] == c) for c in categories]
    cat_first = [sum(r.get("first_tool_correct", False) for r in results_a if r["category"] == c) for c in categories]
    cat_total = [sum(1                                  for r in results_a if r["category"] == c) for c in categories]

    xp = np.arange(len(categories))
    w  = 0.3
    b1 = ax.bar(xp - w/2, cat_match, w, color=COLORS["A"], alpha=0.85, label="Tool Match",   edgecolor="white")
    b2 = ax.bar(xp + w/2, cat_first, w, color=COLORS["B"], alpha=0.85, label="First Correct", edgecolor="white")
    for xi, (m, f, t) in enumerate(zip(cat_match, cat_first, cat_total)):
        ax.text(xi - w/2, m + 0.05, f"{m}/{t}", ha="center", fontsize=8.5)
        ax.text(xi + w/2, f + 0.05, f"{f}/{t}", ha="center", fontsize=8.5)
    stats_a = secs["A"]["stats"]
    ax.text(0.97, 0.97, f"Match {stats_a['tool_match_rate']:.0%}  First {stats_a['first_tool_rate']:.0%}",
            transform=ax.transAxes, ha="right", va="top", fontsize=8.5, color="gray")
    ax.set_xticks(xp)
    ax.set_xticklabels([c.replace("_", "\n") for c in categories], fontsize=8)
    ax.set_ylim(0, max(cat_total) + 1.5)
    ax.set_ylabel("Count")
    ax.set_title("(a) NL Robustness", fontweight="bold")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.3)

    # --- Section B: Dynamic Skill Creation ---
    ax = axes[1]
    results_b = secs["B"]["results"]
    n_b  = len(results_b)
    keys_b = [
        ("create_skill_called", "create_skill\ncalled"),
        ("skill_md_exists",     "skill.md\nexists"),
        ("tool_py_syntax_ok",   "syntax\nvalid"),
        ("tool_registered",     "registered"),
    ]
    labels_b = [lb for _, lb in keys_b]
    vals_b   = [sum(r.get(k, False) for r in results_b) for k, _ in keys_b]
    bars = ax.bar(range(len(labels_b)), vals_b, color=COLORS["C"], alpha=0.85, edgecolor="white")
    for bar, v in zip(bars, vals_b):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 0.05, f"{v}/{n_b}",
                ha="center", fontsize=9.5)
    stats_b = secs["B"]["stats"]
    ax.text(0.97, 0.97, f"Success {stats_b['success_rate']:.0%}",
            transform=ax.transAxes, ha="right", va="top", fontsize=8.5, color="gray")
    ax.set_xticks(range(len(labels_b)))
    ax.set_xticklabels(labels_b, fontsize=8)
    ax.set_ylim(0, n_b + 1.5)
    ax.set_ylabel("Count")
    ax.set_title("(b) Dynamic Skill Creation", fontweight="bold")
    ax.grid(axis="y", alpha=0.3)

    # --- Section C: Self-Driven Planning ---
    ax = axes[2]
    phases = secs["C"]["phases"]
    n_ph   = len(phases)
    comp   = [p.get("completion_rate", 0) for p in phases]
    done   = [p.get("tasks_done",  0) for p in phases]
    total  = [p.get("tasks_total", 1) for p in phases]
    ok     = [p.get("success", False) for p in phases]
    colors_c = [COLORS["K3"] if s else COLORS["K0"] for s in ok]

    bars = ax.bar(range(n_ph), comp, color=colors_c, alpha=0.85, edgecolor="white")
    for i, (bar, d, t) in enumerate(zip(bars, done, total)):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                f"{d}/{t}", ha="center", fontsize=9.5)
    stats_c = secs["C"]["stats"]
    ax.text(0.97, 0.97, f"Pass {stats_c['pass_rate']:.0%}",
            transform=ax.transAxes, ha="right", va="top", fontsize=8.5, color="gray")
    ax.set_xticks(range(n_ph))
    ax.set_xticklabels([f"Phase {p['phase']}" for p in phases], fontsize=9)
    ax.set_ylim(0, 1.35)
    ax.set_ylabel("Task Completion Rate")
    ax.set_title("(c) Self-Driven Planning", fontweight="bold")
    ax.legend(handles=[
        mpatches.Patch(color=COLORS["K3"], alpha=0.85, label="Pass"),
        mpatches.Patch(color=COLORS["K0"], alpha=0.85, label="Fail"),
    ], fontsize=8)
    ax.grid(axis="y", alpha=0.3)

    fig.suptitle("Exp3: Capability Breadth — NL Robustness / Dynamic Skill / Self-Driven Planning",
                 fontweight="bold")
    fig.tight_layout()
    _save(fig, "Fig3_exp3_capability", show)


# ===========================================================================
# Exp4: Knowledge Ablation + Adversarial Robustness
# ===========================================================================

def fig_exp4(data: dict, show: bool = False):
    main      = data["main_ablation"]
    adv_data  = data["adversarial_robustness"]

    conditions = [c["id"] for c in main["conditions"]]   # K0 K1 K2 K3
    scenarios  = [s["id"] for s in main["scenarios"]]    # T1 T2 T3
    results    = main["results"]
    lookup     = {(r["condition_id"], r["scenario_id"]): r for r in results}

    n_cond, n_scen = len(conditions), len(scenarios)
    tokens_mat = np.zeros((n_cond, n_scen))
    match_mat  = np.zeros((n_cond, n_scen))
    first_mat  = np.zeros((n_cond, n_scen))

    for ci, cond in enumerate(conditions):
        for si, scen in enumerate(scenarios):
            rec = lookup.get((cond, scen), {})
            tokens_mat[ci, si] = rec.get("token_count", 0) / 1000
            match_mat[ci, si]  = 1.0 if rec.get("tool_match",       False) else 0.0
            first_mat[ci, si]  = 1.0 if rec.get("first_tool_correct", False) else 0.0

    # --- Fig4a: token heatmap + match/first bar ---
    fig = plt.figure(figsize=(13, 5))
    gs  = GridSpec(1, 2, figure=fig, width_ratios=[1.5, 1], wspace=0.4)

    ax_tok  = fig.add_subplot(gs[0])
    ax_rate = fig.add_subplot(gs[1])

    # Token heatmap
    im = ax_tok.imshow(tokens_mat, cmap="YlOrRd", aspect="auto",
                       vmin=0, vmax=tokens_mat.max())
    ax_tok.set_xticks(range(n_scen))
    ax_tok.set_xticklabels(["T1\n(Calibration)", "T2\n(Boundary)", "T3\n(Code)"], fontsize=8.5)
    ax_tok.set_yticks(range(n_cond))
    ax_tok.set_yticklabels(
        ["K0: No Knowledge", "K1: +Skill Guide", "K2: +Domain KB", "K3: +Memory (Full)"],
        fontsize=8.5)
    ax_tok.set_title("(a) Token Consumption (k tokens)", fontweight="bold")
    ax_tok.grid(False)
    for ci in range(n_cond):
        for si in range(n_scen):
            v     = tokens_mat[ci, si]
            color = "white" if v > tokens_mat.max() * 0.65 else "black"
            ax_tok.text(si, ci, f"{v:.0f}k", ha="center", va="center",
                        fontsize=10, color=color, fontweight="bold")
    plt.colorbar(im, ax=ax_tok, label="kTokens", fraction=0.046, pad=0.04)

    # Match/first bar
    avg_match = match_mat.mean(axis=1)
    avg_first = first_mat.mean(axis=1)
    xp = np.arange(n_cond)
    w  = 0.35
    b1 = ax_rate.bar(xp - w/2, avg_match, w, color=COLORS["A"], alpha=0.85,
                     label="Tool Match Rate", edgecolor="white")
    b2 = ax_rate.bar(xp + w/2, avg_first, w, color=COLORS["B"], alpha=0.85,
                     label="First Tool Correct", edgecolor="white")
    for bar, v in zip(list(b1) + list(b2), list(avg_match) + list(avg_first)):
        ax_rate.text(bar.get_x() + bar.get_width() / 2, v + 0.01,
                     f"{v:.2f}", ha="center", va="bottom", fontsize=9)
    ax_rate.set_xticks(xp)
    ax_rate.set_xticklabels(conditions, fontsize=9)
    ax_rate.set_ylim(0, 1.3)
    ax_rate.set_ylabel("Rate (avg T1/T2/T3)")
    ax_rate.set_title("(b) Tool Planning Accuracy", fontweight="bold")
    ax_rate.legend(fontsize=8)
    ax_rate.grid(axis="y", alpha=0.3)

    fig.suptitle("Exp4: Knowledge Ablation (K0-K3) — Token Cost vs Accuracy",
                 fontweight="bold")
    fig.tight_layout()
    _save(fig, "Fig4a_exp4_ablation", show)

    # --- Fig4b: adversarial detection ---
    adv_results = adv_data["results"]
    n_adv   = len(adv_results)
    det     = [r.get("anomaly_detected", False) for r in adv_results]
    basins  = [r["basin_id"] for r in adv_results]

    fig, ax = plt.subplots(figsize=(5, 3.5))
    colors  = [COLORS["pass"] if d else COLORS["fail"] for d in det]
    ax.bar(range(n_adv), [1] * n_adv, color=colors, alpha=0.85, edgecolor="white")
    for i, (bid, d) in enumerate(zip(basins, det)):
        status = "DETECTED" if d else "MISSED"
        ax.text(i, 0.5, status, ha="center", va="center",
                fontsize=9, color="white", fontweight="bold", rotation=90)
        ax.text(i, 1.05, bid, ha="center", va="bottom", fontsize=8)
        kws = adv_results[i].get("keywords_found", [])
        if kws:
            ax.text(i, -0.08, ", ".join(kws[:2]), ha="center", va="top",
                    fontsize=7, color="gray")
    ax.set_xticks(range(n_adv))
    ax.set_xticklabels(basins, fontsize=8.5)
    ax.set_ylim(-0.2, 1.3)
    ax.set_yticks([])
    ax.set_title("Exp4: Adversarial Prior Detection (K3)\n"
                 "Injected: NSE=0.97, params at boundaries",
                 fontweight="bold")
    ax.legend(handles=[
        mpatches.Patch(color=COLORS["pass"], alpha=0.85, label="Anomaly Detected"),
        mpatches.Patch(color=COLORS["fail"], alpha=0.85, label="Missed"),
    ], fontsize=8.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    fig.tight_layout()
    _save(fig, "Fig4b_exp4_adversarial", show)


# ===========================================================================
# Dispatch
# ===========================================================================

EXP_MAP = {1: fig_exp1, 2: fig_exp2, 3: fig_exp3, 4: fig_exp4}


def main():
    _style()

    parser = argparse.ArgumentParser(description="Generate HydroAgent paper figures")
    parser.add_argument("--exp", type=int, nargs="+",
                        help="Experiment numbers to plot (default: all available)")
    parser.add_argument("--show", action="store_true",
                        help="Display figures interactively")
    args = parser.parse_args()

    exps = args.exp if args.exp else list(EXP_MAP.keys())
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\nGenerating figures -> {FIG_DIR}/\n")
    for exp_num in exps:
        print(f"[Exp{exp_num}]")
        d = _load(exp_num)
        if d is None:
            continue
        try:
            EXP_MAP[exp_num](d, show=args.show)
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()

    print(f"\nDone. Check {FIG_DIR}/")


if __name__ == "__main__":
    main()

"""
Paper Figure Generator for HydroClaw
=====================================
从各实验的 JSON 结果文件生成论文图表（PNG + PDF）。
支持单独指定实验绘图，也可一次全部生成。

用法：
  python scripts/plot_paper_figures.py          # 生成所有可用图
  python scripts/plot_paper_figures.py --exp 2  # 只生成 Exp2 的图

输出目录：results/paper/figures/

图表列表：
  Fig1_exp1_nse_heatmap.pdf        Exp1: NSE 热力图（流域 × 模型）
  Fig1_exp1_nse_bar.pdf            Exp1: 训练/测试期 NSE 分组柱状图
  Fig2_exp2_method_comparison.pdf  Exp2: A/B/C 三路 NSE 对比 + 边界命中
  Fig2_exp2_nse_trajectory.pdf     Exp2: Method C NSE 收敛轨迹
  Fig3_exp3_match_rate.pdf         Exp3: 知识条件 × 场景类别匹配率
  Fig4_exp4_skill_creation.pdf     Exp4: Skill 生成成功率瀑布图
  Fig5_exp5_memory.pdf             Exp5: 三阶段记忆验证综合图
  Fig6_exp6_ablation_heatmap.pdf   Exp6: 三层知识消融热力图
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import json
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

warnings.filterwarnings("ignore")

# ── 全局样式 ─────────────────────────────────────────────────────────────────

RESULTS_DIR = Path("results/paper")
FIG_DIR     = RESULTS_DIR / "figures"

# 论文配色方案（色盲友好）
COLORS = {
    "A":  "#4878CF",   # 蓝：Method A / 标准
    "B":  "#D65F5F",   # 红：Method B / Zhu et al.
    "C":  "#6ACC65",   # 绿：Method C / HydroClaw
    "full": "#2c7bb6", # 蓝：full_knowledge
    "none": "#d7191c", # 红：no_knowledge
    "K0": "#d9d9d9",
    "K1": "#a6bddb",
    "K2": "#3690c0",
    "K3": "#034e7b",
    "pass": "#4dac26",
    "fail": "#d01c8b",
    "gray": "#888888",
}

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

def _save(fig, name: str):
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        p = FIG_DIR / f"{name}.{ext}"
        fig.savefig(p)
    print(f"  Saved: {name}.pdf / .png")
    plt.close(fig)

def _load(exp_num: int) -> dict | None:
    p = RESULTS_DIR / f"exp{exp_num}" / f"exp{exp_num}_results.json"
    if not p.exists():
        print(f"  [skip] {p} not found")
        return None
    return json.loads(p.read_text(encoding="utf-8"))


# ── Exp1 ─────────────────────────────────────────────────────────────────────

def fig_exp1(data: dict):
    """Fig1a: NSE 热力图（流域 × 模型）
       Fig1b: 训练期 vs 测试期 NSE 分组柱状图
    """
    results = data["results"]
    basins = sorted({r["basin_id"] for r in results})
    models = sorted({r["model_name"] for r in results})

    # ── Fig1a: 热力图 ──────────────────────────────────────────────────────
    train_mat = np.full((len(basins), len(models)), np.nan)
    test_mat  = np.full((len(basins), len(models)), np.nan)
    for r in results:
        i = basins.index(r["basin_id"])
        j = models.index(r["model_name"])
        if r["success"]:
            train_mat[i, j] = r["train_metrics"].get("NSE", np.nan)
            test_mat[i, j]  = r.get("test_metrics", {}).get("NSE", np.nan)

    fig, axes = plt.subplots(1, 2, figsize=(9, 4))
    for ax, mat, title in zip(axes, [train_mat, test_mat], ["Train NSE", "Test NSE"]):
        im = ax.imshow(mat, vmin=0.4, vmax=1.0, cmap="RdYlGn", aspect="auto")
        ax.set_xticks(range(len(models)))
        ax.set_xticklabels([m.upper() for m in models])
        ax.set_yticks(range(len(basins)))
        ax.set_yticklabels(basins, fontsize=8)
        ax.set_title(title)
        ax.grid(False)
        for i in range(len(basins)):
            for j in range(len(models)):
                v = mat[i, j]
                if not np.isnan(v):
                    ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                            fontsize=8, color="black" if v > 0.6 else "white")
        fig.colorbar(im, ax=ax, shrink=0.8)

    fig.suptitle("Exp1: Standard Calibration — NSE Heatmap", fontweight="bold")
    fig.tight_layout()
    _save(fig, "Fig1a_exp1_nse_heatmap")

    # ── Fig1b: 分组柱状图（训练 vs 测试）─────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 4))
    n_groups  = len(basins)
    n_models  = len(models)
    width     = 0.35
    x         = np.arange(n_groups)

    model_colors = ["#4878CF", "#D65F5F", "#6ACC65", "#FF9F40"]
    for j, model in enumerate(models):
        train_vals = []
        test_vals  = []
        for basin in basins:
            r = next((r for r in results if r["basin_id"] == basin and r["model_name"] == model), {})
            train_vals.append(r.get("train_metrics", {}).get("NSE", 0) if r.get("success") else 0)
            test_vals.append(r.get("test_metrics", {}).get("NSE", 0) if r.get("success") else 0)

        offset = (j - (n_models - 1) / 2) * width
        bars_t = ax.bar(x + offset, train_vals, width * 0.45,
                        color=model_colors[j], alpha=0.85,
                        label=f"{model.upper()} Train")
        bars_v = ax.bar(x + offset + width * 0.45, test_vals, width * 0.45,
                        color=model_colors[j], alpha=0.45,
                        label=f"{model.upper()} Test")

    ax.axhline(0.75, color="gray", ls="--", lw=1, alpha=0.7, label="NSE=0.75 (good)")
    ax.axhline(0.65, color="gray", ls=":",  lw=1, alpha=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(basins, rotation=15, ha="right")
    ax.set_ylabel("NSE")
    ax.set_ylim(0, 1.05)
    ax.set_title("Exp1: Standard Calibration — Train vs Test NSE", fontweight="bold")
    ax.legend(ncol=n_models, loc="upper right", fontsize=8)
    fig.tight_layout()
    _save(fig, "Fig1b_exp1_nse_bar")


# ── Exp2 ─────────────────────────────────────────────────────────────────────

def fig_exp2(data: dict):
    """Fig2a: A/B/C 三路 NSE 对比柱状图（含边界命中标注）
       Fig2b: Method C NSE 收敛轨迹（折线）
    """
    results = data["results"]
    basins  = [r["basin_id"] for r in results]

    # ── Fig2a: 三路对比 ────────────────────────────────────────────────────
    a_nse = [r["method_A"].get("train_metrics", {}).get("NSE") for r in results]
    b_nse = [r["method_B"].get("best_nse") for r in results]
    c_nse = [r["method_C"].get("best_nse") for r in results]

    x = np.arange(len(basins))
    width = 0.25
    fig, ax = plt.subplots(figsize=(8, 4.5))

    def safe(vals):
        return [v if isinstance(v, float) else 0 for v in vals]

    ba = ax.bar(x - width, safe(a_nse), width, color=COLORS["A"], alpha=0.85, label="A: Standard SCE-UA")
    bb = ax.bar(x,         safe(b_nse), width, color=COLORS["B"], alpha=0.85, label="B: Zhu et al. 2026")
    bc = ax.bar(x + width, safe(c_nse), width, color=COLORS["C"], alpha=0.85, label="C: HydroClaw (ours)")

    # 标注 Δ(C-A)
    for i, (na, nc) in enumerate(zip(a_nse, c_nse)):
        if isinstance(na, float) and isinstance(nc, float) and nc > na:
            ax.annotate(
                f"+{nc-na:.3f}",
                xy=(x[i] + width, nc + 0.005),
                ha="center", va="bottom", fontsize=7.5, color=COLORS["C"],
                fontweight="bold",
            )

    # 标注边界命中数量（method A）
    for i, r in enumerate(results):
        hits = len(r["method_A"].get("boundary_hits", []))
        if hits > 0:
            ax.text(x[i] - width, 0.02, f"⚠{hits}", ha="center", va="bottom",
                    fontsize=7, color="#8B0000")

    ax.axhline(0.75, color="gray", ls="--", lw=1, alpha=0.6, label="NSE=0.75")
    ax.set_xticks(x)
    ax.set_xticklabels(basins, rotation=10)
    ax.set_ylabel("NSE (train period)")
    ax.set_ylim(0, 1.0)
    ax.set_title("Exp2: LLM Calibration Comparison — Three Methods", fontweight="bold")
    ax.legend(loc="upper right")
    # ⚠N = N parameter boundary hits in Method A
    ax.text(0.01, 0.02, "⚠N = boundary hits in Method A",
            transform=ax.transAxes, fontsize=7, color="#8B0000", alpha=0.7)
    fig.tight_layout()
    _save(fig, "Fig2a_exp2_method_comparison")

    # ── Fig2b: Method C NSE 收敛轨迹 ─────────────────────────────────────
    fig, ax = plt.subplots(figsize=(7, 4))
    traj_colors = ["#1b7837", "#762a83", "#e08214"]
    for i, r in enumerate(results):
        hist = r["method_C"].get("nse_history", [])
        hist = [v for v in hist if isinstance(v, float)]
        if hist:
            rounds = list(range(1, len(hist) + 1))
            ax.plot(rounds, hist, "o-", color=traj_colors[i % len(traj_colors)],
                    lw=2, ms=6, label=r["basin_id"])
            # Method A baseline
            a = r["method_A"].get("train_metrics", {}).get("NSE")
            if isinstance(a, float):
                ax.axhline(a, color=traj_colors[i % len(traj_colors)],
                           ls=":", lw=1.2, alpha=0.5)

    ax.axhline(0.75, color="gray", ls="--", lw=1, alpha=0.7, label="Target NSE")
    ax.set_xlabel("Round (LLM range adjustment)")
    ax.set_ylabel("NSE")
    ax.set_title("Exp2: Method C — NSE Convergence Trajectory", fontweight="bold")
    ax.legend()
    ax.set_xticks(range(1, max(
        len([v for v in r["method_C"].get("nse_history",[]) if isinstance(v,float)])
        for r in results
    ) + 1))
    # 虚线 = Method A baseline
    ax.text(0.98, 0.02, "dotted = Method A (SCE-UA) baseline",
            transform=ax.transAxes, ha="right", fontsize=7.5, color="gray")
    fig.tight_layout()
    _save(fig, "Fig2b_exp2_nse_trajectory")


# ── Exp3 ─────────────────────────────────────────────────────────────────────

def fig_exp3(data: dict):
    """Fig3: 知识条件 × 场景类别 匹配率对比（分组柱状图 + 差值标注）"""
    results = data["results"]
    conditions = data.get("conditions", ["full_knowledge", "no_knowledge"])

    # 按 category 和 condition 聚合
    from collections import defaultdict
    cat_data: dict = defaultdict(lambda: defaultdict(lambda: {"n": 0, "ok": 0}))
    for r in results:
        cat_data[r["category"]][r["condition"]]["n"] += 1
        if r.get("match"):
            cat_data[r["category"]][r["condition"]]["ok"] += 1

    categories = list(cat_data.keys())
    n = len(categories)
    x = np.arange(n)
    width = 0.35

    fig, ax = plt.subplots(figsize=(11, 4.5))
    for ci, (cond, color) in enumerate(zip(conditions, [COLORS["full"], COLORS["none"]])):
        rates = [
            cat_data[cat][cond]["ok"] / cat_data[cat][cond]["n"]
            if cat_data[cat][cond]["n"] > 0 else 0
            for cat in categories
        ]
        offset = (ci - 0.5) * width
        bars = ax.bar(x + offset, rates, width, color=color, alpha=0.85,
                      label=cond.replace("_", " "))
        # 标注具体值
        for bar, val in zip(bars, rates):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, val + 0.02,
                        f"{val:.0%}", ha="center", va="bottom", fontsize=7.5)

    # 整体匹配率
    stats = data.get("stats_by_condition", {})
    for cond, color, anchor_x in zip(conditions,
                                      [COLORS["full"], COLORS["none"]],
                                      [0.02, 0.18]):
        s = stats.get(cond, {})
        if s:
            ax.text(anchor_x, 0.97,
                    f"{cond.replace('_', ' ')}: overall {s.get('match_rate', 0):.0%}",
                    transform=ax.transAxes, color=color, fontsize=8.5,
                    va="top", fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels([c.replace("_", "\n") for c in categories],
                       fontsize=8, rotation=0)
    ax.set_ylabel("Tool Sequence Match Rate")
    ax.set_ylim(0, 1.25)
    ax.set_title("Exp3: Natural Language Robustness — Match Rate by Category × Knowledge Condition",
                 fontweight="bold")
    ax.legend(loc="upper right")
    fig.tight_layout()
    _save(fig, "Fig3_exp3_match_rate")


# ── Exp4 ─────────────────────────────────────────────────────────────────────

def fig_exp4(data: dict):
    """Fig4: Skill 生成验证 — 各场景 4 项指标气泡/矩阵图"""
    results = data["results"]
    scenarios = [r["id"] for r in results]
    metrics = [
        ("create_skill_called", "create_skill\ncalled"),
        ("skill_md_exists",     "skill.md\ngenerated"),
        ("tool_py_exists",      "tool.py\ngenerated"),
        ("tool_py_syntax_ok",   "syntax\nvalid"),
        ("tool_registered",     "tool\nregistered"),
    ]

    fig, ax = plt.subplots(figsize=(8, 3.5))
    n_s = len(scenarios)
    n_m = len(metrics)

    for j, (key, label) in enumerate(metrics):
        for i, r in enumerate(results):
            val = r.get(key, False)
            color = COLORS["pass"] if val else COLORS["fail"]
            ax.scatter(j, i, s=320, color=color, zorder=3, marker="s")
            ax.text(j, i, "✓" if val else "✗", ha="center", va="center",
                    fontsize=11, color="white", fontweight="bold")

    ax.set_xticks(range(n_m))
    ax.set_xticklabels([m[1] for m in metrics], fontsize=9)
    ax.set_yticks(range(n_s))
    ax.set_yticklabels([f"{r['id']}\n{r['description'][:22]}" for r in results], fontsize=8)
    ax.set_xlim(-0.5, n_m - 0.5)
    ax.set_ylim(-0.5, n_s - 0.5)
    ax.set_title("Exp4: Dynamic Skill Creation — Verification Matrix", fontweight="bold")
    ax.grid(False)

    # 图例
    pass_patch = mpatches.Patch(color=COLORS["pass"], label="Pass")
    fail_patch = mpatches.Patch(color=COLORS["fail"], label="Fail")
    ax.legend(handles=[pass_patch, fail_patch], loc="lower right")

    # 总体成功率
    sr = data.get("success_rate", 0)
    ax.text(0.98, 0.98, f"Success rate: {sr:.0%}",
            transform=ax.transAxes, ha="right", va="top",
            fontsize=9, fontweight="bold")

    fig.tight_layout()
    _save(fig, "Fig4_exp4_skill_creation")


# ── Exp5 ─────────────────────────────────────────────────────────────────────

def fig_exp5(data: dict):
    """Fig5: 跨会话记忆综合图（3个子图）
       5a: Phase A vs B NSE 对比
       5b: 上下文注入验证（文本标注图）
       5c: Phase C 对抗先验检测结果
    """
    comparisons = data.get("comparisons", [])
    profile_checks = data.get("profile_checks", {})
    context_checks = data.get("context_checks", {})
    adversarial_checks = data.get("adversarial_checks", {})

    fig = plt.figure(figsize=(13, 4.5))
    gs = fig.add_gridspec(1, 3, wspace=0.35)

    # ── 5a: Phase A vs B NSE ─────────────────────────────────────────────
    ax1 = fig.add_subplot(gs[0])
    if comparisons:
        basins  = [c["basin_id"] for c in comparisons]
        nse_a   = [c.get("phase_a_nse") for c in comparisons]
        nse_b   = [c.get("phase_b_nse") for c in comparisons]
        x       = np.arange(len(basins))
        width   = 0.35
        bar1 = ax1.bar(x - width/2, [v or 0 for v in nse_a], width,
                       color="#4878CF", alpha=0.85, label="Phase A (cold)")
        bar2 = ax1.bar(x + width/2, [v or 0 for v in nse_b], width,
                       color="#6ACC65", alpha=0.85, label="Phase B (prior)")
        ax1.set_xticks(x)
        ax1.set_xticklabels(basins, rotation=10, fontsize=8)
        ax1.set_ylabel("NSE")
        ax1.set_ylim(0, 1.0)
        ax1.set_title("5a: Phase A vs B NSE", fontweight="bold")
        ax1.legend(fontsize=7.5)

    # ── 5b: 档案持久化 + 上下文注入验证 ────────────────────────────────
    ax2 = fig.add_subplot(gs[1])
    ax2.axis("off")
    y = 0.92
    ax2.text(0.5, 1.0, "5b: Memory Verification", ha="center", va="top",
             transform=ax2.transAxes, fontsize=10, fontweight="bold")
    for basin_id in list(profile_checks.keys()):
        pc = profile_checks[basin_id]
        cc = context_checks.get(basin_id, {})
        p_ok = pc.get("profile_exists") and pc.get("nse_consistent")
        c_ok = cc.get("profile_in_context")
        color_p = COLORS["pass"] if p_ok  else COLORS["fail"]
        color_c = COLORS["pass"] if c_ok  else COLORS["fail"]
        nse_v = pc.get("saved_nse")
        nse_str = f"{nse_v:.3f}" if isinstance(nse_v, float) else "N/A"
        ax2.text(0.05, y,
                 f"{basin_id}",
                 transform=ax2.transAxes, fontsize=9, fontweight="bold", va="top")
        y -= 0.09
        ax2.text(0.08, y,
                 f"Profile saved (NSE={nse_str}): {'✓' if p_ok else '✗'}",
                 transform=ax2.transAxes, fontsize=8.5, color=color_p, va="top")
        y -= 0.09
        ax2.text(0.08, y,
                 f"Profile in LLM context:  {'✓' if c_ok else '✗'}",
                 transform=ax2.transAxes, fontsize=8.5, color=color_c, va="top")
        y -= 0.12

    # ── 5c: 对抗先验检测 ────────────────────────────────────────────────
    ax3 = fig.add_subplot(gs[2])
    ax3.axis("off")
    ax3.text(0.5, 1.0, "5c: Adversarial Prior Detection", ha="center", va="top",
             transform=ax3.transAxes, fontsize=10, fontweight="bold")
    y = 0.82
    ax3.text(0.05, y, "Injected prior: NSE=0.97, params at boundaries",
             transform=ax3.transAxes, fontsize=8, color="#8B0000", va="top",
             style="italic")
    y -= 0.14
    for basin_id, ac in adversarial_checks.items():
        detected = ac.get("anomaly_detected", False)
        kws = ac.get("keywords_found", [])
        color = COLORS["pass"] if detected else COLORS["fail"]
        ax3.text(0.05, y,
                 f"{basin_id}:",
                 transform=ax3.transAxes, fontsize=9, fontweight="bold", va="top")
        y -= 0.10
        ax3.text(0.08, y,
                 f"Detected: {'✓ YES' if detected else '✗ NO'}",
                 transform=ax3.transAxes, fontsize=8.5, color=color, va="top")
        y -= 0.10
        if kws:
            ax3.text(0.08, y,
                     f"Keywords: {', '.join(kws[:3])}",
                     transform=ax3.transAxes, fontsize=8, color="gray", va="top")
        y -= 0.14

    fig.suptitle("Exp5: Cross-Session Memory", fontweight="bold", fontsize=12)
    _save(fig, "Fig5_exp5_memory")


# ── Exp6 ─────────────────────────────────────────────────────────────────────

def fig_exp6(data: dict):
    """Fig6a: 三层知识消融热力图（条件 × 场景）
       Fig6b: 知识层叠加效果折线图（match rate vs token cost）
    """
    results_list = data["results"]
    conditions   = data["conditions"]    # [{id, key, name}]
    scenarios    = data["scenarios"]     # [{id, name}]

    cond_ids  = [c["id"]   for c in conditions]
    cond_names= [c["name"] for c in conditions]
    scen_ids  = [s["id"]   for s in scenarios]
    scen_names= [s["name"] for s in scenarios]

    # ── Fig6a: 热力图 ─────────────────────────────────────────────────────
    match_mat = np.zeros((len(cond_ids), len(scen_ids)))
    for r in results_list:
        ci = cond_ids.index(r["condition_id"])  if r["condition_id"]  in cond_ids  else -1
        si = scen_ids.index(r["scenario_id"])   if r["scenario_id"]   in scen_ids  else -1
        if ci >= 0 and si >= 0:
            match_mat[ci, si] = 1.0 if r.get("tool_match") else 0.0

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

    ax = axes[0]
    im = ax.imshow(match_mat, vmin=0, vmax=1, cmap="RdYlGn", aspect="auto")
    ax.set_xticks(range(len(scen_ids)))
    ax.set_xticklabels([f"{sid}\n{sn}" for sid, sn in zip(scen_ids, scen_names)],
                       fontsize=8.5)
    ax.set_yticks(range(len(cond_ids)))
    ax.set_yticklabels(cond_names, fontsize=9)
    ax.set_title("Tool Match (1=pass, 0=fail)", fontweight="bold")
    ax.grid(False)
    for i in range(len(cond_ids)):
        for j in range(len(scen_ids)):
            v = match_mat[i, j]
            ax.text(j, i, "✓" if v == 1.0 else "✗",
                    ha="center", va="center", fontsize=13,
                    color="white" if v == 1.0 else "#cc0000")
    fig.colorbar(im, ax=ax, shrink=0.7)

    # ── Fig6b: 匹配率 vs token 成本折线图 ────────────────────────────────
    ax2 = axes[1]
    stats = data.get("stats_by_condition", {})

    match_rates = [stats.get(cid, {}).get("tool_match_rate", 0) * 100 for cid in cond_ids]
    token_costs = [stats.get(cid, {}).get("avg_tokens", 0) for cid in cond_ids]
    first_rates = [stats.get(cid, {}).get("first_tool_rate", 0) * 100 for cid in cond_ids]

    x = range(len(cond_ids))
    ax2.plot(x, match_rates, "o-", color="#034e7b", lw=2.5, ms=8,
             label="Tool Match Rate (%)")
    ax2.plot(x, first_rates, "s--", color="#3690c0", lw=2, ms=7, alpha=0.8,
             label="First Tool Correct (%)")

    ax2_r = ax2.twinx()
    ax2_r.bar(x, token_costs, alpha=0.3, color="#bdbdbd", label="Avg Tokens (cost)")
    ax2_r.set_ylabel("Avg Token Count", color="gray")
    ax2_r.tick_params(axis="y", colors="gray")

    ax2.set_xticks(x)
    ax2.set_xticklabels(cond_names, rotation=10, fontsize=8.5)
    ax2.set_ylabel("Match Rate (%)")
    ax2.set_ylim(0, 115)
    ax2.set_title("Knowledge Layer Contribution\nvs Token Cost", fontweight="bold")

    lines1, labels1 = ax2.get_legend_handles_labels()
    lines2, labels2 = ax2_r.get_legend_handles_labels()
    ax2.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=7.5)

    fig.suptitle("Exp6: Three-Layer Knowledge Ablation", fontweight="bold", fontsize=12)
    fig.tight_layout()
    _save(fig, "Fig6_exp6_ablation")


# ── 主入口 ───────────────────────────────────────────────────────────────────

EXP_MAP = {
    1: fig_exp1,
    2: fig_exp2,
    3: fig_exp3,
    4: fig_exp4,
    5: fig_exp5,
    6: fig_exp6,
}


def main():
    _style()

    parser = argparse.ArgumentParser(description="Generate paper figures from experiment results")
    parser.add_argument("--exp", type=int, nargs="+",
                        help="Experiment numbers to plot (default: all)")
    args = parser.parse_args()

    exps = args.exp if args.exp else list(EXP_MAP.keys())
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\nGenerating figures -> {FIG_DIR}/\n")
    for exp_num in exps:
        print(f"[Exp{exp_num}]")
        data = _load(exp_num)
        if data is None:
            continue
        try:
            EXP_MAP[exp_num](data)
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()

    print(f"\nDone. Check {FIG_DIR}/")


if __name__ == "__main__":
    main()

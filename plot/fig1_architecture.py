"""
Fig.1 — HydroClaw System Architecture
Clean two-section layout:
  Top row:    End-to-end flow  (User -> Agent -> Tools -> Result)
  Bottom row: Three detail panels (5-layer | System Prompt | ReAct Loop)
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np
from pathlib import Path

OUT = Path(__file__).parent / "fig1_architecture.png"

# ── Palette ───────────────────────────────────────────────────────────────────
BLUE   = "#2E6FD9"
GREEN  = "#2AA55D"
RED    = "#D94F3B"
ORANGE = "#E07B2A"
PURPLE = "#6B4FA0"
TEAL   = "#1E9BA0"
GREY   = "#6B7280"
LGREY  = "#F3F4F6"
WHITE  = "#FFFFFF"
BLACK  = "#111827"

fig, ax = plt.subplots(figsize=(16, 9.5))
ax.set_xlim(0, 16); ax.set_ylim(0, 9.5)
ax.axis("off")
fig.patch.set_facecolor(WHITE)

# ── Helpers ───────────────────────────────────────────────────────────────────
def box(x, y, w, h, fc, ec, lw=1.2, radius=0.25, alpha=1.0):
    p = FancyBboxPatch((x, y), w, h,
                       boxstyle=f"round,pad=0",
                       facecolor=fc, edgecolor=ec, linewidth=lw,
                       alpha=alpha, zorder=3)
    ax.add_patch(p)

def label(x, y, s, size=8.5, weight="normal", color=BLACK, ha="center", va="center"):
    ax.text(x, y, s, fontsize=size, fontweight=weight,
            color=color, ha=ha, va=va, zorder=4)

def arrow_h(x0, x1, y, color=GREY, lw=1.4):
    ax.annotate("", xy=(x1, y), xytext=(x0, y),
                arrowprops=dict(arrowstyle="-|>", color=color,
                                lw=lw, mutation_scale=14),
                zorder=5)

def arrow_v(x, y0, y1, color=GREY, lw=1.4):
    ax.annotate("", xy=(x, y1), xytext=(x, y0),
                arrowprops=dict(arrowstyle="-|>", color=color,
                                lw=lw, mutation_scale=14),
                zorder=5)

def section_title(x, y, s):
    ax.text(x, y, s, fontsize=9.5, fontweight="bold",
            color=BLACK, ha="left", va="bottom", zorder=4)
    ax.plot([x, x + 15.6 if x < 1 else x + 4.8], [y - 0.05, y - 0.05],
            color="#DDDDDD", lw=0.8, zorder=2)


# ══════════════════════════════════════════════════════════════════════════════
# ROW 1 — End-to-end flow  (y: 7.3 – 9.2)
# ══════════════════════════════════════════════════════════════════════════════
section_title(0.2, 9.35, "HydroClaw: Natural Language-Driven Hydrological Modeling Agent")

# Flow boxes
flow_items = [
    (0.25,  "User Query",       "\"Calibrate GR4J\nfor basin 12025000\"",  BLUE,   WHITE),
    (3.35,  "HydroClaw Agent",  "LLM ReAct Loop\n(Brain Layer)",           GREEN,  WHITE),
    (7.55,  "Tool Dispatch",    "calibrate / evaluate\nvalidate / code ...",ORANGE, WHITE),
    (11.75, "Hydrological Pkg", "GR4J / XAJ / HBV\nSCE-UA optimizer",      PURPLE, WHITE),
    (15.0,  "Result",           "NSE / KGE\nparams + report",              TEAL,   WHITE),
]

bw, bh = 2.75, 1.55
by = 7.55
for bx, title, detail, ec, fc in flow_items:
    box(bx, by, bw, bh, fc=LGREY, ec=ec, lw=2.0)
    # colored top strip
    box(bx, by + bh - 0.42, bw, 0.42, fc=ec, ec=ec, lw=0)
    label(bx + bw/2, by + bh - 0.21, title, size=8.5, weight="bold", color=WHITE)
    label(bx + bw/2, by + bh/2 - 0.15, detail, size=7.8, color="#333333")

# Horizontal arrows between flow boxes
arrow_ys = by + bh/2
gap = 0.18
for i in range(len(flow_items) - 1):
    x0 = flow_items[i][0] + bw + gap
    x1 = flow_items[i+1][0] - gap
    arrow_h(x0, x1, arrow_ys, color=GREY, lw=1.5)

# Feedback arrow: Result -> User (bottom arc)
ax.annotate("", xy=(flow_items[0][0] + bw/2, by - 0.05),
            xytext=(flow_items[-1][0] + bw/2, by - 0.05),
            arrowprops=dict(arrowstyle="-|>", color="#999999", lw=1.2,
                            connectionstyle="arc3,rad=-0.25"),
            zorder=5)
label(7.8, by - 0.58, "final answer (text + metrics)", size=7.5, color=GREY)


# ══════════════════════════════════════════════════════════════════════════════
# ROW 2 — Three detail panels  (y: 0.2 – 6.9)
# ══════════════════════════════════════════════════════════════════════════════

# ── Panel separators ──────────────────────────────────────────────────────────
for xv in [5.35, 10.7]:
    ax.plot([xv, xv], [0.25, 7.1], color="#DDDDDD", lw=1.0, ls="--", zorder=2)

# ─────────────────────────────────────────────────────────────────────────────
# PANEL A  Five-Layer Architecture  (x: 0 – 5.35)
# ─────────────────────────────────────────────────────────────────────────────
section_title(0.2, 7.05, "A  Five-Layer Architecture")

layers = [
    ("Brain",        "agent.py",            "LLM reasoning & ReAct orchestration",        BLUE),
    ("Cerebellum",   "skills/*/skill.md",   "Skill manuals injected into system prompt",  GREEN),
    ("Spine",        "adapters/",           "PackageAdapter — bidirectional translation",  RED),
    ("Nerve",        "tools/*.py",          "Tool routing — thin dispatch wrappers",       ORANGE),
    ("Muscle",       "hydromodel pkg",      "Numerical compute: SCE-UA, GR4J, XAJ ...",   PURPLE),
]

lx, lw_p, lh, lgap = 0.25, 4.85, 0.95, 0.22
ly_start = 6.55
for i, (name, code, desc, color) in enumerate(layers):
    ly = ly_start - i * (lh + lgap)
    # background
    box(lx, ly, lw_p, lh, fc=color, ec=color, lw=0, alpha=0.10)
    box(lx, ly, lw_p, lh, fc="none", ec=color, lw=1.6)
    # left accent bar
    box(lx, ly, 0.12, lh, fc=color, ec=color, lw=0)
    # text
    label(lx + 0.25, ly + lh * 0.68, name, size=9, weight="bold",
          color=color, ha="left")
    label(lx + 0.25, ly + lh * 0.38, code, size=7.5, color=GREY,
          ha="left")
    label(lx + 0.25, ly + lh * 0.10, desc, size=7.5, color="#444444",
          ha="left")
    # connector arrow
    if i < len(layers) - 1:
        arrow_v(lx + lw_p/2, ly - 0.01, ly - lgap + 0.01, color="#AAAAAA", lw=1.2)

# ─────────────────────────────────────────────────────────────────────────────
# PANEL B  System Prompt Assembly  (x: 5.5 – 10.7)
# ─────────────────────────────────────────────────────────────────────────────
section_title(5.55, 7.05, "B  Dynamic System Prompt  _build_system_prompt(query)")

prompt_sections = [
    ("§1",   "Core Identity",      "Role, principles & safety constraints",     BLUE),
    ("§1.5", "Behavior Policies",  "agent_behavior / calibration_policy.md",    RED),
    ("§1.7", "Cognitive Skills",   "expert_hydrologist.skill — always active",  GREEN),
    ("§2",   "Skill Index",        "Available skills + read paths (on demand)", "#2AA55D"),
    ("§3",   "Adapter Docs",       "PackageAdapter capabilities per task",       ORANGE),
    ("§4",   "Domain Knowledge",   "knowledge/*.md  — hydrology references",     PURPLE),
    ("§5",   "Basin Memory",       "basin_profiles + MEMORY.md — session prior", TEAL),
]

bx_p = 5.55; bw_p = 4.85; bh_p = 0.72; bgap = 0.10
by_p = 6.55
for i, (num, title, detail, color) in enumerate(prompt_sections):
    py = by_p - i * (bh_p + bgap)
    box(bx_p, py, bw_p, bh_p, fc=LGREY, ec=color, lw=1.4)
    # section number badge
    box(bx_p, py, 0.55, bh_p, fc=color, ec=color, lw=0)
    label(bx_p + 0.275, py + bh_p/2, num, size=8, weight="bold", color=WHITE)
    label(bx_p + 0.70, py + bh_p * 0.68, title, size=8.5, weight="bold",
          color=color, ha="left")
    label(bx_p + 0.70, py + bh_p * 0.25, detail, size=7.5, color=GREY,
          ha="left")

# brace label
label(10.35, 3.8, "injected\nper query", size=7.5, color=GREY, ha="center")
ax.annotate("", xy=(10.58, 3.8), xytext=(10.38, 3.8),
            arrowprops=dict(arrowstyle="-|>", color=GREY, lw=1.2), zorder=5)

# ─────────────────────────────────────────────────────────────────────────────
# PANEL C  ReAct Loop  (x: 10.85 – 15.95)
# ─────────────────────────────────────────────────────────────────────────────
section_title(10.9, 7.05, "C  ReAct Agentic Loop  (up to 20 turns)")

react_steps = [
    ("Observe",  "Read system prompt + conversation history",  BLUE),
    ("Think",    "LLM generates reasoning + tool plan",        GREEN),
    ("Act",      "Execute tool call(s) with arguments",        ORANGE),
    ("Observe",  "Receive tool output, update context",        BLUE),
    ("...",      "Repeat until task complete",                 GREY),
    ("Respond",  "Return final answer to user",                TEAL),
]

rx = 10.9; rw = 4.85; rh = 0.72; rgap = 0.10
ry_start = 6.55
for i, (step, desc, color) in enumerate(react_steps):
    ry = ry_start - i * (rh + rgap)
    is_repeat = step == "..."
    fc = "#F9F9F9" if is_repeat else LGREY
    ec = "#BBBBBB" if is_repeat else color
    lw = 0.8 if is_repeat else 1.4
    box(rx, ry, rw, rh, fc=fc, ec=ec, lw=lw)
    if not is_repeat:
        box(rx, ry, 1.10, rh, fc=color, ec=color, lw=0)
        label(rx + 0.55, ry + rh/2, step, size=8.5, weight="bold", color=WHITE)
        label(rx + 1.25, ry + rh/2, desc, size=7.8, color="#333333", ha="left")
    else:
        label(rx + rw/2, ry + rh/2, step + "  " + desc, size=7.5, color=GREY,
              ha="center", weight="normal")
    # arrow down
    if i < len(react_steps) - 1:
        ny = ry_start - (i+1) * (rh + rgap) + rh
        arrow_v(rx + rw/2, ry - 0.01, ny + 0.01, color="#AAAAAA", lw=1.2)

# Loop-back arrow on right side
loop_top = ry_start + rh * 0.5            # middle of Observe (1st)
loop_bot = ry_start - 3*(rh+rgap) + rh*0.5  # middle of Observe (4th)
ax.annotate("",
            xy=(rx + rw + 0.15, loop_top),
            xytext=(rx + rw + 0.15, loop_bot),
            arrowprops=dict(arrowstyle="-|>", color=RED, lw=1.4,
                            connectionstyle="arc3,rad=0.0"),
            zorder=5)
ax.plot([rx + rw, rx + rw + 0.15], [loop_bot, loop_bot], color=RED, lw=1.4, zorder=5)
ax.plot([rx + rw, rx + rw + 0.15], [loop_top, loop_top], color=RED, lw=1.4, zorder=5)
label(rx + rw + 0.52, (loop_top + loop_bot)/2, "loop\nback", size=7.5,
      color=RED, ha="center")

# ── Figure caption ────────────────────────────────────────────────────────────
fig.text(0.5, 0.005,
         "Figure 1.  Architecture of HydroClaw.  "
         "(A) Five-layer brain-spine-limb design separates reasoning, knowledge, routing, and computation.  "
         "(B) Seven-section system prompt assembled dynamically per query.  "
         "(C) ReAct loop iterates Observe-Think-Act until task completion.",
         ha="center", va="bottom", fontsize=8, color=GREY,
         wrap=True)

plt.tight_layout(pad=0.3)
plt.savefig(OUT, dpi=300, bbox_inches="tight", facecolor=WHITE)
plt.close()
print(f"Saved: {OUT}")

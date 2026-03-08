"""
Experiment 5 - 跨会话记忆与先验注入
======================================
目的：验证流域档案（basin profile）的持久化、上下文注入及先验鲁棒性。
方法：三阶段实验

  Phase A (冷启动)  → 率定 → 验证 basin_profiles/<id>.json 正确写入
  Phase B (有先验)  → 再次率定同一流域 → 验证 system prompt 包含先验片段
  Phase C (对抗先验) → 注入故意错误的参数先验 → 验证 LLM 能识别并给出预警

评估：
  - Phase A: 档案 JSON 内容正确性（NSE、参数值与率定结果一致）
  - Phase B: system prompt 中是否出现 "Basin {id}" 先验段落
  - Phase C: LLM 响应是否包含"异常/可疑/偏差"等预警词

论文对应：Section 4.6
参考文献：NHRI 2025（专家知识引导策略 NSE +0.14），AgentHPO（历史记忆机制）
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import logging
import time
from datetime import datetime

import matplotlib
matplotlib.use("Agg")

logger = logging.getLogger(__name__)

BASINS = [
    ("12025000", "Fish River, ME",    "easy"),    # 易率定：提供干净先验
    ("06043500", "Gallatin River, MT", "hard"),   # 困难：验证错误先验检测
]
MODEL     = "gr4j"
ALGORITHM = "SCE_UA"
OUTPUT_DIR = Path("results/paper/exp5")

# 对抗先验：故意填入物理上不合理的极端值
ADVERSARIAL_PRIORS = {
    "12025000": {
        "gr4j": {
            "train_nse": 0.97,           # 不可能这么高的 NSE
            "best_params": {
                "x1": 1998.0,            # 极端值（紧贴上界）
                "x2": -9.8,              # 极端值（接近下界）
                "x3": 498.0,             # 极端值
                "x4": 9.9,               # 极端值
            },
            "algorithm": "SCE_UA",
            "calibrated_at": "2025-01-01T00:00:00",
        }
    },
    "06043500": {
        "gr4j": {
            "train_nse": 0.98,
            "best_params": {
                "x1": 1.1,               # 极端值（紧贴下界）
                "x2": 9.9,               # 反物理方向
                "x3": 1.2,
                "x4": 0.51,
            },
            "algorithm": "SCE_UA",
            "calibrated_at": "2025-01-01T00:00:00",
        }
    },
}

ADVERSARIAL_DETECT_KEYWORDS = [
    "异常", "不合理", "可疑", "偏差", "异乎寻常", "极端",
    "unusual", "suspicious", "abnormal", "extreme", "unrealistic", "outlier",
]


def setup_logging():
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(logs_dir / f"exp5_{ts}.log", encoding="utf-8"),
        ],
    )


def _calibrate(basin_id: str, label: str, cfg: dict, workspace: Path) -> dict:
    from hydroclaw.skills.calibration.calibrate import calibrate_model
    from hydroclaw.skills.evaluation.evaluate import evaluate_model

    out_dir = str(OUTPUT_DIR / f"{label}_{MODEL}_{basin_id}")
    t0 = time.time()
    cal = calibrate_model(
        basin_ids=[basin_id], model_name=MODEL,
        algorithm=ALGORITHM, output_dir=out_dir, _cfg=cfg,
    )
    elapsed = round(time.time() - t0, 2)

    record = {
        "basin_id": basin_id, "label": label,
        "success": cal.get("success", False),
        "train_metrics": cal.get("train_metrics", {}),
        "best_params": cal.get("best_params", {}),
        "calibration_dir": cal.get("calibration_dir", ""),
        "calibration_time_s": elapsed,
        "error": cal.get("error"),
    }
    if cal.get("success") and cal.get("calibration_dir"):
        evl = evaluate_model(calibration_dir=cal["calibration_dir"], _cfg=cfg)
        if evl.get("success"):
            record["test_metrics"] = evl.get("metrics", {})
    return record


def _inject_adversarial_prior(basin_id: str, workspace: Path):
    """将对抗先验写入 basin_profiles，模拟下一个会话读到错误历史。"""
    from hydroclaw.memory import Memory
    mem = Memory(workspace)
    prior = ADVERSARIAL_PRIORS.get(basin_id, {}).get(MODEL, {})
    if not prior:
        return
    # 直接写文件（绕过 save_basin_profile 的 append 逻辑，替换为极端值）
    profile_file = mem.basin_profiles_dir / f"{basin_id}.json"
    profile = {
        "basin_id": basin_id,
        "records": [{
            "model": MODEL,
            "algorithm": prior["algorithm"],
            "train_nse": prior["train_nse"],
            "train_kge": None,
            "train_rmse": None,
            "best_params": prior["best_params"],
            "calibrated_at": prior["calibrated_at"],
        }]
    }
    profile_file.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    logger.info(f"  Adversarial prior injected for {basin_id}: NSE={prior['train_nse']}")


def run_experiment() -> dict:
    from hydroclaw.agent import HydroClaw
    from hydroclaw.config import load_config
    from hydroclaw.memory import Memory

    cfg = load_config()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    workspace = OUTPUT_DIR / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    phase_a, phase_b, phase_c = [], [], []
    profile_checks, context_checks, adversarial_checks = {}, {}, {}

    # ── Phase A: 冷启动率定 + 档案持久化验证 ─────────────────────────────
    logger.info("\n── Phase A: Cold-start calibration ──")
    for basin_id, basin_name, difficulty in BASINS:
        logger.info(f"  Basin {basin_id} ({difficulty})")
        rec = _calibrate(basin_id, "phaseA", cfg, workspace)
        phase_a.append(rec)

        # 自动存档（agent.py 里 _execute_tool 已集成，此处手动触发保持一致性）
        mem = Memory(workspace)
        if rec["success"]:
            mem.save_basin_profile(
                basin_id, MODEL, rec["best_params"], rec["train_metrics"], ALGORITHM
            )

        # 验证档案内容
        saved = mem.load_basin_profile(basin_id)
        saved_nse = saved["records"][-1]["train_nse"] if saved and saved.get("records") else None
        real_nse  = rec["train_metrics"].get("NSE")
        profile_checks[basin_id] = {
            "profile_exists": saved is not None,
            "record_count": len(saved.get("records", [])) if saved else 0,
            "nse_consistent": (
                abs(saved_nse - real_nse) < 0.001
                if isinstance(saved_nse, float) and isinstance(real_nse, float) else None
            ),
            "saved_nse": saved_nse,
            "real_nse": real_nse,
        }

    # ── Phase B: 有先验的第二次率定 + 上下文注入验证 ──────────────────────
    logger.info("\n── Phase B: Second calibration + context injection check ──")
    agent = HydroClaw(workspace=workspace)

    for basin_id, basin_name, difficulty in BASINS:
        # 验证上下文注入
        query = f"率定GR4J模型，流域{basin_id}"
        messages = agent._build_context(query)
        sys_prompt = messages[0]["content"] if messages else ""
        has_prior = f"Basin {basin_id}" in sys_prompt
        excerpt = ""
        if has_prior:
            idx = sys_prompt.find(f"Basin {basin_id}")
            excerpt = sys_prompt[idx: idx + 250].replace("\n", " ")
        context_checks[basin_id] = {
            "profile_in_context": has_prior,
            "excerpt": excerpt,
        }
        logger.info(f"  {basin_id}: profile_in_context={has_prior}")

        # 执行第二次率定
        rec = _calibrate(basin_id, "phaseB", cfg, workspace)
        phase_b.append(rec)
        mem = Memory(workspace)
        if rec["success"]:
            mem.save_basin_profile(
                basin_id, MODEL, rec["best_params"], rec["train_metrics"], ALGORITHM
            )

    # ── Phase C: 对抗先验注入 + LLM 异常检测验证 ──────────────────────────
    logger.info("\n── Phase C: Adversarial prior + LLM anomaly detection ──")
    agent_c = HydroClaw(workspace=workspace)

    for basin_id, basin_name, difficulty in BASINS:
        _inject_adversarial_prior(basin_id, workspace)

        # 运行 agent，给 LLM 机会察觉先验异常（不执行实际率定，只让 LLM 规划）
        query = (
            f"请分析流域{basin_id}的历史率定档案，并给出下一步率定建议。"
            f"如果发现任何异常，请明确指出。"
        )
        agent_c.memory._log.clear()
        t0 = time.time()
        try:
            response = agent_c.run(query)
            elapsed = round(time.time() - t0, 2)
            response_lower = (response or "").lower()
            detected = any(kw in response_lower for kw in ADVERSARIAL_DETECT_KEYWORDS)
            adversarial_checks[basin_id] = {
                "anomaly_detected": detected,
                "keywords_found": [kw for kw in ADVERSARIAL_DETECT_KEYWORDS if kw in response_lower],
                "response_preview": (response or "")[:400],
                "time_s": elapsed,
            }
        except Exception as e:
            adversarial_checks[basin_id] = {"anomaly_detected": False, "error": str(e)}
        logger.info(f"  {basin_id}: anomaly_detected={adversarial_checks[basin_id].get('anomaly_detected')}")

    # ── Phase A vs B NSE 对比 ──────────────────────────────────────────────
    comparisons = []
    for a, b in zip(phase_a, phase_b):
        nse_a = a["train_metrics"].get("NSE")
        nse_b = b["train_metrics"].get("NSE")
        comparisons.append({
            "basin_id": a["basin_id"],
            "phase_a_nse": nse_a,
            "phase_b_nse": nse_b,
            "delta": round(nse_b - nse_a, 4) if isinstance(nse_a, float) and isinstance(nse_b, float) else None,
            "phase_a_time_s": a["calibration_time_s"],
            "phase_b_time_s": b["calibration_time_s"],
        })

    return {
        "experiment": "exp5_memory",
        "timestamp": datetime.now().isoformat(),
        "model": MODEL, "algorithm": ALGORITHM,
        "phase_a": phase_a,
        "phase_b": phase_b,
        "profile_checks": profile_checks,
        "context_checks": context_checks,
        "adversarial_checks": adversarial_checks,
        "comparisons": comparisons,
    }


def save_results(results: dict):
    f = OUTPUT_DIR / "exp5_results.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    logger.info(f"Saved -> {f}")


def print_summary(results: dict):
    print(f"\n{'='*80}")
    print(f"  Exp5: Cross-Session Memory")
    print(f"{'='*80}")

    print(f"\n  Phase A — Profile Persistence:")
    for bid, c in results["profile_checks"].items():
        ok = "PASS" if c["profile_exists"] and c.get("nse_consistent") else "FAIL"
        print(f"    [{ok}] {bid}: exists={c['profile_exists']}, "
              f"nse_consistent={c.get('nse_consistent')}, "
              f"saved_nse={c.get('saved_nse'):.3f if isinstance(c.get('saved_nse'), float) else 'N/A'}")

    print(f"\n  Phase B — Context Injection:")
    for bid, c in results["context_checks"].items():
        ok = "PASS" if c["profile_in_context"] else "FAIL"
        print(f"    [{ok}] {bid}: in_context={c['profile_in_context']}")
        if c.get("excerpt"):
            print(f"           Excerpt: ...{c['excerpt'][:100]}...")

    print(f"\n  Phase C — Adversarial Prior Detection:")
    for bid, c in results["adversarial_checks"].items():
        ok = "PASS" if c.get("anomaly_detected") else "FAIL"
        kws = ", ".join(c.get("keywords_found", []))
        print(f"    [{ok}] {bid}: detected={c.get('anomaly_detected')}, keywords=[{kws}]")

    print(f"\n  Phase A vs B NSE Comparison:")
    header = f"{'Basin':<12} {'A NSE':>9} {'B NSE':>9} {'Delta':>8} {'A time':>8} {'B time':>8}"
    print(f"    {header}")
    print(f"    {'-'*60}")
    for c in results["comparisons"]:
        fmt = lambda v: f"{v:.4f}" if isinstance(v, float) else "N/A"
        dfmt = lambda v: f"{v:+.4f}" if isinstance(v, float) else "N/A"
        print(f"    {c['basin_id']:<12} {fmt(c['phase_a_nse']):>9} "
              f"{fmt(c['phase_b_nse']):>9} {dfmt(c.get('delta')):>8} "
              f"{c['phase_a_time_s']:>7.1f}s {c['phase_b_time_s']:>7.1f}s")


def main():
    setup_logging()
    logger.info("Starting Exp5: Cross-Session Memory")
    results = run_experiment()
    save_results(results)
    print_summary(results)
    logger.info("Exp5 complete")


if __name__ == "__main__":
    main()

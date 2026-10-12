---
name: Checkpoint Calibration
description: One persistent ReAct basin study with real call accounting, optimizer continuation and warm restart.
keywords: [checkpoint, 检查点, 暖启动, 续跑, 搜索预算, 种群状态]
tools: [start_calibration_study, inspect_calibration_study, advance_calibration_study, probe_calibration_study, finalize_calibration_study]
when_to_use: Deployment-authorized XAJ checkpoint experiment; do not use the legacy multi-round llm_calibrate loop.
---

## 必须遵守的观测—决策合同

首次决策完整阅读本文件；每次先 inspect 当前 study/checkpoint，读取真实预算、停止原因、历史决策、全局冠军与当前阶段最佳。不能根据对话记忆替代当前状态。水文参数假设另读 ../adaptive_calibration/skill.md。

每500次 search 的改善量为 100×(best_before−best_after)/best_before，目标为最小率定 RMSE，不是最大 NSE。窗口不足、基准为零或数据缺失时标为不足以判断。开发建议：连续两个完整窗口改善均≤0.1%才称候选停滞；>0.1%称可观察改善。这是待预注册/验证的项目阈值，不是算法停止条件或水文标准，不能看结果临时换阈值。

集中标志读取 concentrated_candidate_flag：在固定外层范围归一化后，至少80%维度的P90−P10≤0.05且整体RMS分散度≤0.03。不得用缩小后的内层范围制造集中结论。优秀前20%候选位于当前范围两端5%的比例由 boundary_fraction_elite 提供；某端比例≥0.5仅作为开发候选贴边信号，不能自动扩界。

| 实际证据 | 允许的决策与必须说明的理由 |
|---|---|
| 有改善，且无新证据要求改变搜索区域 | 优先 continue，保留全部状态；不强制调参 |
| 停滞但仍分散，或窗口不足 | 可再 continue 一个可负担窗口；不能称陷入局部最优 |
| 持续停滞且集中 | 考虑 warm_restart，保留成绩与差异兼顾的历史点并补探索点；说明补点成本 |
| 精英贴边且过程诊断支持某方向 | 在 outer_ranges 内提出可回退范围试验，用 warm_restart；贴边本身不足以确定方向 |
| 算法已收敛 | 不能 continue；在预算内选择有理由的 warm_restart 或 stop |
| 总额度耗尽、截止或终止 | 不推进搜索；按状态冻结/最终评价。异常待核对时不得重放 |

修改 ranges 或 ngs/kstop/peps/pcento/random_seed 必须显式 restart，当前 continue 禁止更改。ngs决定31×ngs初始种群；增加提高覆盖也增加补点成本。kstop是停止历史窗口，peps是几何收敛阈值，pcento是目标改善停止阈值；放宽或收紧停止不能保证更优。random_seed控制随机轨迹，continue不能换种子。暖启动重置收敛历史而不清除旧冠军；当前阶段改善但未超过旧冠军时，不得只用全局停滞判定该阶段失败。

每次 advance 的 decision 填 evidence/hypothesis/prediction/falsification：引用checkpoint、candidate、窗口数值、原/新范围或设置、竞争解释、预计补点调用和下一窗口反证。stop使用call_limit=0。既有窗口不足就如实说明，不补造观测。每轮核对实际执行后的收益与原预测，允许继续、回退和停止，不设强制探针次数。

Keep one basin in one Agent conversation. Validate the data, start ONE authorized study, inspect evidence, submit a decision, inspect its executed outcome, and repeat. Tools contain no LLM and do not select the next strategy.

The study_id and checkpoint_id identify durable optimizer state and experimental memory. Context compression must not erase previous submitted hypotheses, predictions, controls and real outcomes; use inspect to reread them.

Only deployment grants budget, basin, data, model and objective. call_limit is a next-segment TARGET, not rep; accepted simplex-update boundaries can overshoot the target by at most two simulations, but global search quota never does. All failed started simulations are charged. Probes have a separate auxiliary grant; two calls are reserved for final evaluation.

continue preserves population, both RNG streams, configuration and stopping history. warm_restart explicitly selects legal old search candidates, preserves their recorded scores, fills the rest and starts a new convergence history. cold_restart generates all points again. Changed settings/ranges require an explicit restart. Do not describe a restart as continuation.

Read population dispersion, objective improvement windows, candidate identity and actual NSE/PBIAS. Threshold flags are development candidates, not standards or evidence of global optimality. Population concentration alone does not justify narrowing bounds. Calibrating a new region may improve without beating the retained global champion: inspect both phase-best and global-best.

Each advance requires evidence, hypothesis, prediction and falsification strings. Cite actual checkpoint/candidate/probe identities in evidence. No-change continuation is valid. Local probes do not establish global sensitivity, are not search champions, and only use calibration observations. Do not guess water-balance closure or parameter causal directions from NSE alone.

Final test period is not available to the decision tools. Stop/freeze decisions before finalize_calibration_study. Deliver the SAME calibration-RMSE champion, report both search and auxiliary calls, stop reason, costs and limitations. Only scientific_completed=true from finalize confirms completion; a failed/paused/tool-completed conversation does not.

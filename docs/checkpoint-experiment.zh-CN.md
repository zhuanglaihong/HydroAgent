# XAJ 检查点实验实现

此路径保留原 ReAct 会话，不新增 LLM 客户端，不修改 hydromodel 或安装的 SPOTPY 源码。新增研究执行器调用 hydromodel 的 `UnifiedCalibrator`（兼容旧 `UnifiedModelSetup`）模拟和目标接口，复用 SPOTPY 1.6.6/1.6.7 的 `_cceua`。底层私有算法接口按版本限制；升级必须重新验证。

## 配置与授权

以下是配置结构示意，不是实际运行授权。使用已有 `HydroAgent(config_override=..., workspace=...)`，不需要改 Web UI。`defaults` 指定资料、率定/测试期、预热，`paths` 指定本机数据路径。执行器科学快照不复制 LLM 凭据。

```python
checkpoint_experiment = {
    "enabled": True,
    "grant_id": "YOUR-EXPLICITLY-AUTHORIZED-GRANT",
    "basin_ids": ["AUTHORIZED-BASIN"],
    "model_name": "xaj_mz",
    "arm": "A",  # B0 同一执行器，仅允许 continue/stop
    "max_studies": 1,
    "search_budget_calls": 10000,  # 示例，需实际授权
    "first_segment_calls": 2000,
    "wall_budget_seconds": 7200,  # 示例；包括加载、决策和最终评价，总截止不续期
    "auxiliary_budget_calls": 10,  # 示例；其中2次预留最终率定/测试评价
    "sceua": {"ngs": 5, "kstop": 10, "peps": 0.01,
              "pcento": 0.1, "random_seed": 1234},
}
```

研究模式只向 Agent 开放检查点科学工具和有限只读/资料检查工具，防止绕过账本调用旧率定、代码执行或动态工具。部署账本限制 `max_studies`，失败启动也消耗一个槽位，不能通过重复 start 获得无限预算。改变授权配置须使用另行授权的 grant_id。

## Agent 监管

`start_calibration_study(basin_id)` → `inspect_calibration_study(study_id)` → `advance_calibration_study(...)` / `probe_calibration_study(...)` → 最后 `finalize_calibration_study(study_id)`。

每次工具操作在独立子进程执行，进程之间恢复完整优化状态，不是重新随机初始化。重新加载数据产生的时间开销需要计入墙钟，不能把等调用优势直接称为更快。一个流域保持同一 Agent 会话；压缩上下文后重新注入结构化历史，全部已提交决策和实际结果存在流域档案中。重开会话可先 inspect 原 study_id，不创建新预算。

## 调用和检查点

一次 search 是一个流域、一组参数、包含固定预热的一次 `simulate()` 入口。初始化、反射、收缩和随机尝试都计数，模型报错仍计数；SPOTPY postprocessing 计数另存，排序/复用缓存不计新模型调用。probe/final 单独计账，不能称等全部模型调用。

分段 call_limit 是软目标：在一次完整 CCE 更新后暂停，最多超出目标2次调用。总 search 上限逐次检查，绝不超支。状态包含初始化进度、活动复合体和单纯形更新进度、种群/评分、停止历史、内部计数和 NumPy/Python RNG。全局预算中断未完成的 CCE 不再续跑，但全部已完成候选参与历史冠军选择。

continue 不重置任何配置。warm_restart 可改内层范围/设置，并保留 `keep_count` 个合法、不重复、兼顾成绩和距离的历史 search 候选，再随机补点；补点评价包含在本段/总额度。缓存评分仅在模型/数据指纹一致时复用。cold_restart 全量初始化。stop 冻结搜索；测试仅在 finalize 后可见，不能反馈下一轮。

## 输出和失败

所有新文件位于 workspace/result/checkpoint_studies/<study_id>/；授权槽位位于 workspace/result/checkpoint_grants/<grant_id>/。session.json 原子保存状态，calls.jsonl 每次开始/完成/失败均落盘，summary.json 提供精简证据，pending_decision.json 记录先提交后执行的真实决定。独立测试输出 final.json 和 final_*_q.npy；不存在 final.json 不等于科学完成。

跨进程锁防止双重推进，stale checkpoint 拒绝。进程异常中断留下锁或 pending 意图、账本超过旧检查点时拒绝自动重放；先离线核查实际调用/结果再恢复。inspect 是只读，即使待核对仍可读取账本。代码/数据变化拒绝旧状态复用。

范围缩窄不证明参数后验或全局最优。当前水文摘要包括率定 NSE/PBIAS、流量分位数、洪峰窗口和退水段；日期可核验时提供逐月 PBIAS。这些诊断不等于完整闭合水量平衡或全局敏感性。拟议的500调用改善窗口、5%逐维宽度及3%整体分散度是开发判据，需要开发/确认分离，不能宣称标准阈值。

## 验证范围

执行 `.venv/Scripts/python.exe -X utf8 -m unittest discover -s test -p test_checkpoint_experiment.py -v`。覆盖原生候选序列一致性、中途保存/恢复、总调用硬上限、暖启动复用、异常计账、禁止重放、冻结后测试、授权槽位和记忆恢复。模型集成覆盖真实 XAJ 加合成输入，以及真实 UnifiedCalibrator 加合成数据加载器；不代表已完成真实 CAMELS 或付费 LLM 实验。

设置变更目前通过 warm_restart/cold_restart 生效，continue 不允许边跑边改设置。暖启动保留历史点并均匀随机补点；尚未实现局部扰动混合采样。使用相同执行器运行各实验组，并同时报告实际调用和墙钟时间。

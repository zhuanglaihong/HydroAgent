---
name: XAJ Evidence-Based Expert Calibration
description: 根据率定水量偏差、洪峰和退水观测提出可检验的 XAJ-mz 参数范围试验。
keywords: [水量平衡, 水文诊断, 退水, 洪峰, 参数范围, xaj_mz, 专家率定]
tools: [inspect_calibration_study, probe_calibration_study, advance_calibration_study]
when_to_use: 检查点实验中需要根据过程观测调整参数范围时，完整读取本文件及有关参考。
---

从 D:/project/iHeadWater/HydroAgent/skills/adaptive-calibration 迁移专家诊断原理与论文表，已适配当前 Python ReAct 检查点接口。旧 DSH/direct/hydrosystem 合同不适用于此路径。先完整读取 [参数与症状参考](references/xaj-camels-us.md)，引用论文时读取 [证据表](references/evidence.md)。

当前工具只用率定期做决策。inspect 的 hydrological_diagnostics 对应保存的历史冠军，必须核对 candidate_call_id；不是自动对应当前阶段最佳。可见量包括 NSE/PBIAS、低流分位数、日高流窗口、退水代理；日期可靠时有月偏差。未返回的年/季节量、ET、储水及独立洪水事件不得假装已观测。P总量与出口偏差不构成 P−ET−ΔS 闭合检验。

PBIAS=100×(ΣQsim−ΣQobs)/ΣQobs，正值表示模拟偏多。先核单位、日期、预热和候选身份，再提出一条主假设及至少一个竞争解释：

| 观测症状 | 参数组候选与检验 |
|---|---|
| 长期出口流量偏多/偏少 | 先查驱动/状态；考虑 K/C 与 UM/LM/DM。PET×K需求方向明确，但实际流量方向须试验，不能机械加减K |
| 干后起涨/季节偏差 | 考虑容量 UM/LM/DM、B/IM；需对应事件序列，缺证据时不声称已诊断 |
| 洪量较接近但日峰过尖/过宽或错时 | 查日期与窗口；比较 SM/EX/KI/KG 分流与 A/THETA 快速汇流解释，多窗口复核 |
| 无雨退水斜率错 | 比较 CI/CG 释放与 KI/KG 补给；斜率对而水平错优先查供给/状态，不把退水直接当CG观测 |

本地模型机制须与实际 hydromodel 版本核对：WM=UM+LM+DM是派生量；CI/CG较大表示线性库记忆较长；KI/KG可能联合缩放；A/THETA只涉及xaj_mz快速分量，不用xaj的CS/L替代。论文支持过程诊断思路，不证明当前流域参数方向。

允许有依据、可回退的参数组范围探索，不必先证明因果；保存旧范围、完整冠军、竞争解释与反证，范围不得超出固定 outer_ranges。改变范围必须 warm_restart/cold_restart，不能标成continue。探针提交完整合法物理参数向量，单次只计算率定期，消耗辅助额度；不晋升搜索冠军，不提供自动过程细节，不声称观察了未返回量。局部扰动不是全局敏感性。

提交前写清来源和值、拟调整组、物理方向、下一阶段预期与反证、预算及回退。不能平均优秀向量的各列拼装“好解”。诊断改善不取代固定RMSE冠军规则；测试在冻结后finalize，不能反馈决策。与检查点决策skill共同使用，允许无修改续跑。

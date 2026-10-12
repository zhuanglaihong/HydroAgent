# 论文与本地实现证据表

此 Skill 把水文学研究整理为 Agent 可执行的流程。**论文支持的是下表指出的原理**，不自动证明某个流域的参数方向、固定百分比阈值或 Agent 一定胜过基线。研究报告引用时，应把论文链接放在具体主张旁；本项目的试验规则须另行标明。

| 编号 | 原始论文/权威资料 | 具体支持什么；不支持什么 |
|---|---|---|
| **P1** | [Addor 等，2017，CAMELS 数据集，HESS](https://hess.copernicus.org/articles/21/5293/2017/) | 671 个美国流域的属性，与逐日气象驱动和径流资料配套。支持记录流域身份、驱动和日尺度。论文不保证固定 XAJ 适合所有流域。 |
| **P2** | [Yilmaz、Gupta、Wagener，2008，基于过程的水文模型诊断，WRR](https://doi.org/10.1029/2007WR006716) | 用不同水文特征分别观察总水量、垂向分流及时间再分配，支持“先症状、再机制”的诊断顺序。它没有验证本 Skill 的 XAJ 参数表是万能规则。 |
| **P3** | [Gupta 等，2009，NSE/MSE 分解，Journal of Hydrology](https://doi.org/10.1016/j.jhydrol.2009.08.003) | NSE 的偏差、波动与相关成分可能互相补偿，所以需查看水量与过程特征。单个 NSE 无法指出哪一个物理过程错了。 |
| **P4** | [Duan、Sorooshian、Gupta，1994，SCE-UA 在流域率定中的应用，Journal of Hydrology](https://doi.org/10.1016/0022-1694(94)90057-4) | 搜索配置与评估预算影响优化过程，支持检查算法设置和独立搜索。论文不保证单次运行找到严格全局最优，也不给通用随机种子数。 |
| **P5** | [Li、Lu，2012，新安江模型时间尺度分步优化，JSCE](https://doi.org/10.2208/jscejhe.68.I_145) | 直接展示 XAJ 可按时间尺度敏感性分步率定。论文采用 **SCEM-UA**，本 Skill 只迁移分组思想，不把其链收敛规则当作 SCE-UA 规则，也不照搬参数名。 |
| **P6** | [Lu、Li，2014，新安江参数的时间尺度敏感性，Hydrological Research Letters](https://doi.org/10.3178/hrl.8.51) | Morris 分析显示年、月、日尺度敏感性会变，参数有交互。支持针对当前诊断指标做敏感性检查；不能给每个流域一个永久有效的排名。 |
| **P7** | [Zhao，1992，The Xinanjiang model applied in China，Journal of Hydrology](https://doi.org/10.1016/0022-1694(92)90096-E) | XAJ 土壤蓄水、产流与多水源概念基础。本地 `K`、`CS/L`、`A/THETA` 等精确公式要从代码 [L1] 核对，不能仅据原始论文推断。 |
| **P8** | [Pianosi 等，2016，环境模型敏感性分析综述](https://doi.org/10.1016/j.envsoft.2016.02.008)；[Herman 等，2013，Morris 用于水文模型，HESS](https://hess.copernicus.org/articles/17/2893/2013/) | 敏感性取决于问题、参数范围、抽样设计及交互；Morris 可做相对节省评估次数的筛查。局部双向扰动只是小试验，优化轨迹不是全局敏感性样本。 |
| **P9** | [Mizukami 等，2019，高流量率定指标选择，HESS](https://hess.copernicus.org/articles/23/2601/2019/) | 日尺度 NSE 率定不保证年最大流量模拟好；高流量目标又可能牺牲其他表现。支持报告高流量结果，但没有统一“峰值合格线”。 |
| **P10** | [Klemeš，1986，水文模型业务检验，Hydrological Sciences Journal](https://doi.org/10.1080/02626668609491024) | 检验应与未来使用场景匹配；分样与更困难的跨气候检验回答不同问题。反复用于选择轮次的验证集应视为开发资料，锁定后独立测试是由此引申的本项目实验规则。 |
| **P11** | [Boyle 等，2000，人工与自动率定结合，WRR](https://doi.org/10.1029/2000WR900207)；[Hogue 等，2000，河流预报模型分步自动率定，Journal of Hydrometeorology](https://journals.ametsoc.org/view/journals/hydr/1/6/1525-7541_2000_001_0524_amacsf_2_0_co_2.xml) | 专家关注的多个过程可以转为显式准则或分步自动流程，支持“观察—假设—试验—决定”。论文未证明大模型 Agent 会优于调好的 SCE-UA；那正是本项目待检验的问题。 |
| **P12** | [Moriasi 等，2015，水文模型性能指标与评价标准，ASABE](https://doi.org/10.13031/trans.58.10715)；[美国陆军工程兵团 HEC-HMS 指标说明](https://www.hec.usace.army.mil/confluence/hmsdocs/hmstrm/calibration/calibration-summary-statistics) | NSE、PBIAS、图形诊断常联合使用；建议阈值有研究对象与时间尺度背景，不是 CAMELS-US XAJ 的万能合格线。HEC-HMS 将 PBIAS 正值定义为模拟偏大，而部分文献符号相反，故必须同时给公式。 |
| **P13** | [Mizukami 等，2016，mizuRoute 河道汇流模型，Geoscientific Model Development](https://gmd.copernicus.org/articles/9/2223/2016/) | 为 Gamma 类单位线汇流提供来源背景。此 Skill 对 `xaj_mz` 的 `A/THETA` 偏移、有限核长、归一化及只汇快速分量的描述，均以本地实现 [L1] 为准。 |


## 当前本地执行依据

当前接口由 hydroagent/research/backend.py、session.py、diagnostics.py、evidence.py 和 tools/checkpoint_calibration.py 定义。模型方程须依据实际导入的 hydromodel 源码核对，不能把旧项目路径当成当前事实。旧 L2/L3 合同不适用；论文表保留原来源，迁移过程未重新检索论文。阈值、暖启动、预算规则属于本项目设计。

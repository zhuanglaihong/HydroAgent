---
name: spotpy MCMC 不确定性分析
description: 使用 spotpy 库进行水文模型参数的 MCMC（马尔可夫链蒙特卡洛）不确定性分析。支持 Metropolis-Hastings、DREAM、SCE-UA 等多种采样算法，可生成参数后验分布、迹线图、预测区间等可视化结果。适用于 GR4J、XAJ 等概念性水文模型的参数不确定性量化。
keywords: [spotpy, MCMC, 不确定性分析, 参数估计, 贝叶斯推断, 水文模型, GR4J, DREAM, Metropolis-Hastings, 后验分布]
tools: [spotpy_mcmc_uncertainty]
when_to_use: 需要对水文模型参数进行不确定性量化、获取参数后验分布、生成预测区间或比较不同采样算法性能时使用
---

## spotpy MCMC 不确定性分析 工作流

### 适用场景

- 水文模型（GR4J、XAJ、HBV 等）参数的不确定性量化
- 贝叶斯框架下的参数后验分布估计
- 生成径流预测的置信区间
- 评估参数敏感性和可识别性
- 比较不同采样算法的收敛效率

### 核心组件

#### 1. 参数定义（`spotpy.parameter`）

| 分布类型 | 类名 | 用途 |
|---------|------|------|
| 均匀分布 | `Uniform` | 无先验信息时使用 |
| 正态分布 | `Normal` | 有参数先验均值和方差时使用 |
| 对数正态分布 | `LogNormal` | 参数必须为正且呈对数分布时使用 |
| 三角分布 | `Triangular` | 有最可能值估计时使用 |

#### 2. 采样算法（`spotpy.algorithms`）

| 算法 | 类名 | 特点 | 适用场景 |
|-----|------|------|---------|
| Metropolis-Hastings | `mc` | 单链随机游走 | 简单模型，快速测试 |
| DREAM | `dream` | 多链自适应，自动调整提议分布 | 高维参数，复杂后验 |
| SCE-UA | `sceua` | 全局优化 + 不确定性 | 需要优化和不确定性兼顾 |
| ROPE | `rope` | 拒绝采样 | 计算资源充足时 |
| ABC | `abc` | 近似贝叶斯计算 | 似然函数难以定义时 |

#### 3. 目标函数（`spotpy.objectivefunctions`）

- `nashsutcliffe`：纳什效率系数（推荐用于径流模拟）
- `rmse`：均方根误差
- `mae`：平均绝对误差
- `kge`：Kling-Gupta 效率
- `log_p`：自定义对数似然函数

### 标准工作流

#### 步骤 1：定义参数空间
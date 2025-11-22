# HydroAgent 实验设计

## 实验1：标准流域验证
● 目标：验证智能体能否自主完成一个标准流域的率定并达到基准精度。
● 设计：
  ○ 数据：选择 CAMELS_US 中数据质量极高的流域（例如 01013500）。
  ○ 指令："率定流域 01013500，使用标准 XAJ 模型。"
  ○ 预期结果：Agent 自动运行 SCE-UA，最终 NSE 系数应 > 0.8 (或接近文献中的基准值)，并画出径流拟合图。

## 实验2：Agent 通用性与鲁棒性测试 (Versatility & Robustness)
目标：验证系统处理自然语言中“信息完备度”不同的情况的能力，证明系统能灵活应对各种输入，最终都能生成合法的 config 并执行。
● 设计逻辑： 设计三组不同信息密度的指令，观察 Agent 的配置补全能力。
  ○ 场景 A（全信息，Ideal Case）：
    ■ 输入："使用 SCE-UA 算法，设置 rep=5000, ngs=1000，率定 CAMELS_US 的 01013500 流域，时间 1990-2000。"
    ■ 预期行为：Agent 直接映射参数到 config.yaml，无需额外推理。
  ○ 场景 B（缺省信息，Inference Case）：
    ■ 输入："帮我率定流域 01013500。"（缺算法、缺时间、缺数据集类型）。
    ■ 预期行为：
      ● Agent 识别出 ID 格式属于 CAMELS_US。
      ● Agent 自动检索 RAG，填入默认算法 SCE_UA 和默认参数（如 rep: 1000）。
      ● Agent 自动设定默认的时间范围（如数据的前10年）。
      ● 成功标志：生成的 config.yaml 是完整的且能运行。
  ○ 场景 C（模糊/自定义信息，Custom Case）：
    ■ 输入："用我 D 盘 my_data 文件夹里的数据跑一下模型。"
    ■ 预期行为：
      ● Agent 识别路径，配置 data_source_type: selfmadehydrodataset。
      ● Agent 检查文件夹结构，自动推断 dataset_name。
● 验证指标：三种场景下生成的 config.yaml 的语法正确率（能否被 hydromodel 加载）和任务执行成功率。

## 实验 3：参数自适应优化能力 (Adaptive Parameter Refinement)
目标：验证系统具备"科学家"的思维，即：观察结果 -> 提出假设（调整范围） -> 重新实验。系统需要在保持 hydromodel 框架不变的前提下，通过操作 param_range.yaml 来提升效果。
● 设计逻辑： 构建一个“两阶段”率定实验。
  ○ 步骤 1 (粗率定)：
    ■ 输入：系统使用默认的宽泛参数范围文件 param_range_default.yaml 进行第一轮率定（低迭代次数，如 rep=500）。
    ■ 分析：Hydro-Analyst Agent 分析结果文件 01013500_sceua.csv 或 calibration_results.json。
    ■ 触发条件：发现某个敏感参数（如 K 或 SM）的最优值收敛到了参数范围的边界（Boundary Effect），或者分布过于散乱。
  ○ 步骤 2 (范围调整与精率定)：
    ■ 动作：Configurator Agent 基于分析结果，生成一个新的参数范围文件 param_range_refined.yaml。
      ● 策略：将范围中心移动到第一轮的最优值附近，并缩小/扩大范围。
    ■ 配置更新：生成新的 config_round2.yaml，其中 training_cfgs 增加或修改参数指向新的范围文件（注：hydromodel 的 save_config=True 会生成默认范围文件，Agent 需要学会覆盖或修改它）。
    ■ 执行：重新运行率定。
● 验证指标：对比 Round 1 和 Round 2 的 NSE 提升值。证明 Agent 懂得"缩小搜索空间"来获得更好的结果。

## 实验 4：代码生成与工具扩展能力 (Code Generation / Tool Expansion)
目标：验证当用户需求超出 hydromodel 现有功能（Out-of-Distribution Tasks）时，系统能否通过 Developer Agent 编写代码来解决问题，而不是报错。
● 设计逻辑： 提出一个 hydromodel 原生不支持的需求。
  ○ 场景设定：
    ■ hydromodel 原生支持 NSE, KGE, RMSE，也支持绘制标准的时间序列图。
    ■ 用户输入："率定完成后，请帮我计算流域的 径流系数 (Runoff Coefficient)，并画一张 流路历时曲线 (Flow Duration Curve, FDC)。"
  ○ 系统反应：
    ⅰ. 识别：系统检索文档，发现 hydromodel 的评估指标列表里没有 "Runoff Coefficient"，可视化脚本里也没有 "FDC"。
    ⅱ. 代码生成 (Developer Agent)：
      ● Agent 编写一个独立的 Python 脚本 calc_runoff_coef.py，读取 results/.../xaj_mz_evaluation_results.nc 或输出的 CSV。
      ● Agent 编写绘图脚本 plot_fdc.py，使用 matplotlib 绘制 FDC。
    ⅲ. 执行：Simulator Agent 在标准流程结束后，额外调用这两个脚本。
● 验证指标：
  ○ 生成的 Python 代码是否无语法错误。
  ○ 最终是否输出了正确的径流系数值和 FDC 图片。

## 实验 5：稳定性/信任度验证 
● 目标：验证 Agent 和优化算法的鲁棒性（随机种子影响）。
● 设计：
  ○ 内容：连续发送 10 次相同的率定指令，或者在一个指令中要求重复运行 10 次（使用不同的随机种子）。
  ○ 预期结果：计算 10 次结果的 NSE 标准差。证明系统是稳定的，不会因为 Agent 的配置错误导致运行崩溃（100% 成功率），且算法结果具有统计稳定性。
# Tool Error Knowledge Base

每个工具的常见报错 -> 诊断 -> 恢复建议。
由 pipeline.py 的错误处理模块自动查询，也注入 Agent 的故障诊断上下文。

---

## validate_basin

### E01: FileNotFoundError - 数据文件不存在
症状：`No such file or directory` / `data_path` 下找不到 forcing 或 streamflow 文件
诊断：数据集未下载 / basin_id 格式错误 / DATASET_DIR 环境变量配置错误
恢复：1) 检查 DATASET_DIR 是否指向正确的 CAMELS 数据目录
      2) 确认 basin_id 为 8 位数字（如 12025000，不足补零）
      3) 如数据不存在，运行 `python -m hydroclaw.utils.setup_wizard` 重新配置

### E02: DateRangeError - 可用时间范围不足
症状：`available_years < 10` / `insufficient data`
诊断：该流域数据记录不完整或所选时间段超出数据范围
恢复：缩短 train_period 或 test_period；或换数据记录更长的流域

### E03: ValidationError - 数据质量检查失败
症状：NaN 比例超限 / 流量为负值
诊断：原始数据存在缺测或异常值
恢复：跳过该流域（skip），记录为 DATA_QUALITY 失败类型

---

## calibrate_model

### E01: ConvergenceError - 优化不收敛
症状：`NSE < 0` / `max iterations reached` / `SCE-UA failed`
诊断：参数范围设置过窄 / 模型不适配该流域气候特征 / 初始种群全落在不可行域
恢复：1) 扩大参数范围（尤其是 x1/SM 等容量参数）
      2) 考虑换模型（GR4J -> XAJ，或反之）
      3) 增大 ngs（种群大小）至 10

### E02: MemoryError - 内存不足
症状：`process killed` / `MemoryError` / OOM
诊断：ngs 设置过大或流域数据量过大
恢复：减小 algorithm_params 中的 ngs（默认 7 -> 5）

### E03: DataAlignmentError - 时间序列长度不匹配
症状：`forcing/streamflow length mismatch` / shape 不一致
诊断：forcing 数据与 streamflow 数据的时间范围不完全对齐
恢复：重新运行 validate_basin 确认数据完整性；尝试缩小 train_period

### E04: ParamRangeFileError - 参数范围文件格式错误
症状：`param_range_file` 解析失败 / YAML 格式错误
诊断：手动修改了参数范围文件导致格式损坏
恢复：删除 param_range_file，使用默认参数范围重新率定

### E05: TimeoutError - 率定超时
症状：rate limiting / wall time exceeded
诊断：任务队列堆积或 API 限速
恢复：等待 30 秒后 retry；检查并发任务数量

---

## evaluate_model

### E01: CalibrationDirNotFound - 率定目录不存在
症状：`calibration_dir does not exist` / `No such file or directory`
诊断：calibrate_model 未成功完成 / output_var 变量传递错误（Pipeline 模式下 $cal.calibration_dir 解析失败）
恢复：确认 calibrate_model 已成功完成；检查 Pipeline 计划中 output_var 是否正确设置

### E02: MetricsFileNotFound - 结果文件不存在
症状：`basins_metrics.csv not found` / `eval_results.json not found`
诊断：evaluate_model 内部写文件失败（磁盘满 / 权限不足）
恢复：检查磁盘空间；重新运行 evaluate_model

### E03: PeriodMismatch - 评估期超出数据范围
症状：`eval_period out of data range`
诊断：指定的 eval_period 超出了流域数据的时间范围
恢复：使用 eval_period=None（自动从率定配置读取测试期）

---

## llm_calibrate

### E01: NSEStagnation - NSE 连续多轮无改善
症状：连续 3 轮 best_nse 不变 / nse_history 全部相同
诊断：LLM 提议的参数范围调整未能突破当前最优；可能参数已收敛或模型存在可识别性问题
恢复：停止迭代，以当前最优参数输出结果；在报告中标注 convergence_stagnant=True

### E02: BoundaryLoop - 参数持续触边界
症状：连续 2 轮以上某参数触上界或下界
诊断：真实最优参数超出了物理合理范围，或模型结构不适配该流域
恢复：扩大边界至物理极限后再试一轮；若仍触边界，换模型

### E03: LLMParseError - LLM 返回格式无法解析
症状：JSON 解析失败 / 参数名不在已知列表
诊断：LLM 返回了非 JSON 格式或参数名幻觉
恢复：重试一次（retry），在 prompt 中强调"只返回 JSON"

---

## run_code

### E01: SyntaxError - 代码语法错误
症状：`SyntaxError` / `IndentationError`
诊断：generate_code 生成的代码有语法问题
恢复：将错误信息反馈给 generate_code 重新生成；不要超过 2 次重试

### E02: ImportError - 缺少依赖包
症状：`ModuleNotFoundError: No module named '...'`
诊断：代码依赖了未安装的包
恢复：先调用 install_package 安装（需用户授权），再重新运行

### E03: RuntimeError - 执行超时或资源耗尽
症状：执行时间超过 30 秒 / 内存耗尽
诊断：代码存在死循环或数据量过大
恢复：abort，向用户报告；不要自动 retry

---

## generate_code

### E01: HallucinatedAPI - 使用了不存在的 API
症状：生成的代码调用了 hydroclaw 或 hydromodel 中不存在的函数
诊断：LLM 对包 API 的记忆与实际版本不符
恢复：在 prompt 中补充实际 API 签名（从 llms.txt 或 docstring 获取），重新生成

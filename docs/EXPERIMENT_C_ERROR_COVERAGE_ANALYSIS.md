# 实验C错误场景覆盖分析

**Date**: 2026-01-05
**Purpose**: 分析当前实验C的错误场景覆盖率，设计更全面的测试

## 当前实验C错误场景覆盖

### 已覆盖场景 (15个)

| 类别 | 测试场景 | 错误分类 | 数量 |
|------|---------|---------|------|
| 数据验证失败 | 不存在的流域、时间范围错误、部分流域无效 | data_validation | 3 |
| 工具执行失败 | 非法参数、多个非法参数、无效路径 | data_validation | 3 |
| 工具链中断 | 第1步失败后续跳过 | data_validation | 3 |
| 参数异常 | 时间倒序、负数重复次数、NSE超出范围 | data_validation | 3 |
| 输入缺失 | 缺少模型名称、缺少信息 | data_validation | 3 |

**问题**：当前实验C主要测试 **data_validation** 类错误，未覆盖其他8个错误类别。

---

## 9个错误分类 vs 当前覆盖率

| 错误分类 | 典型场景 | 当前覆盖 | 缺失场景 |
|---------|---------|---------|---------|
| **1. network** | 网络超时、连接失败 | ❌ 无 | API调用超时、数据下载失败 |
| **2. llm_api** | LLM API超时、quota exhausted | ❌ 无 | API key无效、免费额度耗尽 |
| **3. code** | NameError, SyntaxError | ❌ 无 | 生成的Python代码错误 |
| **4. configuration** | 配置文件错误、API key缺失 | ❌ 无 | config.py配置错误 |
| **5. data** | 数据文件损坏、NetCDF错误 | ❌ 无 | CAMELS数据文件损坏 |
| **6. data_validation** | 流域不存在、参数非法 | ✅ 15个 | - |
| **7. dependency** | hydromodel未安装 | ❌ 无 | 缺少必要的Python包 |
| **8. numerical** | 率定过程NaN、数值不稳定 | ❌ 无 | SCE-UA算法数值溢出 |
| **9. runtime** | hydromodel内部RuntimeError | ❌ 无 | 模型执行异常 |

**覆盖率**: 1/9 = 11.1%

---

## 扩展的错误场景设计（新增27个）

### 1. Network Errors (网络错误) - 3个

**目的**: 测试网络连接超时、数据下载失败时的处理

| 场景 | 模拟方法 | 预期行为 |
|------|---------|---------|
| API请求超时 | 设置极短的timeout | 识别为network错误，建议检查网络 |
| CAMELS数据下载失败 | 断开网络或删除缓存 | 识别为network/data错误，建议重新下载 |
| 流域数据访问超时 | 模拟大流域数据读取超时 | 识别为network错误，建议增加timeout |

**测试查询**:
```python
# 1. 模拟API超时（通过设置短timeout）
"率定GR4J模型流域01013500"  # + timeout=1s in llm_interface

# 2. 模拟数据下载失败（删除CAMELS缓存）
"验证流域01013500数据，率定GR4J模型"  # + 删除 ~/.cache/camels_us

# 3. 模拟数据访问超时（大流域批量处理）
"批量率定100个流域（01013500到01013599）"  # 数据量过大导致超时
```

---

### 2. LLM API Errors (LLM API错误) - 3个

**目的**: 测试LLM API失败时的容错和报告生成

| 场景 | 模拟方法 | 预期行为 |
|------|---------|---------|
| API key无效 | 使用错误的API key | 识别为llm_api错误，建议检查API key |
| Quota耗尽 | 模拟API返回quota error | 识别为llm_api错误，建议检查配额 |
| LLM服务不可用 | 模拟API返回503 | 识别为llm_api错误，建议稍后重试 |

**测试查询**:
```python
# 1. API key无效
"率定XAJ模型流域11532500"  # + invalid API key in config

# 2. Quota耗尽（模拟）
"重复率定GR4J模型流域01013500共10次"  # 大量API调用后quota耗尽

# 3. LLM服务不可用（模拟）
"生成Python代码计算流域01013500的径流系数"  # + mock 503 error
```

---

### 3. Code Errors (代码错误) - 3个

**目的**: 测试生成的Python代码错误时的处理

| 场景 | 模拟方法 | 预期行为 |
|------|---------|---------|
| 生成代码有NameError | LLM生成的代码引用未定义变量 | 识别为code错误，显示traceback |
| 生成代码有SyntaxError | LLM生成的代码语法错误 | 识别为code错误，建议修复语法 |
| 生成代码有ImportError | LLM生成代码导入不存在的模块 | 识别为code/dependency错误 |

**测试查询**:
```python
# 1. NameError (通过复杂的自定义分析触发)
"率定GR4J模型流域01013500，完成后生成复杂的水文过程分析代码，包括5个自定义指标"

# 2. SyntaxError (通过模糊的分析需求触发)
"帮我生成一个Python脚本，分析流域的水文响应特征，使用各种复杂的if-else逻辑"

# 3. ImportError (通过要求不存在的库触发)
"生成Python代码使用pandas、numpy、seaborn和matplotlib计算流域水文指标"
```

---

### 4. Configuration Errors (配置错误) - 3个

**目的**: 测试配置文件错误时的处理

| 场景 | 模拟方法 | 预期行为 |
|------|---------|---------|
| DATASET_DIR路径错误 | config.py中路径不存在 | 识别为configuration错误，建议检查路径 |
| API_KEY缺失 | definitions_private.py缺少API_KEY | 识别为configuration错误，建议配置 |
| 配置项类型错误 | DEFAULT_WARMUP_DAYS = "365" (字符串) | 识别为configuration错误，建议修正类型 |

**测试查询**:
```python
# 1. DATASET_DIR路径错误
"验证流域01013500的数据质量"  # + config.DATASET_DIR = "/invalid/path"

# 2. API_KEY缺失
"率定GR4J模型流域01013500"  # + OPENAI_API_KEY = None

# 3. 配置项类型错误
"率定GR4J模型流域01013500，warmup期365天"  # + DEFAULT_WARMUP_DAYS = "365"
```

---

### 5. Data File Errors (数据文件错误) - 3个

**目的**: 测试数据文件损坏或格式错误时的处理

| 场景 | 模拟方法 | 预期行为 |
|------|---------|---------|
| NetCDF文件损坏 | 修改CAMELS数据文件为非法格式 | 识别为data错误，建议重新下载 |
| 数据文件缺失 | 删除特定流域的数据文件 | 识别为data错误，建议检查数据完整性 |
| HDF读取错误 | 模拟HDF5库读取错误 | 识别为data错误，建议检查HDF5库 |

**测试查询**:
```python
# 1. NetCDF文件损坏
"验证流域01013500数据，率定GR4J模型"  # + 损坏camels_us_timeseries.nc

# 2. 数据文件缺失
"批量率定流域01013500,11532500,02070000"  # + 删除某个流域数据

# 3. HDF读取错误（难以模拟，通过日志识别）
"率定XAJ模型流域01013500"  # + 检查是否捕获HDF错误
```

---

### 6. Dependency Errors (依赖缺失) - 3个

**目的**: 测试缺少Python依赖时的处理

| 场景 | 模拟方法 | 预期行为 |
|------|---------|---------|
| hydromodel未安装 | 卸载hydromodel | 识别为dependency错误，建议pip install |
| spotpy缺失 | 卸载spotpy (SCE-UA依赖) | 识别为dependency错误，建议安装spotpy |
| pandas版本不兼容 | 使用旧版pandas | 识别为dependency错误，建议升级 |

**测试查询**:
```python
# 1. hydromodel未安装
"率定GR4J模型流域01013500"  # + pip uninstall hydromodel

# 2. spotpy缺失
"率定GR4J模型流域01013500，使用SCE-UA算法"  # + pip uninstall spotpy

# 3. pandas版本不兼容
"验证流域01013500数据，生成CSV报告"  # + pandas < 1.0
```

---

### 7. Numerical Errors (数值计算错误) - 3个

**目的**: 测试率定过程中数值不稳定时的处理

| 场景 | 模拟方法 | 预期行为 |
|------|---------|---------|
| 参数范围导致NaN | 极端的参数范围（如[0, 1e10]） | 识别为numerical错误，建议调整范围 |
| 算法迭代发散 | 迭代次数过多导致数值溢出 | 识别为numerical错误，建议减少迭代 |
| 目标函数NaN | 数据问题导致NSE计算NaN | 识别为numerical错误，建议检查数据 |

**测试查询**:
```python
# 1. 参数范围导致NaN
"率定GR4J模型流域01013500，参数x1范围设为[0, 100000]"  # 极端范围

# 2. 算法迭代发散
"率定XAJ模型流域01013500，迭代50000轮"  # 迭代次数过多

# 3. 目标函数NaN (通过数据问题触发)
"率定GR4J模型流域01013500，训练期1990-01-01到1990-01-31"  # 时间太短
```

---

### 8. Runtime Errors (运行时错误) - 3个

**目的**: 测试hydromodel内部RuntimeError时的处理

| 场景 | 模拟方法 | 预期行为 |
|------|---------|---------|
| 模型计算异常 | 模型内部assert失败 | 识别为runtime错误，显示traceback |
| 算法初始化失败 | 算法参数冲突导致失败 | 识别为runtime错误，建议调整参数 |
| 内存溢出 | 批量处理过多流域 | 识别为runtime错误，建议减少批量 |

**测试查询**:
```python
# 1. 模型计算异常
"率定GR4J模型流域01013500，warmup期0天"  # warmup=0可能触发assert

# 2. 算法初始化失败
"率定GR4J模型流域01013500，SCE-UA算法ngs=1"  # ngs太小导致失败

# 3. 内存溢出
"批量率定所有CAMELS流域（671个）"  # 内存不足
```

---

### 9. Data Validation Errors (数据验证错误) - 3个

**目的**: 保留原有的data_validation测试，确保覆盖全面

**保留原有测试**:
- 不存在的流域
- 时间范围错误
- 参数边界检查

---

## 扩展后的实验C总体设计

### 错误场景矩阵 (9类 × 3个 = 27个新场景 + 15个原有 = 42个)

| 错误分类 | 场景数 | 典型示例 | 验证指标 |
|---------|-------|---------|---------|
| network | 3 | API超时、数据下载失败 | 错误识别率、恢复建议 |
| llm_api | 3 | API key无效、quota耗尽 | 错误提示清晰度 |
| code | 3 | NameError、SyntaxError | 错误定位准确性 |
| configuration | 3 | 路径错误、配置缺失 | 建议可操作性 |
| data | 3 | NetCDF损坏、文件缺失 | 错误分类准确性 |
| dependency | 3 | hydromodel未安装 | 安装建议清晰度 |
| numerical | 3 | NaN、数值溢出 | 参数调整建议 |
| runtime | 3 | RuntimeError、内存溢出 | 错误传播控制 |
| data_validation | 15 | 流域不存在、参数非法 | 容错率、安全退出 |

---

## 实验C增强版指标设计

### 1. 错误分类准确率 (Error Classification Accuracy)

```python
def calculate_classification_accuracy(results):
    """计算错误分类的准确率"""
    correct = 0
    total = 0

    for r in results:
        if not r.get("success"):
            expected_category = r.get("expected_error_category")
            actual_category = r.get("error_category")

            if expected_category:
                total += 1
                if expected_category == actual_category:
                    correct += 1

    return correct / total if total > 0 else 0
```

### 2. 错误恢复建议质量 (Recovery Suggestion Quality)

```python
def evaluate_suggestion_quality(results):
    """评估错误恢复建议的质量"""
    # 检查建议是否包含：
    # 1. 具体的错误原因
    # 2. 可操作的解决步骤
    # 3. 相关的配置/参数提示

    quality_score = 0
    error_count = 0

    for r in results:
        if not r.get("success"):
            error_count += 1
            analysis = r.get("analysis", {})

            # 检查是否有详细的错误分析
            if "error_category" in r and "error_type" in r:
                quality_score += 0.3

            # 检查是否有可操作的建议
            if "suggestions" in analysis and len(analysis["suggestions"]) > 0:
                quality_score += 0.4

            # 检查是否生成了失败报告
            if "analysis_report.md" in str(r.get("workspace", "")):
                quality_score += 0.3

    return quality_score / error_count if error_count > 0 else 0
```

### 3. 失败报告生成率 (Failure Report Generation Rate)

```python
def calculate_report_generation_rate(results):
    """计算失败任务的报告生成率"""
    failed_with_report = 0
    failed_total = 0

    for r in results:
        if not r.get("success"):
            failed_total += 1
            workspace = Path(r.get("workspace", ""))
            if (workspace / "analysis_report.md").exists():
                failed_with_report += 1

    return failed_with_report / failed_total if failed_total > 0 else 0
```

---

## 实施建议

### Phase 1: 扩展ErrorHandler (当前已完成)
- ✅ 9个错误分类类别
- ✅ 错误原因分析
- ✅ 基础建议生成

### Phase 2: 增强错误建议 (本次改进)
- 🔧 为每个错误类别添加针对性的解决步骤
- 🔧 添加配置检查清单
- 🔧 提供相关文档链接

### Phase 3: 扩展实验C (本次改进)
- 🔧 新增27个错误场景测试
- 🔧 新增3个评估指标
- 🔧 生成完整的错误覆盖报告

### Phase 4: 自动化测试 (未来)
- 🔮 错误注入框架
- 🔮 持续集成测试
- 🔮 错误场景回归测试

---

## 预期效果

### Before (当前)
- 错误场景覆盖: 1/9 (11.1%)
- 主要测试: data_validation
- 报告生成: 部分缺失

### After (改进后)
- 错误场景覆盖: 9/9 (100%)
- 全面测试: 9个错误类别 × 3个场景
- 报告生成: 100% (所有失败任务都有报告)
- 错误分类准确率: ≥90%
- 建议质量分数: ≥0.7

---

**Last Updated**: 2026-01-05
**Status**: 🔧 Design完成，待实施

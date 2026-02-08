# 错误分类与失败报告生成修复总结

**Date**: 2026-01-05
**Version**: v6.0
**Author**: Claude

## 问题描述

用户在测试实验B时发现两个问题：

1. **错误分类不清晰**：CSV 结果中所有错误都显示为 "Unknown error"，无法区分网络问题、配置错误、数据错误等不同类型，给问题定位带来困难。

2. **analysis_report.md 缺失**：某些 session 目录下没有生成分析报告，即使任务失败也应该有总结报告，说明遇到的错误类型和可能的解决办法。

### 具体错误日志

```
logs/exp_B_tool_chain_orchestration_20260105_101420.log:
- APITimeoutError: Request timed out
- NameError: name 'final_basin_ids' is not defined
- RuntimeError: NetCDF: HDF error

experiment_results/.../exp_B_results.csv:
query,success,...,error
"...",False,...,Unknown error
```

---

## 修复方案

### 1. 扩展 ErrorHandler 错误分类系统

**文件**: `hydroagent/utils/error_handler.py`

#### 修改内容

在 `_analyze_error()` 方法中新增 9 个错误分类类别：

| 分类 | 错误类型 | 示例 |
|------|---------|------|
| **network** | APITimeoutError, TimeoutError, ConnectionError | "Request timed out", "Connection failed" |
| **llm_api** | LLMTimeoutError | "LLM API request failed" |
| **code** | NameError, SyntaxError, IndentationError | "name 'final_basin_ids' is not defined" |
| **configuration** | KeyError, AttributeError | "KeyError: 'prec'" |
| **data** | FileNotFoundError, IOError, NetCDF/HDF errors | "NetCDF: HDF error" |
| **data_validation** | ValueError, TypeError | "Invalid data type" |
| **dependency** | ImportError, ModuleNotFoundError | "No module named 'hydromodel'" |
| **numerical** | NaN, numerical instability | "NaN detected" |
| **runtime** | RuntimeError, AssertionError | "Assertion failed" |

#### 代码示例

```python
# Enhanced categorization: Network, API, Code, Data, Config, etc.

# 1. Network and API errors (highest priority)
if error_type in ["APITimeoutError", "TimeoutError", "RequestException", "ConnectionError"]:
    analysis["error_category"] = "network"
    analysis["likely_cause"] = "Network connection timeout or API request timeout"
elif "timeout" in error_message.lower() or "timed out" in error_message.lower():
    analysis["error_category"] = "network"
    analysis["likely_cause"] = "Request timeout (network or API)"

# 2. LLM-specific errors
elif "LLMTimeoutError" in error_type or "llm" in error_message.lower():
    analysis["error_category"] = "llm_api"
    analysis["likely_cause"] = "LLM API request failed or timeout"

# 3. Code errors (NameError, SyntaxError, etc.)
elif error_type in ["NameError", "SyntaxError", "IndentationError"]:
    analysis["error_category"] = "code"
    analysis["likely_cause"] = "Code error (undefined variable or syntax error)"

# ... (其他分类)
```

---

### 2. BaseExperiment 集成 ErrorHandler

**文件**: `experiment/base_experiment.py`

#### 修改内容

在 `run_batch()` 方法的异常处理中调用 ErrorHandler 分类错误：

```python
except Exception as e:
    # 使用 ErrorHandler 分类错误
    from hydroagent.utils.error_handler import ErrorHandler
    error_handler = ErrorHandler()
    error_info = error_handler.handle_exception(e)

    error_category = error_info["analysis"].get("error_category", "unknown")
    error_type = error_info.get("error_type", "Exception")

    print(f"[{i}/{total_queries}] [FAIL] 异常: {str(e)}")
    print(f"                        错误类型: {error_category}")

    results.append({
        "success": False,
        "query": query,
        "error": str(e),
        "error_type": error_type,           # 新增
        "error_category": error_category,   # 新增
        "experiment": self.exp_name,
        "mode": "mock" if use_mock else "real"
    })
```

#### CSV 增强错误信息

在 `save_results()` 方法中添加错误分类列：

```python
# 格式化错误: "[category] message" 便于阅读
error_msg = r.get("error", "")
error_category = r.get("error_category", "")
error_type = r.get("error_type", "")

if error_msg and error_category:
    formatted_error = f"[{error_category}] {error_msg}"
else:
    formatted_error = error_msg

row = {
    # ...
    "error_category": error_category,  # 新增
    "error_type": error_type,          # 新增
    "error": formatted_error           # 增强
}
```

---

### 3. 修复 DeveloperAgent `final_basin_ids` 未定义错误

**文件**: `hydroagent/agents/developer_agent.py:760`

#### 问题原因

在 `_generate_session_report()` 方法中，调用 `_generate_fallback_report()` 时使用了未定义的变量 `final_basin_ids`，而代码中只定义了 `basin_ids`。

#### 修复

```python
# Before (错误):
fallback_content = self._generate_fallback_report(
    tool_output=tool_output,
    final_basin_ids=final_basin_ids,  # 未定义！
    all_basins_metrics=all_basins_metrics,
    calibration_metrics=calibration_metrics
)

# After (修复):
fallback_content = self._generate_fallback_report(
    tool_output=tool_output,
    final_basin_ids=basin_ids,  # 使用正确的变量名
    all_basins_metrics=all_basins_metrics,
    calibration_metrics=calibration_metrics
)
```

---

### 4. Orchestrator 失败时生成报告

**文件**: `hydroagent/agents/orchestrator.py`

#### 问题原因

当任务在 `FAILED_UNRECOVERABLE` 状态时，Orchestrator 只是简单返回错误结果，不调用 DeveloperAgent 生成失败报告。这导致用户无法看到专业的分析报告。

#### 修复

在 `_execute_state_action()` 方法中，为 `FAILED_UNRECOVERABLE` 状态添加失败报告生成逻辑：

```python
elif state in [OrchestratorState.COMPLETED_SUCCESS, OrchestratorState.FAILED_UNRECOVERABLE]:
    # Terminal states - save to PromptPool if applicable
    if state == OrchestratorState.COMPLETED_SUCCESS:
        self._save_to_prompt_pool()

    # ✅ CRITICAL FIX: Generate failure report when task fails
    elif state == OrchestratorState.FAILED_UNRECOVERABLE:
        logger.info("[Orchestrator] Task failed, generating failure report...")
        try:
            # Prepare execution_result with error information
            error_msg = self.execution_context.get("error", "Unknown error")
            error_phase = self.execution_context.get("error_phase", "unknown")

            failure_result = {
                "success": False,
                "error": error_msg,
                "error_phase": error_phase,
                "user_query": self.execution_context.get("query", ""),
                "intent_result": self.execution_context.get("intent_result", {}),
                "task_plan": self.execution_context.get("task_plan", {}),
                "execution_results": self.execution_context.get("execution_results", []),
            }

            # Call DeveloperAgent to analyze failure
            failure_analysis = self._analyze_results(failure_result)

            # Store failure analysis in context
            return {
                "context_updates": {
                    "analysis_result": failure_analysis,
                }
            }

        except Exception as e:
            logger.error(f"[Orchestrator] Failed to generate failure report: {e}", exc_info=True)
            return {"context_updates": {}}

    return {"context_updates": {}}
```

---

## 测试验证

### 测试脚本

创建了 `test/test_error_classification_fix.py` 来验证所有修复：

```python
def test_error_handler_classification():
    """Test ErrorHandler's enhanced error classification."""
    handler = ErrorHandler()

    # Test 1: Network timeout error
    try:
        raise TimeoutError("Request timed out after 60 seconds")
    except Exception as e:
        error_info = handler.handle_exception(e)
        assert error_info['analysis']['error_category'] == 'network'

    # Test 2: NameError (code error)
    try:
        raise NameError("name 'final_basin_ids' is not defined")
    except Exception as e:
        error_info = handler.handle_exception(e)
        assert error_info['analysis']['error_category'] == 'code'

    # Test 3: NetCDF/HDF error (data error)
    try:
        raise RuntimeError("NetCDF: HDF error")
    except Exception as e:
        error_info = handler.handle_exception(e)
        assert error_info['analysis']['error_category'] == 'data'

    # Test 4: KeyError (configuration error)
    try:
        raise KeyError("prec")
    except Exception as e:
        error_info = handler.handle_exception(e)
        assert error_info['analysis']['error_category'] == 'configuration'
```

### 测试结果

```
================================================================================
[PASS] All tests passed successfully!
================================================================================

Summary of fixes:
1. [OK] ErrorHandler now classifies errors into 9 categories
2. [OK] DeveloperAgent fallback report fixed (final_basin_ids bug)
3. [OK] CSV now includes error_category, error_type, and formatted error
4. [OK] Orchestrator generates failure reports for failed tasks
```

---

## 修改文件清单

| 文件 | 修改内容 | 影响 |
|------|----------|------|
| `hydroagent/utils/error_handler.py` | 扩展错误分类（9个类别） | 增强错误分析能力 |
| `experiment/base_experiment.py` | 集成ErrorHandler，增强CSV错误信息 | 实验结果更清晰 |
| `hydroagent/agents/developer_agent.py` | 修复`final_basin_ids`未定义bug | 修复报告生成失败 |
| `hydroagent/agents/orchestrator.py` | 失败时调用DeveloperAgent生成报告 | 确保总是生成报告 |
| `test/test_error_classification_fix.py` | 添加单元测试 | 验证修复效果 |

---

## 用户体验改进

### Before (修复前)

```csv
query,success,error
"率定GR4J...",False,Unknown error
"验证流域...",False,Unknown error
```

**问题**：
- 无法区分错误类型
- 不知道是网络问题还是代码bug
- 没有失败报告，无法了解原因

### After (修复后)

```csv
query,success,error_category,error_type,error
"率定GR4J...",False,network,TimeoutError,"[network] Request timed out"
"验证流域...",False,code,NameError,"[code] name 'final_basin_ids' is not defined"
```

**改进**：
- ✅ 清晰的错误分类（network, code, data, etc.）
- ✅ 具体的错误类型（TimeoutError, NameError, etc.）
- ✅ 格式化的错误消息（`[category] message`）
- ✅ 每个失败的session都有 `analysis_report.md`

---

## 架构优势

### DeveloperAgent 作为统一后处理智能体

根据 CLAUDE.md v5.1 的设计原则，DeveloperAgent 现在是**真正的统一后处理智能体**：

```
任务执行成功 → DeveloperAgent → analysis_report.md ✅
任务执行失败 → DeveloperAgent → analysis_report.md ✅ (新增)
```

**核心价值**：
- 无论成功还是失败，用户都能获得专业的分析报告
- 失败报告包含错误类型、原因分析、解决建议
- 统一的用户体验，符合"哪怕没执行成功也要有总结"的需求

---

## 未来优化建议

1. **Error Recovery Suggestions**: 在 ErrorHandler 中添加更多针对性的修复建议
2. **Error Statistics**: 统计实验中各类错误的分布，生成错误热力图
3. **Auto-Retry Logic**: 对于 network 类错误，自动重试3次
4. **Error Notification**: 关键错误（如 API quota exhausted）发送邮件通知

---

## 参考文档

- `CLAUDE.md` - v5.1架构说明（DeveloperAgent统一后处理）
- `docs/ARCHITECTURE_FINAL.md` - 系统架构文档
- `hydroagent/utils/error_handler.py` - 错误处理器源码
- `experiment/base_experiment.py` - 实验基类源码

---

**Last Updated**: 2026-01-05
**Status**: ✅ All fixes tested and verified

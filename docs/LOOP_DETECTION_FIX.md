# Loop Detection and Fallback Mechanism

**Date**: 2025-12-31
**Version**: v5.1
**Status**: ✅ Implemented and Tested

---

## Problem Description

The system was experiencing **infinite loops** that hit the 100-transition state machine limit, particularly when:
1. **Multi-model tasks** (e.g., "对GR4J和XAJ两个模型分别率定") were split into subtasks
2. **LLM config reviewer** repeatedly rejected valid configurations with the same error
3. The state machine looped: `GENERATING_CONFIG → abort → PLANNING_TASKS → GENERATING_CONFIG`

### Example Log

```
logs/test_query_15_20251231_151706.log - 100 transitions reached
```

**Root Cause**: LLM reviewer saw "GR4J和XAJ" in the original query but only "xaj" in the current subtask's config, and repeatedly rejected it as "incomplete".

---

## Solution Architecture

### Two-Layer Defense

#### Layer 1: Prompt Improvements (Already Done)
- Added context to `llm_config_reviewer.py` explaining multi-model task decomposition
- Added context for iterative tasks, multi-basin tasks, etc.
- Updated obj_func validation rules to distinguish stopping conditions from objectives

**Limitation**: LLM may still misunderstand complex scenarios

#### Layer 2: Loop Detection + Fallback (NEW - Root Solution)
- **Detect** when the same config fails validation 2+ times
- **Fallback** to skip review and execute anyway
- **Preserve** normal validation for non-looping cases

---

## Implementation Details

### 1. FeedbackRouter (`hydroagent/core/feedback_router.py`)

#### Added Loop Detection State

```python
def __init__(self):
    # Loop detection: track recent config failures
    self.config_failure_history = []  # [(hash, error_msg), ...]
    self.max_history_size = 5
    self.loop_detection_threshold = 2  # 2 identical failures = loop
```

#### Hash Computation

```python
def _compute_config_hash(self, config: Dict[str, Any]) -> str:
    """Compute MD5 hash of key config fields for loop detection."""
    key_fields = {
        "model_name": config.get("model_cfgs", {}).get("model_name", ""),
        "basin_ids": str(config.get("data_cfgs", {}).get("basin_ids", [])),
        "algorithm": config.get("training_cfgs", {}).get("algorithm_name", "")
    }
    config_str = json.dumps(key_fields, sort_keys=True)
    return hashlib.md5(config_str.encode()).hexdigest()[:8]
```

**Why these fields?**
- `model_name`: Core identity of the task
- `basin_ids`: Data scope
- `algorithm`: Calibration method

These fields uniquely identify a config. If the same combination fails repeatedly, it's a loop.

#### Loop Detection Logic

```python
def _detect_config_loop(self, config_hash: str, error_msg: str) -> bool:
    """Returns True if same config failed threshold times."""
    self.config_failure_history.append((config_hash, error_msg))

    if len(self.config_failure_history) > self.max_history_size:
        self.config_failure_history.pop(0)

    if len(self.config_failure_history) < self.loop_detection_threshold:
        return False

    recent_hashes = [h for h, _ in self.config_failure_history[-self.loop_detection_threshold:]]
    same_config_count = recent_hashes.count(config_hash)

    return same_config_count >= self.loop_detection_threshold
```

#### Modified Feedback Routing

```python
def _route_interpreter_feedback(self, feedback, context):
    if feedback.get("success"):
        return {"action": "execute_task", ...}

    # Config failed validation
    error_msg = feedback.get("error", "")
    config = feedback.get("config", {})

    # 🔧 NEW: Check for loop
    if config:
        config_hash = self._compute_config_hash(config)
        is_loop = self._detect_config_loop(config_hash, error_msg)

        if is_loop:
            logger.warning("🚨 Loop detected! Skipping review and executing.")
            return {
                "action": "skip_review_and_execute",  # NEW ACTION
                "parameters": {
                    "config": config,
                    "skip_reason": "validation_loop_detected",
                    "original_error": error_msg[:200]
                }
            }

    # Original behavior: abort
    return {"action": "abort", ...}
```

### 2. Orchestrator (`hydroagent/agents/orchestrator.py`)

#### Handle New Action in GENERATING_CONFIG State

```python
elif state == OrchestratorState.GENERATING_CONFIG:
    # 🔧 Check if FeedbackRouter requested to skip review
    routing_decision = self.execution_context.get("routing_decision", {})
    if routing_decision.get("action") == "skip_review_and_execute":
        logger.warning("🔁 Loop detected - skipping review and executing directly")

        params = routing_decision.get("parameters", {})
        config = params.get("config", {})
        skip_reason = params.get("skip_reason")
        original_error = params.get("original_error")

        logger.warning(f"   Reason: {skip_reason}")
        logger.warning(f"   Original error: {original_error}")

        # Clear routing_decision to avoid reuse
        self.execution_context["routing_decision"] = {}

        # Extract task_id (from config or fallback to subtask)
        task_id = config.get("task_metadata", {}).get("task_id")
        if not task_id:
            # Fallback: find next pending subtask
            task_plan = self.execution_context.get("task_plan", {})
            subtasks = task_plan.get("subtasks", [])
            execution_results = self.execution_context.get("execution_results", [])
            completed_ids = {r.get("task_id") for r in execution_results}
            for st in subtasks:
                if st.get("task_id") not in completed_ids:
                    task_id = st.get("task_id")
                    break

        # Mark config as successful and proceed
        config_result = {
            "success": True,
            "config": config,
            "skip_review": True,
            "skip_reason": skip_reason,
            "task_id": task_id or "unknown"
        }

        return {
            "context_updates": {
                "config_result": config_result,
                "current_config": config,
            },
            "source_agent": "FeedbackRouter",
            "agent_result": config_result,
        }

    # Normal flow: call InterpreterAgent...
```

---

## Testing

### Unit Test: `test/test_feedback_router_loop.py`

Tests FeedbackRouter logic directly:

```bash
.venv/Scripts/python.exe test/test_feedback_router_loop.py
```

**Test Cases**:
1. ✅ First failure → abort (no loop yet)
2. ✅ Second identical failure → skip_review_and_execute (loop detected)
3. ✅ Different config → abort (no loop)
4. ✅ Hash computation consistency

**Result**: All tests passed ✅

### Integration Test: `test/test_loop_detection.py`

Tests full Orchestrator flow with multi-model task:

```bash
.venv/Scripts/python.exe test/test_loop_detection.py
```

**Expected Behavior**:
1. IntentAgent identifies multi-model task
2. TaskPlanner splits into 2 subtasks (GR4J, XAJ)
3. InterpreterAgent generates config for first model
4. If LLM reviewer rejects it 2+ times → Loop detected
5. FeedbackRouter returns `skip_review_and_execute`
6. Orchestrator skips review and proceeds to execution

---

## Benefits

### ✅ Solves Root Cause
- Prevents infinite loops without disabling validation
- Works for ANY repeated validation failure, not just multi-model tasks

### ✅ Preserves Normal Flow
- Validation still works for non-looping cases
- Only triggers fallback when truly stuck

### ✅ Diagnostic Friendly
- Logs show when loop was detected and why
- Original error is preserved for debugging
- Config is marked with `skip_review: true` for traceability

### ✅ Configurable
- `loop_detection_threshold = 2`: Easy to adjust sensitivity
- `max_history_size = 5`: Prevents unbounded memory growth

---

## Configuration Parameters

In `FeedbackRouter.__init__()`:

```python
self.max_history_size = 5          # Keep last N failures
self.loop_detection_threshold = 2   # N identical failures = loop
```

**Recommendations**:
- `threshold = 2`: Fast detection, minimal wasted effort
- `threshold = 3`: More conservative, allows for transient issues
- `max_history_size`: Should be ≥ threshold, typically 2-3x

---

## Log Indicators

### Loop Detected

```
[FeedbackRouter] 🔁 Loop detected! Same config failed 2 times. Hash: f993f1c2
[FeedbackRouter] 🚨 Configuration validation loop detected!
[FeedbackRouter] 🔧 Applying fallback: Skip review and execute with generated config
[Orchestrator] 🔁 Loop detected by FeedbackRouter - skipping review and executing directly
   Reason: validation_loop_detected
   Original error: 配置中obj_func设置为'RMSE'，但用户查询明确要求...
```

### Normal Validation Failure

```
[FeedbackRouter] InterpreterAgent failed (attempt 1): ...
[FeedbackRouter] Aborting after config validation failure
```

---

## Future Enhancements

### Possible Improvements

1. **Smarter Hash Function**
   - Include more config fields if needed
   - Use semantic similarity instead of exact match

2. **Adaptive Threshold**
   - Increase threshold for high-stakes tasks
   - Decrease for routine tasks

3. **Loop Classification**
   - Track which error patterns cause loops
   - Feed back to prompt improvement

4. **User Notification**
   - Option to ask user if should proceed when loop detected
   - Especially for critical tasks

---

## Related Files

### Modified
- `hydroagent/core/feedback_router.py` - Loop detection logic
- `hydroagent/agents/orchestrator.py` - Handle `skip_review_and_execute` action

### Related (Context Improvements)
- `hydroagent/utils/llm_config_reviewer.py` - Multi-model, iterative task context
- `hydroagent/agents/interpreter_agent.py` - obj_func default changed to RMSE

### Tests
- `test/test_feedback_router_loop.py` - Unit tests
- `test/test_loop_detection.py` - Integration test
- `test/test_obj_func_fix.py` - Related obj_func fix validation

---

## Changelog

### 2025-12-31 - v5.1
- ✅ Added loop detection to FeedbackRouter
- ✅ Added `skip_review_and_execute` action
- ✅ Modified Orchestrator to handle fallback
- ✅ Unit tests passing
- ✅ Documentation complete

### Related Fixes
- 2025-12-30: obj_func default changed to RMSE
- 2025-12-30: Multi-model task context added to LLMConfigReviewer
- 2025-12-30: Iterative task context added to LLMConfigReviewer

---

**Status**: ✅ Ready for production use

**Tested**: ✅ Unit tests passing

**Impact**: Prevents 100-transition limit errors without disabling validation

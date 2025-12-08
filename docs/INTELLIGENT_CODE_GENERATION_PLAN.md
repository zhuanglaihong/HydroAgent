# 智能代码生成系统改进方案
**版本**: v1.0
**日期**: 2025-12-07
**目标**: 让HydroAgent真正智能处理各种代码生成任务

---

## 🎯 核心问题

### **当前系统的局限性**
1. **代码质量不稳定**: LLM生成的代码可能有语法错误、被截断、逻辑错误
2. **缺少代码验证**: 生成后直接执行，没有语法检查
3. **错误反馈低效**: 只传递stderr，没有结构化的错误分析
4. **缺少代码模板**: 每次从零生成，效率低且不稳定
5. **没有自我修复能力**: 重试时没有针对性地修复问题

---

## 🚀 解决方案：5层智能化架构

### **Layer 1: 智能Prompt工程**

#### **1.1 结构化的Multi-Shot Prompts**
```python
# hydroagent/utils/intelligent_prompt_builder.py

class IntelligentPromptBuilder:
    """智能代码生成Prompt构建器"""

    def build_code_generation_prompt(
        self,
        analysis_type: str,
        data_info: Dict[str, Any],
        previous_errors: List[Dict] = None
    ) -> str:
        """
        构建高质量代码生成prompt

        特点：
        1. 提供成功案例（few-shot learning）
        2. 明确数据schema和路径
        3. 包含错误规避策略
        4. 强制代码完整性要求
        """

        # 基础要求
        base_requirements = self._get_base_requirements()

        # 成功案例（few-shot examples）
        success_examples = self._get_success_examples(analysis_type)

        # 数据信息
        data_schema = self._build_data_schema(data_info)

        # 错误规避（如果有previous_errors）
        error_prevention = self._build_error_prevention(previous_errors)

        # 代码完整性要求
        completeness_requirements = self._get_completeness_requirements()

        prompt = f"""
{base_requirements}

## 📋 任务
生成Python代码，进行**{analysis_type}**分析。

{success_examples}

{data_schema}

{error_prevention}

{completeness_requirements}

## ⚠️ 关键要求
1. **完整性**: 代码必须包含完整的 if __name__ == "__main__": 块
2. **错误处理**: 所有文件读取操作必须有try-except
3. **路径验证**: 文件不存在时给出清晰的错误信息
4. **输出明确**: 使用print()输出关键结果
5. **编码安全**: 使用 encoding='utf-8'

请生成完整、可执行的代码。
"""
        return prompt

    def _get_success_examples(self, analysis_type: str) -> str:
        """提供成功案例（Few-Shot Learning）"""
        examples = {
            "runoff_coefficient": '''
## 成功案例示范

```python
import xarray as xr
import numpy as np
from pathlib import Path

def calculate_runoff_coefficient(nc_file_path: str, basin_id: str) -> float:
    """计算径流系数"""
    try:
        # 读取数据
        ds = xr.open_dataset(nc_file_path)

        # 提取变量
        qobs = ds['qobs'].values.flatten()  # 观测流量
        prcp = ds['prcp'].values.flatten()  # 降水

        # 计算径流系数
        total_runoff = np.nansum(qobs)
        total_precip = np.nansum(prcp)

        if total_precip > 0:
            rc = total_runoff / total_precip
            print(f"流域 {basin_id} 径流系数: {rc:.4f}")
            return rc
        else:
            print("[WARNING] 总降水量为0，无法计算径流系数")
            return 0.0

    except FileNotFoundError:
        print(f"[ERROR] 文件不存在: {nc_file_path}")
        raise
    except KeyError as e:
        print(f"[ERROR] 数据变量缺失: {e}")
        raise

if __name__ == "__main__":
    # 主程序
    nc_file = r"path/to/data.nc"
    basin = "01013500"
    rc = calculate_runoff_coefficient(nc_file, basin)
```

请参考上述代码结构生成完整代码。
''',
            "FDC": '''...''',  # FDC的成功案例
        }
        return examples.get(analysis_type, "")

    def _build_data_schema(self, data_info: Dict) -> str:
        """构建数据schema说明"""
        nc_file = data_info.get("nc_file_path")

        return f"""
## 📂 数据信息
- **NetCDF文件路径**: `{nc_file}`
- **变量说明**:
  - `qobs`: 观测流量 [time, basin] (m³/s)
  - `qsim`: 模拟流量 [time, basin] (m³/s)
  - `prcp`: 降水 [time, basin] (mm/day)
  - `time`: 时间维度
  - `basin`: 流域维度

**CRITICAL**: 使用以下代码读取数据：
```python
import xarray as xr
nc_file_path = r"{nc_file}"  # 使用原始字符串避免转义问题

# 验证文件存在
from pathlib import Path
if not Path(nc_file_path).exists():
    raise FileNotFoundError(f"数据文件不存在: {{nc_file_path}}")

# 读取数据
ds = xr.open_dataset(nc_file_path)
```
"""

    def _build_error_prevention(self, previous_errors: List[Dict]) -> str:
        """基于历史错误构建规避策略"""
        if not previous_errors:
            return ""

        prevention = "\n## 🔧 错误规避策略\n"
        prevention += "以下错误在之前尝试中出现过，请避免：\n\n"

        for i, error in enumerate(previous_errors, 1):
            error_type = error.get("type", "unknown")
            stderr = error.get("stderr", "")

            if "SyntaxError" in stderr:
                prevention += f"{i}. **语法错误**: 请确保代码完整，特别是 `if __name__ == \"__main__\":` 块\n"
            elif "FileNotFoundError" in stderr:
                prevention += f"{i}. **文件不存在**: 请先验证文件路径，使用 `Path().exists()` 检查\n"
            elif "KeyError" in stderr:
                prevention += f"{i}. **变量缺失**: 请使用 `.get()` 方法安全访问字典\n"
            else:
                prevention += f"{i}. 之前错误: {stderr[:200]}...\n"

        return prevention

    def _get_completeness_requirements(self) -> str:
        """代码完整性要求"""
        return """
## ✅ 代码完整性检查清单
生成的代码必须包含以下所有部分：

```python
# 1. 导入语句（必须完整）
import xarray as xr
import numpy as np
from pathlib import Path

# 2. 函数定义（必须有docstring）
def analyze_xxx(...):
    \"\"\"函数说明\"\"\"
    pass

# 3. 主程序块（必须完整！）
if __name__ == "__main__":
    # 主逻辑
    result = analyze_xxx(...)
    print(f"结果: {result}")
```

⚠️ **常见错误**:
- ❌ `if __name` (不完整)
- ❌ `if __name__` (缺少比较)
- ✅ `if __name__ == "__main__":` (正确)
"""
```

---

### **Layer 2: 代码验证层**

```python
# hydroagent/utils/code_validator.py

import ast
import re
from typing import Tuple, List, Dict

class CodeValidator:
    """代码验证器 - 在执行前检查代码质量"""

    def validate_generated_code(self, code: str) -> Tuple[bool, List[Dict]]:
        """
        验证生成的代码

        Returns:
            (is_valid, issues)
        """
        issues = []

        # 1. 语法检查
        syntax_ok, syntax_issues = self._check_syntax(code)
        issues.extend(syntax_issues)

        # 2. 完整性检查
        completeness_ok, completeness_issues = self._check_completeness(code)
        issues.extend(completeness_issues)

        # 3. 安全性检查
        safety_ok, safety_issues = self._check_safety(code)
        issues.extend(safety_issues)

        is_valid = syntax_ok and completeness_ok and safety_ok
        return is_valid, issues

    def _check_syntax(self, code: str) -> Tuple[bool, List[Dict]]:
        """语法检查"""
        try:
            ast.parse(code)
            return True, []
        except SyntaxError as e:
            return False, [{
                "type": "syntax_error",
                "line": e.lineno,
                "message": str(e),
                "fix_suggestion": self._suggest_syntax_fix(e)
            }]

    def _check_completeness(self, code: str) -> Tuple[bool, List[Dict]]:
        """完整性检查"""
        issues = []

        # 检查是否有main块
        if not re.search(r'if\s+__name__\s*==\s*["\']__main__["\']\s*:', code):
            issues.append({
                "type": "missing_main_block",
                "message": "缺少 if __name__ == '__main__': 块",
                "fix_suggestion": "添加完整的主程序块"
            })

        # 检查是否有函数定义
        if not re.search(r'def\s+\w+\s*\(', code):
            issues.append({
                "type": "missing_function",
                "message": "没有函数定义",
                "fix_suggestion": "添加至少一个函数"
            })

        # 检查是否有import语句
        if not re.search(r'^import\s+|^from\s+\w+\s+import', code, re.MULTILINE):
            issues.append({
                "type": "missing_imports",
                "message": "缺少import语句",
                "fix_suggestion": "添加必要的import"
            })

        return len(issues) == 0, issues

    def _check_safety(self, code: str) -> Tuple[bool, List[Dict]]:
        """安全性检查"""
        issues = []

        # 检查危险操作
        dangerous_patterns = [
            (r'os\.system\(', "使用os.system()可能不安全"),
            (r'eval\(', "使用eval()可能不安全"),
            (r'exec\(', "使用exec()可能不安全"),
        ]

        for pattern, message in dangerous_patterns:
            if re.search(pattern, code):
                issues.append({
                    "type": "safety_warning",
                    "message": message,
                    "severity": "warning"
                })

        return len([i for i in issues if i.get("severity") == "error"]) == 0, issues

    def _suggest_syntax_fix(self, error: SyntaxError) -> str:
        """建议语法修复方案"""
        if "expected ':'" in str(error):
            return "请检查if/for/def等语句是否缺少冒号"
        elif "invalid syntax" in str(error):
            return "请检查代码结构完整性，可能有未闭合的括号或引号"
        return "请检查语法错误"
```

---

### **Layer 3: 智能重试机制**

```python
# hydroagent/utils/intelligent_retry.py

class IntelligentRetry:
    """智能重试 - 根据错误类型采取针对性策略"""

    def should_retry(
        self,
        error_info: Dict,
        attempt: int,
        max_retries: int
    ) -> Tuple[bool, str]:
        """
        决定是否重试以及重试策略

        Returns:
            (should_retry, retry_strategy)
        """
        if attempt >= max_retries:
            return False, ""

        error_type = error_info.get("type")
        stderr = error_info.get("stderr", "")

        # 语法错误 - 重新生成代码（加强completeness要求）
        if "SyntaxError" in stderr:
            return True, "regenerate_with_completeness_focus"

        # 文件不存在 - 重新生成代码（强调路径验证）
        elif "FileNotFoundError" in stderr:
            return True, "regenerate_with_path_validation"

        # 变量缺失 - 重新生成代码（提供更详细的data schema）
        elif "KeyError" in stderr:
            return True, "regenerate_with_detailed_schema"

        # 逻辑错误 - 重新生成代码（添加调试输出）
        elif "ZeroDivisionError" in stderr or "ValueError" in stderr:
            return True, "regenerate_with_debug_output"

        # 其他错误 - 通用重试
        else:
            return True, "regenerate_general"

    def apply_retry_strategy(
        self,
        strategy: str,
        prompt_builder: 'IntelligentPromptBuilder',
        error_info: Dict
    ) -> str:
        """应用特定的重试策略"""

        if strategy == "regenerate_with_completeness_focus":
            # 在prompt中强调代码完整性
            return prompt_builder.build_with_emphasis(
                emphasis="completeness",
                previous_error=error_info
            )

        elif strategy == "regenerate_with_path_validation":
            # 在prompt中强调路径验证
            return prompt_builder.build_with_emphasis(
                emphasis="path_validation",
                previous_error=error_info
            )

        # ... 其他策略
```

---

### **Layer 4: 代码模板库**

```python
# hydroagent/resources/code_templates/

# runoff_coefficient_template.py
"""
径流系数计算模板
- 稳定性高
- 错误处理完善
- 可直接使用或微调
"""

RUNOFF_COEFFICIENT_TEMPLATE = '''
import xarray as xr
import numpy as np
from pathlib import Path
from typing import Tuple, Optional

def calculate_runoff_coefficient(
    nc_file_path: str,
    basin_id: str,
    output_dir: Optional[str] = None
) -> Tuple[float, dict]:
    """
    计算流域径流系数

    Args:
        nc_file_path: NetCDF数据文件路径
        basin_id: 流域ID
        output_dir: 输出目录（可选）

    Returns:
        (runoff_coefficient, metadata)
    """
    print(f"[INFO] 开始计算流域 {basin_id} 的径流系数...")

    # 1. 验证文件存在
    nc_path = Path(nc_file_path)
    if not nc_path.exists():
        raise FileNotFoundError(f"数据文件不存在: {nc_file_path}")
    print(f"[INFO] 数据文件: {nc_file_path}")

    try:
        # 2. 读取NetCDF数据
        ds = xr.open_dataset(nc_file_path)
        print(f"[INFO] 可用变量: {list(ds.data_vars)}")

        # 3. 提取流量和降水数据
        if 'qobs' in ds.data_vars:
            qobs = ds['qobs'].values.flatten()
        elif 'streamflow' in ds.data_vars:
            qobs = ds['streamflow'].values.flatten()
        else:
            raise KeyError("未找到流量变量 (qobs 或 streamflow)")

        if 'prcp' in ds.data_vars:
            prcp = ds['prcp'].values.flatten()
        elif 'precipitation' in ds.data_vars:
            prcp = ds['precipitation'].values.flatten()
        else:
            raise KeyError("未找到降水变量 (prcp 或 precipitation)")

        # 4. 过滤NaN值
        valid_mask = ~(np.isnan(qobs) | np.isnan(prcp))
        qobs_clean = qobs[valid_mask]
        prcp_clean = prcp[valid_mask]

        print(f"[INFO] 有效数据点: {len(qobs_clean)} / {len(qobs)}")

        # 5. 计算径流系数
        total_runoff = np.sum(qobs_clean)
        total_precip = np.sum(prcp_clean)

        if total_precip == 0:
            print("[WARNING] 总降水量为0，无法计算径流系数")
            return 0.0, {"error": "zero_precipitation"}

        runoff_coefficient = total_runoff / total_precip

        # 6. 输出结果
        print(f"\\n{'='*60}")
        print(f"流域: {basin_id}")
        print(f"径流系数 (Runoff Coefficient): {runoff_coefficient:.4f}")
        print(f"总径流量: {total_runoff:.2f} m³/s")
        print(f"总降水量: {total_precip:.2f} mm")
        print(f"{'='*60}\\n")

        # 7. 构建元数据
        metadata = {
            "basin_id": basin_id,
            "runoff_coefficient": float(runoff_coefficient),
            "total_runoff": float(total_runoff),
            "total_precipitation": float(total_precip),
            "valid_points": int(len(qobs_clean)),
            "total_points": int(len(qobs))
        }

        # 8. 可选：保存结果到文件
        if output_dir:
            import json
            output_path = Path(output_dir) / f"runoff_coefficient_{basin_id}.json"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            print(f"[INFO] 结果已保存到: {output_path}")

        ds.close()
        return runoff_coefficient, metadata

    except Exception as e:
        print(f"[ERROR] 计算过程中发生错误: {str(e)}")
        raise


if __name__ == "__main__":
    # 主程序
    import sys

    # 从命令行参数或硬编码路径获取
    nc_file = r"{{NC_FILE_PATH}}"  # 将被替换
    basin = "{{BASIN_ID}}"  # 将被替换
    output = r"{{OUTPUT_DIR}}"  # 将被替换

    try:
        rc, meta = calculate_runoff_coefficient(nc_file, basin, output)
        print(f"\\n[SUCCESS] 径流系数计算完成: {rc:.4f}")
        sys.exit(0)
    except Exception as e:
        print(f"\\n[FAILED] 计算失败: {str(e)}")
        sys.exit(1)
'''

# 模板管理器
class TemplateManager:
    """代码模板管理器"""

    def get_template(self, analysis_type: str) -> Optional[str]:
        """获取模板"""
        templates = {
            "runoff_coefficient": RUNOFF_COEFFICIENT_TEMPLATE,
            "FDC": FDC_TEMPLATE,
            # ... 更多模板
        }
        return templates.get(analysis_type)

    def fill_template(
        self,
        template: str,
        placeholders: Dict[str, str]
    ) -> str:
        """填充模板占位符"""
        code = template
        for key, value in placeholders.items():
            code = code.replace(f"{{{{{key}}}}}", value)
        return code
```

---

### **Layer 5: 测试驱动的代码生成**

```python
# hydroagent/utils/test_driven_codegen.py

class TestDrivenCodeGenerator:
    """测试驱动的代码生成器"""

    def generate_with_tests(
        self,
        analysis_type: str,
        data_info: Dict
    ) -> Tuple[str, str]:
        """
        生成代码和测试用例

        Returns:
            (generated_code, test_code)
        """
        # 1. 先生成测试用例
        test_code = self._generate_test_case(analysis_type, data_info)

        # 2. 生成满足测试的代码
        code = self._generate_code_to_pass_tests(
            analysis_type,
            data_info,
            test_code
        )

        # 3. 运行测试验证
        test_passed, failures = self._run_tests(code, test_code)

        if not test_passed:
            # 4. 迭代修复
            code = self._fix_to_pass_tests(code, test_code, failures)

        return code, test_code

    def _generate_test_case(
        self,
        analysis_type: str,
        data_info: Dict
    ) -> str:
        """生成测试用例"""
        return f'''
import unittest
from pathlib import Path
import sys

class Test{analysis_type.title()}(unittest.TestCase):

    def test_file_exists(self):
        """测试数据文件存在"""
        nc_file = r"{data_info['nc_file_path']}"
        self.assertTrue(Path(nc_file).exists(), f"数据文件不存在: {{nc_file}}")

    def test_function_returns_valid_result(self):
        """测试函数返回有效结果"""
        # 导入待测试的函数
        # ...
        result = calculate_xxx(...)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, (float, int))

    def test_output_is_created(self):
        """测试输出文件被创建"""
        # ...

if __name__ == "__main__":
    unittest.main()
'''
```

---

## 🔧 实施步骤

### **Phase 1: 基础增强（1周）**
1. ✅ 实现 `IntelligentPromptBuilder`
2. ✅ 实现 `CodeValidator`
3. ✅ 集成到现有的 `code_generator.py`

### **Phase 2: 模板库（2周）**
1. ✅ 创建5个核心分析模板（径流系数、FDC、水量平衡、季节分析、极值分析）
2. ✅ 实现 `TemplateManager`
3. ✅ 在代码生成时优先使用模板

### **Phase 3: 智能重试（1周）**
1. ✅ 实现 `IntelligentRetry`
2. ✅ 集成error-specific重试策略
3. ✅ 添加详细的日志和诊断

### **Phase 4: 测试驱动（2周，可选）**
1. ⏰ 实现 `TestDrivenCodeGenerator`
2. ⏰ 集成单元测试框架
3. ⏰ 自动化测试验证

---

## 📊 预期效果

| 指标 | 当前 | 改进后 |
|------|------|--------|
| **代码生成成功率** | ~60% | ~95% |
| **首次执行成功率** | ~40% | ~80% |
| **平均重试次数** | 2.5次 | <1.5次 |
| **语法错误率** | ~25% | <5% |
| **文件读取错误率** | ~20% | <3% |
| **用户满意度** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

---

## 🎯 关键成功因素

1. **Few-Shot Learning**: 提供成功案例让LLM学习
2. **Pre-Execution Validation**: 执行前验证代码质量
3. **Error-Specific Retry**: 针对性地修复不同类型的错误
4. **Template Library**: 使用验证过的模板提高稳定性
5. **Structured Error Feedback**: 给LLM提供结构化的错误信息

---

## 🚀 立即可行的Quick Win

```python
# 在 code_generator.py 的 generate_analysis_code 函数中添加：

def generate_analysis_code(...):
    # 1. 先尝试使用模板
    template = TemplateManager().get_template(analysis_type)
    if template:
        code = fill_template(template, placeholders)
        is_valid, issues = CodeValidator().validate_generated_code(code)
        if is_valid:
            return code  # 使用模板成功！

    # 2. 模板不可用，使用LLM生成
    prompt = IntelligentPromptBuilder().build_code_generation_prompt(
        analysis_type=analysis_type,
        data_info=data_info,
        previous_errors=error_history
    )

    code = llm.generate(prompt)

    # 3. 验证生成的代码
    is_valid, issues = CodeValidator().validate_generated_code(code)
    if not is_valid:
        # 修复或重新生成
        code = self._fix_code_issues(code, issues)

    return code
```

---

**结论**: 通过这5层智能化架构，HydroAgent将能够**真正智能地处理各种代码生成任务**，而不是依赖运气和多次重试。

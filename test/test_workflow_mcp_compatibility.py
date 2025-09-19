"""
新工作流生成器与MCP格式兼容性测试

测试新生成的工作流格式是否能与现有的MCP工具兼容

Author: Assistant  
Date: 2025-01-20
"""

import logging
import sys
import json
from pathlib import Path
from typing import Dict, Any, List

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入新版工作流生成器
from workflow import (
    create_workflow_generator, GenerationConfig,
    AssembledWorkflow, WorkflowTask, TaskType
)

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WorkflowCompatibilityTester:
    """工作流兼容性测试器"""
    
    def __init__(self):
        """初始化测试器"""
        # 尝试创建Ollama客户端
        self.ollama_client = None
        try:
            import ollama
            self.ollama_client = ollama.Client()
            print("✅ Ollama客户端创建成功，将使用LLM增强功能")
        except ImportError:
            print("⚠️  Ollama未安装，将使用基础规则模式")
        except Exception as e:
            print(f"⚠️  Ollama客户端创建失败: {str(e)}，将使用基础规则模式")
        
        # 创建配置
        self.config = GenerationConfig(
            llm_model="qwen3:8b",
            llm_temperature=0.7,
            enable_feedback_learning=False,
            enable_validation=True
        )
        
        # 创建工作流生成器，传入Ollama客户端
        self.generator = create_workflow_generator(
            ollama_client=self.ollama_client,
            config=self.config
        )
        
        # 测试结果
        self.test_results = []
    
    def convert_workflow_to_mcp_format(self, workflow: AssembledWorkflow) -> Dict[str, Any]:
        """将新工作流格式转换为MCP兼容格式"""
        try:
            # 转换为MCP工作流格式
            mcp_workflow = {
                "plan_id": workflow.workflow_id,
                "name": workflow.name,
                "description": workflow.description,
                "steps": [],
                "metadata": {
                    **workflow.metadata,
                    "conversion_time": "2025-01-20",
                    "source_format": "WorkflowGeneratorV2"
                }
            }
            
            # 转换任务为MCP步骤格式
            for task in workflow.tasks:
                mcp_step = {
                    "step_id": task.task_id,
                    "name": task.name,
                    "description": task.description,
                    "tool_name": task.action,
                    "step_type": "tool_call",
                    "parameters": task.parameters,
                    "dependencies": task.dependencies,
                    "conditions": task.conditions if task.conditions else {},
                    "retry_count": task.retry_count,
                    "timeout": task.timeout
                }
                mcp_workflow["steps"].append(mcp_step)
            
            return mcp_workflow
            
        except Exception as e:
            logger.error(f"工作流格式转换失败: {str(e)}")
            return {}
    
    def validate_mcp_format(self, mcp_workflow: Dict[str, Any]) -> Dict[str, Any]:
        """验证MCP格式的有效性"""
        validation_result = {
            "is_valid": True,
            "issues": [],
            "suggestions": []
        }
        
        try:
            # 检查必需字段
            required_fields = ["plan_id", "name", "description", "steps"]
            for field in required_fields:
                if field not in mcp_workflow:
                    validation_result["is_valid"] = False
                    validation_result["issues"].append(f"缺少必需字段: {field}")
            
            # 检查步骤格式
            if "steps" in mcp_workflow:
                for i, step in enumerate(mcp_workflow["steps"]):
                    step_required_fields = ["step_id", "name", "tool_name"]
                    for field in step_required_fields:
                        if field not in step:
                            validation_result["is_valid"] = False
                            validation_result["issues"].append(f"步骤{i+1}缺少必需字段: {field}")
                    
                    # 检查依赖关系
                    dependencies = step.get("dependencies", [])
                    all_step_ids = [s.get("step_id") for s in mcp_workflow["steps"]]
                    for dep_id in dependencies:
                        if dep_id not in all_step_ids:
                            validation_result["is_valid"] = False
                            validation_result["issues"].append(f"步骤{step.get('step_id')}依赖的步骤{dep_id}不存在")
            
            # 检查工具名称有效性
            valid_tools = {
                "load_data", "save_data", "read_csv", "write_csv",
                "analyze_data", "calculate_stats", "get_model_params",
                "calibrate_model", "run_model", "gr4j_calibration",
                "plot_data", "create_chart", "visualize_results",
                "generate_report", "export_results"
            }
            
            if "steps" in mcp_workflow:
                for step in mcp_workflow["steps"]:
                    tool_name = step.get("tool_name", "")
                    if tool_name and tool_name not in valid_tools:
                        validation_result["issues"].append(f"未知工具: {tool_name}")
                        validation_result["suggestions"].append(f"建议使用已知工具替代 {tool_name}")
            
        except Exception as e:
            validation_result["is_valid"] = False
            validation_result["issues"].append(f"验证过程出错: {str(e)}")
        
        return validation_result
    
    def test_workflow_compatibility(self, instruction: str) -> Dict[str, Any]:
        """测试单个工作流的兼容性"""
        logger.info(f"测试指令: {instruction}")
        
        test_result = {
            "instruction": instruction,
            "generation_success": False,
            "generation_time": 0.0,
            "conversion_success": False,
            "validation_success": False,
            "workflow_info": {},
            "mcp_format": {},
            "validation_result": {},
            "errors": []
        }
        
        try:
            # 第一步：生成工作流
            generation_result = self.generator.generate_workflow(instruction)
            
            test_result["generation_success"] = generation_result.success
            test_result["generation_time"] = generation_result.total_time
            
            if not generation_result.success:
                test_result["errors"].append(f"工作流生成失败: {generation_result.error_message}")
                return test_result
            
            workflow = generation_result.workflow
            
            # 记录工作流信息
            test_result["workflow_info"] = {
                "name": workflow.name,
                "task_count": len(workflow.tasks),
                "has_dependencies": any(task.dependencies for task in workflow.tasks),
                "task_types": [task.task_type.value for task in workflow.tasks],
                "actions": [task.action for task in workflow.tasks]
            }
            
            # 第二步：转换为MCP格式
            mcp_workflow = self.convert_workflow_to_mcp_format(workflow)
            
            if mcp_workflow:
                test_result["conversion_success"] = True
                test_result["mcp_format"] = mcp_workflow
            else:
                test_result["errors"].append("MCP格式转换失败")
                return test_result
            
            # 第三步：验证MCP格式
            validation_result = self.validate_mcp_format(mcp_workflow)
            test_result["validation_result"] = validation_result
            test_result["validation_success"] = validation_result["is_valid"]
            
            if not validation_result["is_valid"]:
                test_result["errors"].extend(validation_result["issues"])
            
        except Exception as e:
            test_result["errors"].append(f"测试过程异常: {str(e)}")
            logger.error(f"测试异常: {str(e)}")
        
        return test_result
    
    def run_compatibility_tests(self) -> List[Dict[str, Any]]:
        """运行兼容性测试套件"""
        print("🧪 新工作流生成器与MCP格式兼容性测试\n")
        
        # 测试用例
        test_cases = [
            "加载CSV数据并计算统计信息",
            "获取GR4J模型参数",
            "使用示例数据校准模型",
            "完整的水文建模流程：数据预处理、模型校准、结果分析"
        ]
        
        # 执行测试
        for instruction in test_cases:
            test_result = self.test_compatibility(instruction)
            self.test_results.append(test_result)
            
            # 打印简要结果
            gen_status = "✅" if test_result["generation_success"] else "❌"
            conv_status = "✅" if test_result["conversion_success"] else "❌"
            val_status = "✅" if test_result["validation_success"] else "❌"
            
            print(f"{gen_status} 生成 | {conv_status} 转换 | {val_status} 验证 | {instruction}")
            
            # 如果有错误，显示第一个错误
            if test_result["errors"]:
                print(f"   ⚠️  {test_result['errors'][0]}")
            
            print("-" * 80)
        
        return self.test_results
    
    def test_compatibility(self, instruction: str) -> Dict[str, Any]:
        """简化的兼容性测试方法"""
        return self.test_workflow_compatibility(instruction)
    
    def generate_compatibility_report(self) -> Dict[str, Any]:
        """生成兼容性报告"""
        if not self.test_results:
            return {"error": "没有测试结果"}
        
        total_tests = len(self.test_results)
        generation_success = sum(1 for r in self.test_results if r["generation_success"])
        conversion_success = sum(1 for r in self.test_results if r["conversion_success"])
        validation_success = sum(1 for r in self.test_results if r["validation_success"])
        
        # 统计工具使用情况
        all_actions = []
        for result in self.test_results:
            if result["workflow_info"].get("actions"):
                all_actions.extend(result["workflow_info"]["actions"])
        
        action_counts = {}
        for action in all_actions:
            action_counts[action] = action_counts.get(action, 0) + 1
        
        # 统计任务类型
        all_task_types = []
        for result in self.test_results:
            if result["workflow_info"].get("task_types"):
                all_task_types.extend(result["workflow_info"]["task_types"])
        
        task_type_counts = {}
        for task_type in all_task_types:
            task_type_counts[task_type] = task_type_counts.get(task_type, 0) + 1
        
        report = {
            "测试概况": {
                "总测试数": total_tests,
                "生成成功数": generation_success,
                "转换成功数": conversion_success,
                "验证成功数": validation_success,
                "生成成功率": f"{generation_success/total_tests*100:.1f}%",
                "转换成功率": f"{conversion_success/total_tests*100:.1f}%",
                "验证成功率": f"{validation_success/total_tests*100:.1f}%"
            },
            "工具使用统计": action_counts,
            "任务类型统计": task_type_counts,
            "详细结果": self.test_results
        }
        
        return report
    
    def save_sample_workflows(self):
        """保存示例工作流文件"""
        sample_dir = Path("test") / "sample_workflows"
        sample_dir.mkdir(exist_ok=True)
        
        for i, result in enumerate(self.test_results, 1):
            if result["generation_success"] and result["mcp_format"]:
                # 保存原始格式
                original_file = sample_dir / f"workflow_{i}_original.json"
                with open(original_file, 'w', encoding='utf-8') as f:
                    json.dump(result["workflow_info"], f, ensure_ascii=False, indent=2)
                
                # 保存MCP格式
                mcp_file = sample_dir / f"workflow_{i}_mcp.json"
                with open(mcp_file, 'w', encoding='utf-8') as f:
                    json.dump(result["mcp_format"], f, ensure_ascii=False, indent=2)
        
        print(f"📁 示例工作流已保存到: {sample_dir}")


def main():
    """主函数"""
    tester = WorkflowCompatibilityTester()
    
    try:
        # 运行兼容性测试
        results = tester.run_compatibility_tests()
        
        # 生成报告
        report = tester.generate_compatibility_report()
        
        # 打印报告
        print("\n" + "="*80)
        print("📊 兼容性测试报告")
        print("="*80)
        
        for section, data in report.items():
            if section != "详细结果":
                print(f"\n{section}:")
                if isinstance(data, dict):
                    for key, value in data.items():
                        print(f"  {key}: {value}")
                else:
                    print(f"  {data}")
        
        # 保存示例工作流
        tester.save_sample_workflows()
        
        # 保存完整报告
        report_file = Path("test") / "workflow_compatibility_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n📄 完整报告已保存到: {report_file}")
        
        # 判断测试是否成功
        success_rate = float(report["测试概况"]["验证成功率"].rstrip('%'))
        if success_rate >= 80.0:
            print("\n🎉 兼容性测试成功!")
            return True
        else:
            print(f"\n⚠️  兼容性测试部分失败，验证成功率: {success_rate}%")
            return False
        
    except Exception as e:
        logger.error(f"测试失败: {str(e)}")
        print(f"\n❌ 测试失败: {str(e)}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

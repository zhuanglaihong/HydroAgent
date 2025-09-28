"""
Author: Claude Code
Date: 2025-09-28 13:50:00
LastEditTime: 2025-09-28 13:50:00
LastEditors: Claude Code
Description: Ollama卡住问题诊断脚本
FilePath: \HydroAgent\test\test_ollama_diagnosis.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import sys
import json
import time
import logging
import threading
import psutil
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 确保logs目录存在
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

# 设置详细日志
log_file = logs_dir / f"test_ollama_diagnosis_{int(time.time())}.log"

# 只输出到文件，不输出到终端
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)

# 创建一个logger用于输出
logger = logging.getLogger(__name__)

# 重定向print到logger
import builtins
original_print = builtins.print

def log_print(*args, **kwargs):
    """重定向print到logger"""
    message = ' '.join(str(arg) for arg in args)
    logger.info(message)

builtins.print = log_print

# 只在终端显示日志文件路径
original_print(f"诊断开始，所有输出将保存到: {log_file}")
original_print("请查看日志文件获取详细结果")

def check_system_resources():
    """检查系统资源使用情况"""
    print("=== 系统资源检查 ===")

    # CPU使用率
    cpu_percent = psutil.cpu_percent(interval=1)
    print(f"CPU使用率: {cpu_percent}%")

    # 内存使用
    memory = psutil.virtual_memory()
    print(f"内存使用: {memory.percent}% ({memory.used / 1024**3:.1f}GB / {memory.total / 1024**3:.1f}GB)")

    # 磁盘使用
    disk = psutil.disk_usage('C:')
    print(f"磁盘使用: {disk.percent}% ({disk.used / 1024**3:.1f}GB / {disk.total / 1024**3:.1f}GB)")

    return {
        "cpu_percent": cpu_percent,
        "memory_percent": memory.percent,
        "memory_available_gb": memory.available / 1024**3,
        "disk_percent": disk.percent
    }

def check_ollama_service():
    """检查Ollama服务状态"""
    print("\n=== Ollama服务检查 ===")

    try:
        import ollama
        client = ollama.Client()

        # 检查连接
        models = client.list()
        print(f"Ollama服务连接: 正常")

        # 正确解析模型名称
        model_names = []
        if models and 'models' in models:
            for model in models['models']:
                # 尝试多种可能的键名
                name = model.get('name') or model.get('model') or model.get('id', 'unknown')
                # 如果还是unknown，打印完整模型信息以便调试
                if name == 'unknown':
                    print(f"模型信息调试: {model}")
                model_names.append(name)

        print(f"可用模型: {model_names}")
        print(f"模型总数: {len(model_names)}")

        return True, models
    except Exception as e:
        print(f"Ollama服务连接: 失败 - {e}")
        return False, None

def test_progressive_complexity():
    """渐进式复杂度测试"""
    print("\n=== 渐进式复杂度测试 ===")

    try:
        import ollama
        client = ollama.Client()

        # 测试用例 - 从简单到复杂
        test_cases = [
            {
                "name": "简单问答",
                "prompt": "你好",
                "timeout": 10
            },
            {
                "name": "基础介绍",
                "prompt": "请简单介绍GR4J水文模型。",
                "timeout": 30
            },
            {
                "name": "结构化输出",
                "prompt": "请以JSON格式介绍GR4J模型的4个参数，格式：{\"parameters\": [{\"name\": \"参数名\", \"description\": \"描述\"}]}",
                "timeout": 45
            },
            {
                "name": "复杂推理（简化版）",
                "prompt": """请为水文建模设计一个简单的工作流，包含3个步骤：
1. 数据准备
2. 模型率定
3. 结果评估

以JSON格式输出：
{
  "workflow": [
    {"step": 1, "name": "步骤名", "description": "描述"}
  ]
}""",
                "timeout": 60
            }
        ]

        results = []

        for i, test_case in enumerate(test_cases, 1):
            print(f"\n测试 {i}: {test_case['name']}")
            print(f"提示词长度: {len(test_case['prompt'])} 字符")

            success = False
            response_time = 0
            content = ""
            error_msg = ""

            try:
                start_time = time.time()

                # 使用线程和超时控制
                response_container = [None]
                exception_container = [None]

                def ollama_call():
                    try:
                        response = client.generate(
                            model="qwen3:8b",
                            prompt=test_case['prompt'],
                            options={"temperature": 0.2}
                        )
                        response_container[0] = response
                    except Exception as e:
                        exception_container[0] = e

                # 启动线程
                thread = threading.Thread(target=ollama_call)
                thread.daemon = True
                thread.start()

                # 等待完成或超时
                thread.join(timeout=test_case['timeout'])
                response_time = time.time() - start_time

                if thread.is_alive():
                    print(f"❌ 超时 ({test_case['timeout']}秒)")
                    error_msg = f"超时({test_case['timeout']}秒)"
                elif exception_container[0]:
                    print(f"❌ 异常: {exception_container[0]}")
                    error_msg = str(exception_container[0])
                elif response_container[0]:
                    content = response_container[0].get('response', '')
                    if content:
                        print(f"✅ 成功 ({response_time:.2f}秒)")
                        print(f"响应长度: {len(content)} 字符")
                        print(f"响应预览: {content[:100]}...")
                        success = True
                    else:
                        print(f"❌ 空响应")
                        error_msg = "空响应"
                else:
                    print(f"❌ 无响应")
                    error_msg = "无响应"

            except Exception as e:
                print(f"❌ 测试异常: {e}")
                error_msg = str(e)
                response_time = time.time() - start_time

            results.append({
                "test_name": test_case['name'],
                "prompt_length": len(test_case['prompt']),
                "success": success,
                "response_time": response_time,
                "timeout": test_case['timeout'],
                "content_length": len(content),
                "error": error_msg
            })

            # 如果测试失败，检查系统资源
            if not success:
                print("检查测试失败时的系统资源:")
                resources = check_system_resources()
                results[-1]["resources_on_failure"] = resources

                # 如果是超时，等待一段时间让系统恢复
                if "超时" in error_msg:
                    print("等待30秒让系统恢复...")
                    time.sleep(30)

        return results

    except Exception as e:
        print(f"渐进式测试异常: {e}")
        return []

def analyze_results(results):
    """分析测试结果"""
    print("\n=== 结果分析 ===")

    success_count = sum(1 for r in results if r['success'])
    total_count = len(results)

    print(f"成功率: {success_count}/{total_count} ({success_count/total_count*100:.1f}%)")

    # 找出卡住的临界点
    last_success = None
    first_failure = None

    for result in results:
        if result['success']:
            last_success = result
        elif first_failure is None:
            first_failure = result

    if last_success and first_failure:
        print(f"\n临界点分析:")
        print(f"最后成功: {last_success['test_name']} ({last_success['prompt_length']} 字符)")
        print(f"首次失败: {first_failure['test_name']} ({first_failure['prompt_length']} 字符)")

        if first_failure.get('resources_on_failure'):
            res = first_failure['resources_on_failure']
            print(f"失败时系统资源: CPU {res['cpu_percent']}%, 内存 {res['memory_percent']}%")

    # 检查是否是特定复杂度导致的问题
    complex_prompts = [r for r in results if r['prompt_length'] > 500]
    if complex_prompts and not any(r['success'] for r in complex_prompts):
        print("\n问题诊断: Ollama在处理复杂提示词(>500字符)时卡住")
        print("建议: 简化提示词模板或使用API模式")

    return {
        "success_rate": success_count / total_count if total_count > 0 else 0,
        "last_success": last_success,
        "first_failure": first_failure,
        "complex_prompts_failing": len([r for r in complex_prompts if not r['success']]) if complex_prompts else 0
    }

def main():
    """主函数"""
    print("=== Ollama卡住问题诊断 ===")

    # 1. 检查系统资源
    system_resources = check_system_resources()

    # 2. 检查Ollama服务
    ollama_available, models = check_ollama_service()

    if not ollama_available:
        print("Ollama服务不可用，无法继续测试")
        return

    # 3. 渐进式复杂度测试
    test_results = test_progressive_complexity()

    # 4. 分析结果
    analysis = analyze_results(test_results)

    # 5. 保存诊断报告
    report = {
        "timestamp": time.time(),
        "system_resources": system_resources,
        "ollama_service": {
            "available": ollama_available,
            "models": models
        },
        "test_results": test_results,
        "analysis": analysis,
        "recommendations": []
    }

    # 生成建议
    if analysis['success_rate'] < 0.5:
        report['recommendations'].append("Ollama性能不佳，建议使用API模式")

    if analysis.get('complex_prompts_failing', 0) > 0:
        report['recommendations'].append("复杂提示词导致卡住，建议简化CoT模板")

    if system_resources['memory_percent'] > 80:
        report['recommendations'].append("内存使用率过高，可能影响Ollama性能")

    if system_resources['cpu_percent'] > 80:
        report['recommendations'].append("CPU使用率过高，可能影响Ollama性能")

    # 保存报告
    output_file = project_root / "ollama_diagnosis_report.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n诊断报告已保存到: {output_file}")

    # 输出建议
    print("\n=== 建议 ===")
    for rec in report['recommendations']:
        print(f"• {rec}")

    if not report['recommendations']:
        print("• 系统运行正常，问题可能在提示词复杂度")
        print("• 建议减少CoT步骤或使用更强的模型")

    # 恢复原始print函数并显示完成信息
    builtins.print = original_print
    original_print(f"\n诊断完成！")
    original_print(f"详细报告: {output_file}")
    original_print(f"诊断日志: {log_file}")

    # 显示关键结果摘要
    success_rate = analysis.get('success_rate', 0)
    original_print(f"测试成功率: {success_rate*100:.1f}%")

    if report['recommendations']:
        original_print("主要建议:")
        for rec in report['recommendations'][:3]:  # 只显示前3个建议
            original_print(f"  • {rec}")

if __name__ == "__main__":
    main()
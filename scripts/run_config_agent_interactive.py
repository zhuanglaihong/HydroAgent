"""
Author: zhuanglaihong
Date: 2025-11-20 22:30:00
LastEditTime: 2025-11-20 22:30:00
LastEditors: zhuanglaihong
Description: Interactive test script for ConfigAgent - 配置生成智能体交互测试
FilePath: \\HydroAgent\\scripts\\run_config_agent_interactive.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def print_banner():
    """打印欢迎横幅"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║              ConfigAgent 交互式测试工具                      ║
║           测试配置生成智能体的参数调整和验证功能              ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)


def print_separator(char="─", length=60):
    """打印分隔线"""
    print(char * length)


def get_preset_intents():
    """获取预设的Intent结果"""
    return {
        "1": {
            "name": "GR4J模型率定（完整配置）",
            "intent_result": {
                "intent": "calibration",
                "model_name": "gr4j",
                "basin_id": "01013500",
                "time_period": {
                    "train": ["2000-01-01", "2010-12-31"],
                    "test": ["2011-01-01", "2015-12-31"]
                },
                "algorithm": "SCE_UA",
                "missing_info": [],
                "clarifications_needed": [],
                "confidence": 0.95
            }
        },
        "2": {
            "name": "XAJ模型率定（复杂模型）",
            "intent_result": {
                "intent": "calibration",
                "model_name": "xaj",
                "basin_id": "camels_11532500",
                "time_period": {
                    "train": ["2005-01-01", "2010-12-31"],
                    "test": ["2011-01-01", "2015-12-31"]
                },
                "algorithm": "SCE_UA",
                "missing_info": [],
                "clarifications_needed": [],
                "confidence": 0.9
            }
        },
        "3": {
            "name": "GR5J模型（缺少时间段）",
            "intent_result": {
                "intent": "calibration",
                "model_name": "gr5j",
                "basin_id": "01022500",
                "time_period": None,
                "algorithm": "SCE_UA",
                "missing_info": ["time_period"],
                "clarifications_needed": ["请指定时间段"],
                "confidence": 0.7
            }
        },
        "4": {
            "name": "GR6J模型评估",
            "intent_result": {
                "intent": "evaluation",
                "model_name": "gr6j",
                "basin_id": "01030500",
                "time_period": {
                    "test": ["2015-01-01", "2020-12-31"]
                },
                "algorithm": "SCE_UA",
                "missing_info": [],
                "clarifications_needed": [],
                "confidence": 0.85
            }
        },
        "5": {
            "name": "最小配置（仅模型名）",
            "intent_result": {
                "intent": "calibration",
                "model_name": "gr1y",
                "basin_id": None,
                "time_period": None,
                "algorithm": "SCE_UA",
                "missing_info": ["basin_id", "time_period"],
                "clarifications_needed": [],
                "confidence": 0.6
            }
        }
    }


def show_preset_menu():
    """显示预设菜单"""
    print("\n预设Intent结果:")
    print_separator()

    presets = get_preset_intents()
    for key, preset in presets.items():
        print(f"{key}. {preset['name']}")
        intent = preset['intent_result']
        print(f"   模型: {intent['model_name']}, "
              f"流域: {intent.get('basin_id', 'N/A')}, "
              f"意图: {intent['intent']}")

    print("0. 自定义Intent结果（输入JSON）")
    print("q. 退出")
    print_separator()


def print_intent_result(intent_result: dict):
    """打印Intent结果"""
    print("\n【Intent Result】")
    print_separator("─")
    print(f"意图: {intent_result.get('intent', 'N/A').upper()}")
    print(f"模型: {intent_result.get('model_name', 'N/A')}")
    print(f"流域: {intent_result.get('basin_id', 'N/A')}")
    print(f"算法: {intent_result.get('algorithm', 'N/A')}")

    time_period = intent_result.get('time_period')
    if time_period and isinstance(time_period, dict):
        print("时间段:")
        if train := time_period.get('train'):
            print(f"  训练: {train[0]} 到 {train[1]}")
        if test := time_period.get('test'):
            print(f"  测试: {test[0]} 到 {test[1]}")
    else:
        print("时间段: 未指定")

    if missing := intent_result.get('missing_info'):
        print(f"缺失信息: {', '.join(missing)}")

    print_separator("─")


def print_config_result(result: dict):
    """打印配置结果"""
    print("\n【Config Generation Result】")
    print_separator("═")

    success = result.get("success", False)
    status_icon = "✅" if success else "❌"
    print(f"状态: {status_icon} {'成功' if success else '失败'}")

    if not success:
        print(f"错误: {result.get('error', 'Unknown error')}")
        if validation_errors := result.get('validation_errors'):
            print("验证错误:")
            for error in validation_errors:
                print(f"  - {error}")
        print_separator("═")
        return

    # 显示配置摘要
    if summary := result.get('config_summary'):
        print(summary)

    print_separator("═")


def print_detailed_config(config: dict):
    """打印详细配置"""
    print("\n【详细配置】")
    print_separator("─")

    # 数据配置
    print("数据配置 (data_cfgs):")
    data_cfgs = config.get('data_cfgs', {})
    print(f"  数据源类型: {data_cfgs.get('data_source_type')}")
    print(f"  流域列表: {data_cfgs.get('basin_ids')}")
    print(f"  训练期: {data_cfgs.get('train_period')}")
    print(f"  测试期: {data_cfgs.get('test_period')}")
    print(f"  预热期长度: {data_cfgs.get('warmup_length')} 天")
    print(f"  变量: {', '.join(data_cfgs.get('variables', []))}")

    # 模型配置
    print("\n模型配置 (model_cfgs):")
    model_cfgs = config.get('model_cfgs', {})
    print(f"  模型名称: {model_cfgs.get('model_name')}")
    print(f"  模型参数: {model_cfgs.get('model_params', {})}")

    # 训练配置
    print("\n训练配置 (training_cfgs):")
    training_cfgs = config.get('training_cfgs', {})
    print(f"  算法名称: {training_cfgs.get('algorithm_name')}")
    algo_params = training_cfgs.get('algorithm_params', {})
    print(f"  算法参数:")
    for key, value in algo_params.items():
        print(f"    {key}: {value}")
    loss_config = training_cfgs.get('loss_config', {})
    print(f"  损失函数: {loss_config.get('obj_func', 'N/A')}")
    print(f"  输出目录: {training_cfgs.get('output_dir')}")
    print(f"  实验名称: {training_cfgs.get('experiment_name')}")
    print(f"  随机种子: {training_cfgs.get('random_seed')}")

    # 评估配置
    print("\n评估配置 (evaluation_cfgs):")
    eval_cfgs = config.get('evaluation_cfgs', {})
    print(f"  评估指标: {', '.join(eval_cfgs.get('metrics', []))}")
    print(f"  保存结果: {eval_cfgs.get('save_results')}")
    print(f"  绘制结果: {eval_cfgs.get('plot_results')}")

    print_separator("─")


def get_custom_intent():
    """获取自定义Intent结果"""
    print("\n请输入Intent结果（JSON格式）:")
    print("示例:")
    print(json.dumps({
        "intent": "calibration",
        "model_name": "gr4j",
        "basin_id": "01013500",
        "time_period": {
            "train": ["2000-01-01", "2010-12-31"],
            "test": ["2011-01-01", "2015-12-31"]
        },
        "algorithm": "SCE_UA",
        "missing_info": [],
        "clarifications_needed": [],
        "confidence": 0.95
    }, indent=2, ensure_ascii=False))

    print("\n输入JSON（可以多行，以空行结束）:")
    lines = []
    while True:
        line = input()
        if line.strip() == "":
            break
        lines.append(line)

    json_str = "\n".join(lines)

    try:
        intent_result = json.loads(json_str)
        return intent_result
    except json.JSONDecodeError as e:
        print(f"❌ JSON解析失败: {str(e)}")
        return None


def test_config_agent(intent_result: dict):
    """测试ConfigAgent"""
    from hydroagent.agents.config_agent import ConfigAgent
    from hydroagent.core.llm_interface import create_llm_interface

    # 创建ConfigAgent
    workspace_dir = project_root / "results" / "test_config_agent" / datetime.now().strftime("%Y%m%d_%H%M%S")
    workspace_dir.mkdir(parents=True, exist_ok=True)

    llm = create_llm_interface('ollama', 'qwen3:8b')
    config_agent = ConfigAgent(llm_interface=llm, workspace_dir=workspace_dir)

    # 准备输入
    input_data = {
        "success": True,
        "intent_result": intent_result
    }

    # 处理
    print("\n⚙️  正在生成配置...")
    result = config_agent.process(input_data)

    return result


def main():
    """主函数"""
    print_banner()

    test_count = 0
    while True:
        try:
            show_preset_menu()
            choice = input("\n请选择 (0-5, q退出): ").strip()

            if choice.lower() == 'q':
                print("\n再见！👋")
                break

            if choice == "0":
                # 自定义Intent
                intent_result = get_custom_intent()
                if intent_result is None:
                    continue
            else:
                # 预设Intent
                presets = get_preset_intents()
                if choice not in presets:
                    print("❌ 无效选择，请重试")
                    continue

                preset = presets[choice]
                print(f"\n选择: {preset['name']}")
                intent_result = preset['intent_result']

            test_count += 1

            # 显示Intent结果
            print_intent_result(intent_result)

            # 测试ConfigAgent
            result = test_config_agent(intent_result)

            # 显示结果
            print_config_result(result)

            # 询问是否显示详细配置
            if result.get("success"):
                show_detail = input("\n显示详细配置？(y/n): ").strip().lower()
                if show_detail == 'y':
                    print_detailed_config(result['config'])

                # 询问是否保存配置
                save_config = input("\n保存配置到JSON文件？(y/n): ").strip().lower()
                if save_config == 'y':
                    output_file = project_root / "results" / "test_config_agent" / f"config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    output_file.parent.mkdir(parents=True, exist_ok=True)

                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(result['config'], f, indent=2, ensure_ascii=False)

                    print(f"✅ 配置已保存到: {output_file}")

            input("\n按Enter继续...")

        except KeyboardInterrupt:
            print("\n\n操作被中断，再见！👋")
            break
        except Exception as e:
            print(f"\n❌ 发生错误: {str(e)}")
            import traceback
            traceback.print_exc()
            input("\n按Enter继续...")

    print(f"\n总共测试: {test_count} 次")


if __name__ == "__main__":
    main()

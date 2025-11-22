"""
Author: Claude
Date: 2025-01-22 17:15:00
LastEditTime: 2025-01-22 17:15:00
LastEditors: Claude
Description: Test for InterpreterAgent - LLM-driven config generation
FilePath: \HydroAgent\test\test_interpreter_agent.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set console encoding (Windows compatible)
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from hydroagent.agents.interpreter_agent import InterpreterAgent
from hydroagent.core.llm_interface import create_llm_interface
import logging
from datetime import datetime
import json


def setup_logging():
    """Setup logging for test."""
    logs_dir = Path(__file__).parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)

    log_file = logs_dir / f"test_interpreter_agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding='utf-8')
        ]
    )

    return log_file


def test_config_generation(interpreter, subtask, test_name):
    """Test a single config generation."""
    print("\n" + "="*70)
    print(f"【{test_name}】")
    print("="*70)

    task_id = subtask.get("task_id", "N/A")
    task_type = subtask.get("task_type", "N/A")

    print(f"Task ID:   {task_id}")
    print(f"Task Type: {task_type}")
    print(f"Prompt length: {len(subtask.get('prompt', ''))} chars")
    print()

    # Process
    result = interpreter.process({"subtask": subtask})

    if result.get("success"):
        config = result["config"]

        print(f"✅ SUCCESS - Config generated")
        print()

        # Display config summary
        print("  📋 Configuration Summary:")
        print(f"    Model:     {config.get('model_cfgs', {}).get('model_name', 'N/A')}")
        print(f"    Basins:    {config.get('data_cfgs', {}).get('basin_ids', 'N/A')}")
        print(f"    Algorithm: {config.get('training_cfgs', {}).get('algorithm_name', 'N/A')}")

        train_period = config.get('data_cfgs', {}).get('train_period', ['N/A', 'N/A'])
        print(f"    Train:     {train_period[0]} to {train_period[1]}")

        # Algorithm params
        algo_params = config.get('training_cfgs', {}).get('algorithm_params', {})
        print(f"    Algo params: {len(algo_params)} parameters")

        # Validation check
        data_cfgs_ok = "data_cfgs" in config
        model_cfgs_ok = "model_cfgs" in config
        training_cfgs_ok = "training_cfgs" in config

        print()
        print(f"  ✅ data_cfgs:     {'OK' if data_cfgs_ok else 'MISSING'}")
        print(f"  ✅ model_cfgs:    {'OK' if model_cfgs_ok else 'MISSING'}")
        print(f"  ✅ training_cfgs: {'OK' if training_cfgs_ok else 'MISSING'}")

        # Show full config (truncated)
        print()
        print("  📄 Full Config (first 500 chars):")
        config_str = json.dumps(config, indent=2, ensure_ascii=False)
        print(f"  {config_str[:500]}...")

    else:
        print(f"❌ FAILED: {result.get('error', 'Unknown error')}")

        if "validation_errors" in result:
            print(f"  Validation errors:")
            for error in result["validation_errors"]:
                print(f"    - {error}")


def main():
    """Main test function."""
    import argparse

    parser = argparse.ArgumentParser(description='InterpreterAgent Test')
    parser.add_argument('--backend', type=str, default='ollama',
                       choices=['ollama', 'api'],
                       help='LLM backend (default: ollama)')
    parser.add_argument('--model', type=str, default=None,
                       help='Model name')
    args = parser.parse_args()

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║        InterpreterAgent Test - 配置生成测试              ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    # Setup logging
    log_file = setup_logging()
    print(f"\n📝 Logs: {log_file}")

    # Load config
    try:
        from configs import definitions_private as config
    except ImportError:
        from configs import definitions as config

    # Create LLM interface
    print(f"\n正在初始化LLM接口 (backend: {args.backend})...")

    if args.backend == 'ollama':
        model = args.model or 'qwen3:8b'
        llm = create_llm_interface('ollama', model)
        print(f"✅ LLM接口初始化完成 (Ollama: {model})")
    else:
        api_key = getattr(config, 'OPENAI_API_KEY', None)
        base_url = getattr(config, 'OPENAI_BASE_URL', None)

        if not api_key:
            print("❌ API key未配置，请设置configs/definitions_private.py")
            return

        model = args.model or 'qwen-turbo'
        llm = create_llm_interface('openai', model,
                                  api_key=api_key,
                                  base_url=base_url)
        print(f"✅ LLM接口初始化完成 (API: {model})")

    # Create InterpreterAgent
    workspace_dir = Path(__file__).parent.parent / "test_workspace"
    workspace_dir.mkdir(exist_ok=True)

    interpreter = InterpreterAgent(llm_interface=llm, workspace_dir=workspace_dir)
    print("✅ InterpreterAgent初始化完成\n")

    # ========================================================================
    # Test Cases
    # ========================================================================

    # Test 1: Simple calibration task
    test_config_generation(
        interpreter,
        subtask={
            "task_id": "task_1",
            "task_type": "calibration",
            "description": "Calibrate XAJ model on basin 01013500",
            "prompt": """
## 任务：水文模型率定

请生成hydromodel配置字典，用于率定水文模型。

**要求**:
1. 使用统一配置格式（unified format）
2. 配置应包含 data_cfgs, model_cfgs, training_cfgs 三个部分
3. 确保所有必需字段都已填写
4. 算法参数应根据模型复杂度调整

**输出**: 完整的配置字典（JSON格式）

### 任务参数

- **model_name**: xaj
- **basin_id**: 01013500
- **algorithm**: SCE_UA
- **time_period**: {'train': ['1985-10-01', '1995-09-30'], 'test': ['2005-10-01', '2014-09-30']}
- **extra_params**: {}
- **auto_evaluate**: True
""",
            "parameters": {
                "model_name": "xaj",
                "basin_id": "01013500",
                "algorithm": "SCE_UA",
                "time_period": {
                    "train": ["1985-10-01", "1995-09-30"],
                    "test": ["2005-10-01", "2014-09-30"]
                },
                "extra_params": {},
                "auto_evaluate": True
            },
            "dependencies": []
        },
        test_name="测试1 - 简单率定任务 (XAJ + SCE_UA)"
    )

    # Test 2: GR4J model
    test_config_generation(
        interpreter,
        subtask={
            "task_id": "task_2",
            "task_type": "calibration",
            "description": "Calibrate GR4J model on basin 01013500",
            "prompt": """
## 任务：水文模型率定

请生成hydromodel配置字典，用于率定GR4J模型。

### 任务参数

- **model_name**: gr4j
- **basin_id**: 01013500
- **algorithm**: GA
- **time_period**: {'train': ['1990-01-01', '2000-12-31'], 'test': ['2001-01-01', '2010-12-31']}
- **extra_params**: {'generations': 200}
- **auto_evaluate**: True
""",
            "parameters": {
                "model_name": "gr4j",
                "basin_id": "01013500",
                "algorithm": "GA",
                "time_period": {
                    "train": ["1990-01-01", "2000-12-31"],
                    "test": ["2001-01-01", "2010-12-31"]
                },
                "extra_params": {"generations": 200},
                "auto_evaluate": True
            },
            "dependencies": []
        },
        test_name="测试2 - GR4J模型率定 (GR4J + GA)"
    )

    # Test 3: Custom data
    test_config_generation(
        interpreter,
        subtask={
            "task_id": "task_3",
            "task_type": "calibration",
            "description": "Calibrate with custom data",
            "prompt": """
## 任务：使用自定义数据率定

请生成hydromodel配置字典，使用自定义数据路径。

### 任务参数

- **model_name**: xaj
- **basin_id**: my_basin
- **algorithm**: SCE_UA
- **data_source_type**: custom
- **data_source_path**: D:/my_data
- **time_period**: {'train': ['1985-10-01', '1995-09-30'], 'test': ['2005-10-01', '2014-09-30']}
- **auto_evaluate**: True
""",
            "parameters": {
                "model_name": "xaj",
                "basin_id": "my_basin",
                "algorithm": "SCE_UA",
                "data_source_type": "custom",
                "data_source_path": "D:/my_data",
                "time_period": {
                    "train": ["1985-10-01", "1995-09-30"],
                    "test": ["2005-10-01", "2014-09-30"]
                },
                "auto_evaluate": True
            },
            "dependencies": []
        },
        test_name="测试3 - 自定义数据路径"
    )

    print("\n" + "="*70)
    print("✅ 所有测试完成!")
    print("="*70)
    print(f"\n📝 完整日志: {log_file}")


if __name__ == "__main__":
    main()

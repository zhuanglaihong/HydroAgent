# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HydroAgent is an intelligent hydrological model calibration system built with LangChain. It uses workflow-based AI agents to automatically calibrate hydrological model parameters based on existing models and data. The system integrates RAG (Retrieval-Augmented Generation) for knowledge-enhanced workflow generation.

## Development Environment Setup

### Dependencies Management
```bash
# Install uv package manager
pip install uv

# Sync dependencies
uv sync

# Activate virtual environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac
```

### Model Setup
```bash
# Install Ollama from https://ollama.ai/
# List available models
ollama list

# Download required models
ollama pull qwen3:8b
ollama pull granite3-dense:8b
```

## Common Commands

### Running the Agent
```bash
# Interactive mode with RAG enabled (default)
python scripts/run_agent.py

# Disable RAG for basic mode
python scripts/run_agent.py --no-rag

# Debug mode with detailed logs
python scripts/run_agent.py --debug

# Single query mode
python scripts/run_agent.py --query "率定并评估GR4J模型"

# Specify model
python scripts/run_agent.py --model qwen-turbo

# Or use the installed command (after installation)
hydroagent
hydroagent --no-rag
hydroagent --query "率定GR4J模型"
```

### Testing

**重要**: 所有测试都应将日志保存到 `logs/` 目录，便于问题追踪和性能分析。

```bash
# Run basic tool tests
python test/test_basic_tools.py

# Test RAG system integration
python test/test_rag_agent_integration.py

# Test workflow generation
python test/test_new_workflow_generator.py

# Integration tests
python test/run_integration_test.py

# Test individual components
python test/test_individual_tools.py

# Ollama诊断测试
python test/test_ollama_diagnosis.py

# LLM性能对比测试
python test/test_llm_performance.py
```

#### 测试日志规范

**所有测试脚本必须遵循以下日志规范**：

```python
# 标准测试日志设置模板
import logging
import time
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 确保logs目录存在
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

# 设置详细日志
log_file = logs_dir / f"test_{test_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)

print(f"日志将保存到: {log_file}")
```

**日志文件命名规范**：
- 格式: `test_{测试名称}_{YYYYMMDD_HHMMSS}.log`
- 示例: `test_ollama_diagnosis_20241001_143052.log`
- 位置: `logs/` 目录
- **重要**: 必须使用年月日时分秒格式，不允许使用时间戳

**纯日志输出模式**（用于长时间运行的诊断测试）：

```python
# 将所有输出重定向到日志文件
import builtins
original_print = builtins.print

def log_print(*args, **kwargs):
    """重定向print到logger"""
    message = ' '.join(str(arg) for arg in args)
    logger.info(message)

builtins.print = log_print

# 只在终端显示关键信息
original_print(f"测试开始，详细输出保存到: {log_file}")

# 测试结束时恢复并显示摘要
builtins.print = original_print
original_print(f"测试完成！详细日志: {log_file}")
```

### RAG System Testing
```bash
# Test RAG system
python workflows/rag_integration_example.py

# Knowledge integration test
python test/test_hydrorag_knowledge_integration.py

# Demo knowledge integration (if available)
python -m hydroagent.knowledge.demo_knowledge_integration
```

## Architecture Overview

The system follows a modular architecture with clear separation of concerns:

### Core Components

1. **hydroagent/** - Main package containing all core functionality
   - **core/** - Core agent implementation
     - `agent.py` - Main HydroAgent class orchestrating all systems
     - `graceful_killer.py` - Signal handling for graceful shutdown

   - **planning/** - Workflow planning layer (formerly builder/)
     - Workflow generation and planning logic
     - Intent recognition and query expansion

   - **execution/** - Workflow execution layer (formerly executor/)
     - Tool execution and workflow orchestration
     - LangChain tool integrations

   - **knowledge/** - RAG knowledge system (formerly hydrorag/)
     - `rag_system.py` - Main RAG interface
     - `document_processor.py` - Document parsing and chunking
     - `embeddings_manager.py` - Ollama embedding model management
     - `vector_store.py` - ChromaDB vector database operations

   - **utils/** - Utility functions and helpers

2. **scripts/** - Entry points and executable scripts
   - `run_agent.py` - Main CLI entry point (formerly Agent.py)
   - Other utility and processing scripts

3. **workflows/** - Workflow orchestration layer (formerly workflow/)
   - `cot_rag_engine.py` - Chain-of-Thought + RAG integration
   - `workflow_assembler.py` - Workflow assembly and validation
   - `instruction_parser.py` - Natural language instruction parsing
   - `workflow_generator_v2.py` - Enhanced workflow generation

4. **hydromcp/** - MCP (Model Context Protocol) integration
   - `server.py` - MCP server implementation
   - `task_handlers.py` - Task execution handlers
   - `tools.py` - Tool definitions and implementations

5. **hydromodel** (External Dependency)
   - Installed via pip from git repository
   - Supports GR1Y, GR2M, GR4J, GR5J, GR6J, and XAJ models
   - Model training and evaluation utilities

### Configuration

- **configs/** - Configuration directory
  - `definitions.py` - Project-wide path and configuration definitions
  - `definitions_private.py` - Private configuration (create manually)
  - `config.py` - Global parameter configuration
- **pyproject.toml** - Project dependencies and metadata

### Data Flow

1. User input → Intent processing → Query expansion
2. RAG system retrieves relevant knowledge from vector database
3. Workflow generator creates execution plan using CoT + RAG
4. Workflow executor runs tools in sequence
5. Results are collected and presented to user

## Key Development Patterns

### Tool Integration
- All tools are LangChain-compatible with standardized interfaces
- Tools support both local execution and MCP server modes
- Error handling and validation at tool level

### RAG Integration
- Documents are processed into chunks and stored in ChromaDB
- Ollama embeddings provide semantic search capabilities
- Knowledge retrieval enhances workflow generation accuracy

### Workflow Generation
- Uses Chain-of-Thought reasoning combined with RAG
- Supports multi-step complex hydrological modeling tasks
- Validates workflow feasibility before execution

### Path Management
- All paths are normalized using `Path` objects
- Configuration paths defined in `configs/definitions.py`
- Support for both absolute and relative path specifications

## Testing Strategy

The project uses a comprehensive testing approach:

- **Unit tests** for individual components
- **Integration tests** for workflow execution
- **RAG system tests** for knowledge retrieval
- **Tool validation tests** for individual tools
- **End-to-end tests** for complete workflows

## Dependencies

Key external dependencies:
- **LangChain** (0.3.26) - AI agent framework
- **Ollama** - Local LLM inference
- **ChromaDB** - Vector database for RAG
- **FastMCP** - Model Context Protocol implementation
- **hydroutils/hydrodatasource/hydromodel** - Custom hydrological libraries

## Supported Tasks

- Hydrological model calibration (GR4J, XAJ, etc.)
- Model performance evaluation
- Data preparation and preprocessing
- Parameter querying and analysis
- Workflow planning and execution

## Global Development Standards and Configuration Management

### Configuration File Structure

**IMPORTANT**: Always follow this configuration hierarchy for maintainability and user-friendliness:

1. **configs/definitions.py** - Public configuration template and fallback values
   - Contains default project paths and configuration structure
   - Imports from definitions_private.py if available
   - Serves as template for users to understand what needs to be configured

2. **configs/definitions_private.py** - Private user-specific configuration
   - Contains actual API keys, local paths, and sensitive information
   - Should be created by users based on definitions.py template
   - Never committed to version control (.gitignore)
   - Used for:
     - API keys (OPENAI_API_KEY, etc.)
     - Local file paths (PROJECT_DIR, DATASET_DIR, RESULT_DIR)
     - Database connections and other sensitive configs

3. **configs/config.py** - Global parameter configuration
   - Centralized location for all adjustable parameters
   - Model parameters, thresholds, and algorithm settings
   - Easy for users to modify without touching code files
   - Examples: chunk_size, top_k, temperature settings, etc.

### File Organization Overview

```
HydroAgent/
├── hydroagent/                # Main package
│   ├── core/                 # Core agent implementation
│   ├── planning/            # Workflow planning (formerly builder/)
│   ├── execution/           # Workflow execution (formerly executor/)
│   ├── knowledge/           # RAG system (formerly hydrorag/)
│   └── utils/               # Utility functions
├── configs/                  # Configuration directory
│   ├── definitions.py       # Public config template
│   ├── definitions_private.py  # Private user config (not in git)
│   └── config.py           # Global parameters
├── scripts/                  # Entry points and executable scripts
│   ├── run_agent.py        # Main CLI entry point
│   └── *.py                # Other utility scripts
├── test/                     # All test files
│   ├── test_*.py            # Unit and integration tests
│   └── __init__.py
├── workflows/                # Workflow orchestration (formerly workflow/)
├── hydromcp/                # MCP integration
├── documents/               # Knowledge base documents
├── pyproject.toml          # Project configuration
└── .gitignore              # Git ignore rules
```

### File Header Requirements

**MANDATORY**: Every new Python file must include a standardized header following the project convention:

```python
"""
Author: [Your Name]
Date: [Creation Date YYYY-MM-DD HH:MM:SS]
LastEditTime: [Last Edit YYYY-MM-DD HH:MM:SS]
LastEditors: [Editor Name]
Description: [Brief description of file purpose]
FilePath: [Relative path from project root]
Copyright (c) 2023-2024 [Project Name]. All rights reserved.
"""
```

### Directory Structure Standards

**CRITICAL**: Always place files in the correct directories:

- **test/** - All test files go here
  - Unit tests: test_[component_name].py
  - Integration tests: test_[system]_integration.py
  - All test files should be executable with proper shebang if needed
  - Test files should import from parent directory using sys.path manipulation

- **scripts/** - All executable scripts and utilities
  - Standalone scripts for specific tasks
  - Utility scripts for data processing, setup, etc.
  - **IMPORTANT**: All run_* scripts (interactive runners) belong here
  - Should be executable and include proper argument parsing
  - Include comprehensive README.md for script descriptions

### Configuration Loading Pattern

**STANDARD PATTERN**: Always use this pattern for configuration loading:

```python
try:
    from configs import definitions_private
    # Load from private configuration
    API_KEY = definitions_private.API_KEY
    PROJECT_DIR = definitions_private.PROJECT_DIR
except ImportError:
    from configs import definitions
    # Fallback to defaults or environment variables
    API_KEY = definitions.API_KEY or os.getenv('API_KEY', 'default_or_placeholder')
    PROJECT_DIR = definitions.PROJECT_DIR or os.getcwd()
```

### Configuration Management Examples

```python
# Standard File Header Example
"""
Author: zhuanglaihong
Date: 2024-09-24 15:30:00
LastEditTime: 2024-09-24 15:30:00
LastEditors: zhuanglaihong
Description: Enhanced RAG system for hydrological knowledge retrieval
FilePath: \HydroAgent\hydroagent\knowledge\rag_system.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

# Correct Configuration Loading
try:
    from configs import definitions_private as config
    API_KEY = config.OPENAI_API_KEY
    PROJECT_DIR = config.PROJECT_DIR
except ImportError:
    from configs import definitions as config
    API_KEY = config.OPENAI_API_KEY  # Will be placeholder
    PROJECT_DIR = config.PROJECT_DIR
```

## File Organization Rules for Claude Code

**MANDATORY**: When creating or moving files, always follow these rules:

1. **Test files** → test/ directory
2. **Scripts and utilities** → scripts/ directory
3. **Configuration templates** → configs/ directory (configs/definitions.py)
4. **Private configs** → configs/ directory (configs/definitions_private.py)
5. **Global parameters** → configs/ directory (configs/config.py)
6. **Core package code** → hydroagent/ directory with appropriate subpackages
7. **Include standard headers** in all new Python files
8. **Use proper imports** and path management

**Configuration Priority Order**:
1. configs/definitions_private.py (user-specific, not in git)
2. configs/definitions.py (project defaults and templates)
3. configs/config.py (adjustable parameters)
4. Environment variables (fallback)
5. Hard-coded defaults (last resort)

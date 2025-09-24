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
python Agent.py

# Disable RAG for basic mode
python Agent.py --disable-rag

# Debug mode with detailed logs
python Agent.py --debug

# Single query mode
python Agent.py --query "率定并评估GR4J模型"

# Specify model
python Agent.py --model qwen3:8b

# MCP service mode (requires server)
python hydromcp/run_server.py  # In separate terminal
python Agent.py --mcp-mode service
```

### Testing
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
```

### RAG System Testing
```bash
# Test RAG system
python workflow/rag_integration_example.py

# Knowledge integration test
python test/test_hydrorag_knowledge_integration.py

# Demo knowledge integration
python hydrorag/demo_knowledge_integration.py
```

## Architecture Overview

The system follows a modular architecture with clear separation of concerns:

### Core Components

1. **Agent.py** - Main entry point and orchestrator
   - Handles command-line arguments and user interaction
   - Integrates workflow generation with RAG system
   - Supports both interactive and single-query modes

2. **workflow/** - Workflow orchestration layer
   - `cot_rag_engine.py` - Chain-of-Thought + RAG integration
   - `workflow_assembler.py` - Workflow assembly and validation
   - `instruction_parser.py` - Natural language instruction parsing
   - `workflow_generator_v2.py` - Enhanced workflow generation

3. **hydrorag/** - RAG knowledge system
   - `rag_system.py` - Main RAG interface
   - `document_processor.py` - Document parsing and chunking
   - `embeddings_manager.py` - Ollama embedding model management
   - `vector_store.py` - ChromaDB vector database operations

4. **hydromcp/** - MCP (Model Context Protocol) integration
   - `server.py` - MCP server implementation
   - `task_handlers.py` - Task execution handlers
   - `tools.py` - Tool definitions and implementations

5. **hydromodel/** - Hydrological models
   - Supports GR1Y, GR2M, GR4J, GR5J, GR6J, and XAJ models
   - Model training and evaluation utilities

6. **hydrotool/** - Tool execution layer
   - `langchain_tool.py` - LangChain tool integrations
   - `workflow_executor.py` - Workflow execution engine
   - `ollama_config.py` - Ollama configuration management

### Configuration

- **definitions.py** - Project-wide path and configuration definitions
- **definitions_private.py** - Private configuration (create manually)
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
- Configuration paths defined in `definitions.py`
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

1. **definitions.py** - Public configuration template and fallback values
   - Contains default project paths and configuration structure
   - Imports from definitions_private.py if available
   - Serves as template for users to understand what needs to be configured

2. **definitions_private.py** - Private user-specific configuration
   - Contains actual API keys, local paths, and sensitive information
   - Should be created by users based on definitions.py template
   - Never committed to version control (.gitignore)
   - Used for:
     - API keys (OPENAI_API_KEY, etc.)
     - Local file paths (PROJECT_DIR, DATASET_DIR, RESULT_DIR)
     - Database connections and other sensitive configs

3. **config.py** (root level) - Global parameter configuration
   - Centralized location for all adjustable parameters
   - Model parameters, thresholds, and algorithm settings
   - Easy for users to modify without touching code files
   - Examples: chunk_size, top_k, temperature settings, etc.

### File Organization Overview

```
HydroAgent/
├── definitions.py              # Public config template
├── definitions_private.py      # Private user config (not in git)
├── config.py                  # Global parameters (create if needed)
├── test/                      # All test files
│   ├── test_*.py             # Unit and integration tests
│   └── __init__.py
├── script/                   # All executable scripts
│   ├── *.py                  # Utility and processing scripts
│   └── README.md            # Script documentation
├── hydrorag/                # RAG system package
├── workflow/               # Workflow orchestration
├── hydromcp/              # MCP integration
└── [other packages]/      # Additional modules
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

- **script/** - All executable scripts and utilities
  - Standalone scripts for specific tasks
  - Utility scripts for data processing, setup, etc.
  - Should be executable and include proper argument parsing
  - Include comprehensive README.md for script descriptions

### Configuration Loading Pattern

**STANDARD PATTERN**: Always use this pattern for configuration loading:

```python
try:
    import definitions_private
    # Load from private configuration
    API_KEY = definitions_private.API_KEY
    PROJECT_DIR = definitions_private.PROJECT_DIR
except ImportError:
    # Fallback to defaults or environment variables
    API_KEY = os.getenv('API_KEY', 'default_or_placeholder')
    PROJECT_DIR = os.getcwd()
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
FilePath: \HydroAgent\hydrorag\rag_system.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

# Correct Configuration Loading
try:
    import definitions_private as config
    API_KEY = config.OPENAI_API_KEY
    PROJECT_DIR = config.PROJECT_DIR
except ImportError:
    import definitions as config
    API_KEY = config.OPENAI_API_KEY  # Will be placeholder
    PROJECT_DIR = config.PROJECT_DIR
```

## File Organization Rules for Claude Code

**MANDATORY**: When creating or moving files, always follow these rules:

1. **Test files** → test/ directory
2. **Scripts and utilities** → script/ directory
3. **Configuration templates** → root directory (definitions.py)
4. **Private configs** → root directory (definitions_private.py)
5. **Global parameters** → root directory (config.py)
6. **Include standard headers** in all new Python files
7. **Use proper imports** and path management

**Configuration Priority Order**:
1. definitions_private.py (user-specific, not in git)
2. definitions.py (project defaults and templates)
3. config.py (adjustable parameters)
4. Environment variables (fallback)
5. Hard-coded defaults (last resort)

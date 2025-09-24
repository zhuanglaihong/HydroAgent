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
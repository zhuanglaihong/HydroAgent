"""
Author: zhuanglaihong
Date: 2025-07-21 14:54:24
LastEditTime: 2025-07-28 16:24:08
Description: LangChain Agent for Hydrological Modeling
FilePath: tool/langchain_agent.py
Copyright: Copyright (c) 2021-2024 zhuanglaihong. All rights reserved.
"""

import os
import sys
from pathlib import Path

repo_path = Path(os.path.abspath(__file__)).parent.parent
sys.path.append(str(repo_path))

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnablePassthrough

# Import our hydrological model tools
from tool.langchain_tool import get_hydromodel_tools, HydroModelTools

# Import Ollama configuration
from tool.ollama_config import (
    create_ollama_llm_with_config,
    create_tool_supported_llm,
    ollama_config,
)

# Import custom paths
from definitions import DATASET_DIR, RESULT_DIR, PARAM_RANGE_FILE


def create_hydromodel_agent(model_name="granite3-dense:8b", verbose=False):
    """Create a hydrological model agent using local Ollama"""

    # Get tools
    tools = get_hydromodel_tools()
    if not tools:
        print("❌ No hydrological model tools available")
        return None

    if verbose:
        print(f"✅ Loaded {len(tools)} tools:")
        for tool in tools:
            print(f"  - {tool.name}: {tool.description}")

    # Create Ollama LLM with tool support
    model_config = ollama_config.get_model_config(model_name)
    if "granite" in model_name.lower():
        model_config.update(
            {
                "temperature": 0.1,
                "top_p": 0.8,
                "num_ctx": 8192,
            }
        )
        if verbose:
            print(f"🔧 Applied optimized config for {model_name}")

    llm = ChatOllama(model=model_name, **model_config)

    # Create prompt template with the successful universal prompt
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """IMPORTANT: You are an assistant that can ONLY get information by calling tools. You have NO knowledge of your own.

You have these tools available:
1. get_model_params - for questions about model parameters, configurations, or "what is" questions
2. prepare_data - for questions about data preparation, processing, or data-related tasks  
3. calibrate_model - for questions about model training, calibration, or optimization
4. evaluate_model - for questions about model evaluation, performance, or metrics

CRITICAL RULES:
1. ALWAYS call a tool first before answering
2. NEVER provide information from your own knowledge
3. ONLY respond with information from the tool's response
4. Choose the RIGHT tool based on the user's question

TOOL SELECTION GUIDE:
- "parameters", "what is", "model info" → get_model_params
- "prepare", "data", "process" → prepare_data
- "calibrate", "train", "optimize" → calibrate_model  
- "evaluate", "performance", "metrics" → evaluate_model

When you need to call a tool, you MUST use this format:
<|tool_call|>{{"type":"function","function":{{"name":"TOOL_NAME","arguments":{{"param":"value"}}}}}}

If you try to answer without calling a tool first, you are making a mistake.

Remember: ALWAYS call the appropriate tool first, then explain the results.""",
            ),
            ("human", "{input}"),
            ("assistant", "{agent_scratchpad}"),
        ]
    )

    # Create agent
    agent = create_openai_tools_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=verbose,
        handle_parsing_errors=True,
        max_iterations=5,
        return_intermediate_steps=True,
        early_stopping_method="force",
    )

    return agent_executor


def run_hydromodel_workflow():
    """Run complete hydrological model workflow"""
    print("=== Hydrological Model Workflow Example (Local Ollama) ===")

    agent = create_hydromodel_agent(verbose=True)
    if not agent:
        print("❌ Could not create agent")
        return

    # Example conversations
    conversations = [
        "What are the parameters of gr4j model?",
        "I need to prepare hydrological data from the camels_11532500 folder in the data directory",
        "Please calibrate a gr4j model with default parameters",
        "Evaluate the calibrated model",
    ]

    for i, message in enumerate(conversations, 1):
        print(f"\n--- Conversation {i} ---")
        print(f"User: {message}")

        try:
            response = agent.invoke({"input": message})
            print(f"Assistant: {response['output']}")
        except Exception as e:
            print(f"❌ Execution failed: {e}")


def interactive_chat():
    """Interactive chat with the hydrological model assistant"""
    print("=== Interactive Hydrological Model Assistant (Local Ollama) ===")
    print("Enter 'quit' to exit")

    agent = create_hydromodel_agent()
    if not agent:
        print("❌ Could not create agent")
        return

    while True:
        try:
            user_input = input("\nYou: ").strip()

            if user_input.lower() in ["quit", "exit"]:
                print("Goodbye!")
                break

            if not user_input:
                continue

            print("Assistant is thinking...")
            response = agent.invoke({"input": user_input})
            print(f"Assistant: {response['output']}")

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")


def check_ollama_status():
    """Check Ollama status"""
    print("=== Ollama Status Check ===")

    if ollama_config.check_service():
        print("✅ Ollama service is running")

        models = ollama_config.get_available_models()
        if models:
            print(f"📋 Available models: {', '.join(models)}")

            selected_model = ollama_config.select_best_model()
            if selected_model:
                print(f"🎯 Recommended model: {selected_model}")

                config = ollama_config.get_model_config(selected_model)
                print(f"⚙️ Model configuration: {config}")

                if ollama_config.test_model(selected_model):
                    print("✅ Model test passed")
                else:
                    print("❌ Model test failed")
        else:
            print("❌ No available models found")
            print("Please run: ollama pull granite3-dense:8b")
    else:
        print("❌ Ollama service is not running")
        print("Please follow these steps to start Ollama:")
        print("1. Download and install Ollama: https://ollama.ai/")
        print("2. Start Ollama service")
        print("3. Download model: ollama pull granite3-dense:8b")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Hydrological Model LangChain Agent (Local Ollama)"
    )
    parser.add_argument(
        "--mode",
        choices=["workflow", "chat", "status"],
        default="workflow",
        help="Run mode",
    )

    args = parser.parse_args()

    if args.mode == "workflow":
        run_hydromodel_workflow()
    elif args.mode == "chat":
        interactive_chat()
    elif args.mode == "status":
        check_ollama_status()

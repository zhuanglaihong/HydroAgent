"""
Author: zhuanglaihong 
Date: 2025-11-20 22:00:00
LastEditTime: 2025-11-20 22:00:00
LastEditors: zhuanglaihong
Description: Interactive script to test IntentAgent and ConfigAgent integration
FilePath: \\HydroAgent\\scripts\\run_intent_agent_interactive.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import sys
import logging
import time
import json
import argparse
import os
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set console encoding (Windows compatible)
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Ensure logs directory exists
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

# Setup logging
log_file = logs_dir / f"interactive_agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


def print_banner():
    """Print welcome banner."""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                   HydroAgent Interactive                     ║
║                   Intent → Config → Runner                   ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)
    print(f"Log file: {log_file}")
    print()


def print_separator(char="─", length=60):
    """Print a separator line."""
    print(char * length)


def format_time(seconds):
    """Format time in seconds."""
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    else:
        return f"{seconds/60:.1f}min"


def print_intent_result(result: dict, elapsed_time: float):
    """Pretty print intent analysis result."""
    print_separator("═")
    print("【Intent Analysis Result】")
    print_separator()

    # Success status
    success = result.get("success", False)
    status_icon = "✅" if success else "❌"
    print(f"Status: {status_icon} {'SUCCESS' if success else 'FAILED'}")
    print(f"Time: {format_time(elapsed_time)}")
    print()

    if not success:
        print(f"Error: {result.get('error', 'Unknown error')}")
        print_separator("═")
        return

    # Intent result
    intent_result = result.get("intent_result", {})

    # Core fields
    print(f"Intent:     {intent_result.get('intent', 'N/A').upper()}")
    print(f"Model:      {intent_result.get('model_name', 'N/A')}")
    print(f"Basin:      {intent_result.get('basin_id', 'N/A')}")
    print(f"Algorithm:  {intent_result.get('algorithm', 'N/A')}")
    print(f"Confidence: {intent_result.get('confidence', 0.0):.2f}")

    # Extra parameters
    extra_params = intent_result.get('extra_params', {})
    if extra_params:
        print(f"\nExtra Params:")
        for key, value in extra_params.items():
            print(f"  {key}: {value}")

    print()

    # Time period
    time_period = intent_result.get('time_period')
    if time_period:
        print("Time Period:")
        if isinstance(time_period, dict):
            if train := time_period.get('train'):
                print(f"  Train: {train[0]} to {train[1]}")
            if test := time_period.get('test'):
                print(f"  Test:  {test[0]} to {test[1]}")
        print()

    # Missing info
    missing_info = intent_result.get('missing_info', [])
    if missing_info:
        print(f"Missing Info: {', '.join(missing_info)}")

    # Clarifications
    clarifications = intent_result.get('clarifications_needed', [])
    if clarifications:
        print("Clarifications Needed:")
        for i, clarification in enumerate(clarifications, 1):
            print(f"  {i}. {clarification}")
        print()

    # Extension task info
    if intent_result.get('task_type'):
        print(f"Task Type: {intent_result['task_type']}")
        if desc := intent_result.get('task_description'):
            print(f"Description: {desc}")
        print()

    print_separator("═")


def print_config_result(result: dict, elapsed_time: float):
    """Pretty print config generation result."""
    print_separator("═")
    print("【Config Generation Result】")
    print_separator()

    # Success status
    success = result.get("success", False)
    status_icon = "✅" if success else "❌"
    print(f"Status: {status_icon} {'SUCCESS' if success else 'FAILED'}")
    print(f"Time: {format_time(elapsed_time)}")
    print()

    if not success:
        print(f"Error: {result.get('error', 'Unknown error')}")
        if validation_errors := result.get('validation_errors'):
            print("Validation Errors:")
            for error in validation_errors:
                print(f"  - {error}")
        print_separator("═")
        return

    # Config summary
    if summary := result.get('config_summary'):
        print(summary)

    print_separator("═")


def print_json_config(config: dict):
    """Print config as formatted JSON."""
    print_separator("─")
    print("【Config Dict (JSON)】")
    print_separator("─")
    print(json.dumps(config, indent=2, ensure_ascii=False))
    print_separator("─")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='HydroAgent Interactive: Test IntentAgent and ConfigAgent pipeline'
    )
    parser.add_argument(
        '--backend',
        type=str,
        default='api',
        choices=['ollama', 'openai', 'api'],
        help='LLM backend to use (default: ollama)'
    )
    parser.add_argument(
        '--model',
        type=str,
        default=None,
        help='Model name (default: qwen3:8b for ollama, qwen-turbo for api)'
    )
    parser.add_argument(
        '--api-key',
        type=str,
        default=None,
        help='API key (read from OPENAI_API_KEY env if not provided)'
    )
    parser.add_argument(
        '--base-url',
        type=str,
        default=None,
        help='API base URL (for OpenAI-compatible APIs like Qwen)'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=30,
        help='Request timeout in seconds (default: 30)'
    )
    parser.add_argument(
        '--max-retries',
        type=int,
        default=2,
        help='Maximum retry attempts (default: 2)'
    )
    return parser.parse_args()


def load_config():
    """Load configuration from definitions files."""
    try:
        from configs import definitions_private as config
    except ImportError:
        from configs import definitions as config

    return {
        'api_key': getattr(config, 'OPENAI_API_KEY', None),
        'base_url': getattr(config, 'OPENAI_BASE_URL', None),
    }


def create_llm(args):
    """Create LLM interface based on arguments."""
    from hydroagent.core.llm_interface import create_llm_interface

    backend = args.backend
    if backend == 'api':
        backend = 'openai'  # 'api' is alias for 'openai'

    # Load config from definitions files
    config = load_config()

    # Determine model name
    if args.model:
        model_name = args.model
    else:
        # Default models
        if backend == 'ollama':
            model_name = 'qwen3:8b'
        else:
            model_name = 'qwen-turbo'

    # Create LLM interface
    if backend == 'ollama':
        llm = create_llm_interface(
            'ollama',
            model_name,
            timeout=args.timeout,
            max_retries=args.max_retries
        )
        return llm, f"Ollama ({model_name})"

    elif backend == 'openai':
        # Get API key (priority: CLI args > config file > environment variable)
        api_key = args.api_key or config.get('api_key') or os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError(
                "API key not provided. Please:\n"
                "  1. Set it in configs/definitions_private.py (OPENAI_API_KEY), or\n"
                "  2. Use --api-key argument, or\n"
                "  3. Set OPENAI_API_KEY environment variable"
            )

        # Get base URL (priority: CLI args > config file)
        base_url = args.base_url or config.get('base_url')

        # Create OpenAI interface
        kwargs = {'api_key': api_key}
        if base_url:
            kwargs['base_url'] = base_url

        llm = create_llm_interface('openai', model_name, **kwargs)

        # Show config source in description
        api_source = "CLI" if args.api_key else ("config" if config.get('api_key') else "env")
        return llm, f"OpenAI ({model_name}) [API from {api_source}]"

    else:
        raise ValueError(f"Unsupported backend: {backend}")


def main():
    """Main interactive loop."""
    # Parse arguments
    args = parse_args()

    print_banner()

    # Initialize agents
    print("Initializing agents...")
    try:
        from hydroagent.agents.intent_agent import IntentAgent
        from hydroagent.agents.config_agent import ConfigAgent

        # Create LLM interface
        llm, llm_desc = create_llm(args)
        print(f"✅ LLM backend: {llm_desc}")

        # Create agents
        workspace_dir = project_root / "results" / datetime.now().strftime("%Y%m%d_%H%M%S")
        workspace_dir.mkdir(parents=True, exist_ok=True)

        intent_agent = IntentAgent(llm_interface=llm)
        config_agent = ConfigAgent(llm_interface=llm, workspace_dir=workspace_dir)

        print(f"✅ IntentAgent initialized")
        print(f"✅ ConfigAgent initialized")
        print(f"✅ Workspace: {workspace_dir}")
        print()

    except Exception as e:
        print(f"❌ Failed to initialize agents: {str(e)}")
        logger.error(f"Initialization failed", exc_info=True)
        return

    print_separator("═")
    print("Ready! Enter your queries below.")
    print("Commands:")
    print("  'quit' or 'exit' - Exit the program")
    print("  'clear' - Clear screen")
    print("  'help' - Show help")
    print_separator("═")
    print()

    # Main loop
    query_count = 0
    while True:
        try:
            # Get user input
            print(f"\n[Query #{query_count + 1}]")
            query = input("You: ").strip()

            if not query:
                continue

            # Handle commands
            if query.lower() in ['quit', 'exit', 'q']:
                print("\nGoodbye! 👋")
                break

            if query.lower() == 'clear':
                import os
                os.system('cls' if os.name == 'nt' else 'clear')
                print_banner()
                continue

            if query.lower() == 'help':
                print("\nAvailable commands:")
                print("  quit/exit/q - Exit the program")
                print("  clear - Clear screen")
                print("  help - Show this help")
                print("\nExample queries:")
                print("  率定GR4J模型，流域01013500")
                print("  Calibrate XAJ model for basin camels_11532500")
                print("  评估GR5J模型的性能")
                print("  帮我画一下流域的降雨径流过程线")
                continue

            query_count += 1
            print()

            # Step 1: Intent Analysis
            print("🔍 [Step 1/2] Analyzing intent...")
            intent_start = time.time()

            try:
                intent_result = intent_agent.process({"query": query})
                intent_elapsed = time.time() - intent_start

                print_intent_result(intent_result, intent_elapsed)

                if not intent_result.get("success"):
                    continue

            except Exception as e:
                intent_elapsed = time.time() - intent_start
                print(f"❌ Intent analysis failed: {str(e)}")
                logger.error(f"Intent analysis failed", exc_info=True)
                continue

            # Step 2: Config Generation
            print("\n⚙️  [Step 2/2] Generating configuration...")
            config_start = time.time()

            try:
                config_result = config_agent.process(intent_result)
                config_elapsed = time.time() - config_start

                print_config_result(config_result, config_elapsed)

                if config_result.get("success"):
                    # Ask if user wants to see full config
                    show_config = input("\nShow full config dict? (y/n): ").strip().lower()
                    if show_config == 'y':
                        print_json_config(config_result['config'])

                    # Summary
                    total_time = intent_elapsed + config_elapsed
                    print(f"\n✅ Total time: {format_time(total_time)}")
                    print(f"   - Intent: {format_time(intent_elapsed)}")
                    print(f"   - Config: {format_time(config_elapsed)}")

                    # Ready for next step
                    print("\n✅ Ready for RunnerAgent!")
                    print(f"   Config can be passed directly to hydromodel.calibrate()")

            except Exception as e:
                config_elapsed = time.time() - config_start
                print(f"❌ Config generation failed: {str(e)}")
                logger.error(f"Config generation failed", exc_info=True)
                continue

        except KeyboardInterrupt:
            print("\n\nInterrupted by user. Goodbye! 👋")
            break
        except Exception as e:
            print(f"\n❌ Unexpected error: {str(e)}")
            logger.error(f"Unexpected error", exc_info=True)

    print(f"\nTotal queries processed: {query_count}")
    print(f"Log saved to: {log_file}")


if __name__ == "__main__":
    main()

"""
Author: Claude & zhuanglaihong
Date: 2025-11-21 15:30:00
LastEditTime: 2025-11-21 15:30:00
LastEditors: Claude
Description: Interactive HydroAgent system - complete 4-agent pipeline
             交互式HydroAgent系统 - 完整的4-Agent管道
FilePath: \HydroAgent\scripts\run_hydro_agent.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import sys
import logging
import argparse
import time
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
log_file = logs_dir / f"hydro_agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
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
║                      HydroAgent System                       ║
║          Intelligent Hydrological Model Calibration          ║
║                                                              ║
║    Intent → Config → Runner → Developer (4-Agent Pipeline)  ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)
    print(f"Log file: {log_file}")
    print()


def print_separator(char="─", length=70):
    """Print a separator line."""
    print(char * length)


def format_time(seconds):
    """Format time."""
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    else:
        return f"{seconds/60:.1f}min"


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='HydroAgent Interactive System - Complete 4-Agent Pipeline'
    )
    parser.add_argument(
        'query',
        type=str,
        nargs='?',
        default=None,
        help='Query to run (optional, if not provided will enter interactive mode)'
    )
    parser.add_argument(
        '--backend',
        type=str,
        default='ollama',
        choices=['ollama', 'openai', 'api'],
        help='LLM backend (default: ollama)'
    )
    parser.add_argument(
        '--model',
        type=str,
        default=None,
        help='Model name (default: qwen3:8b for ollama, qwen-turbo for api)'
    )
    parser.add_argument(
        '--mock',
        action='store_true',
        help='Use mock mode (bypass hydromodel execution)'
    )
    parser.add_argument(
        '--no-progress',
        action='store_true',
        help='Disable hydromodel progress display'
    )
    parser.add_argument(
        '--no-code-gen',
        action='store_true',
        help='Disable code generation in DeveloperAgent'
    )
    parser.add_argument(
        '--workspace',
        type=str,
        default=None,
        help='Workspace root directory (default: results/)'
    )
    return parser.parse_args()


def print_result(result: dict, elapsed_time: float):
    """Print pipeline result."""
    print_separator("═")
    print("【Pipeline Result】")
    print_separator()

    # Success status
    success = result.get("success", False)
    status_icon = "✅" if success else "❌"
    print(f"Status: {status_icon} {'SUCCESS' if success else 'FAILED'}")
    print(f"Time: {format_time(elapsed_time)}")
    print(f"Session: {result.get('session_id', 'N/A')}")
    print(f"Workspace: {result.get('workspace', 'N/A')}")
    print()

    if not success:
        print(f"Error: {result.get('error', 'Unknown error')}")
        print_separator("═")
        return

    # Summary
    if summary := result.get('summary'):
        print("Summary:")
        print_separator("─")
        print(summary)
        print_separator("─")

    # Detailed results (optional)
    show_details = input("\nShow detailed results? (y/n): ").strip().lower()
    if show_details == 'y':
        print("\n【Detailed Results】")
        print_separator()

        # Intent
        intent_data = result.get('intent', {}).get('intent_result', {})
        print(f"Intent: {intent_data.get('intent', 'N/A')}")
        print(f"Model: {intent_data.get('model_name', 'N/A')}")
        print(f"Basin: {intent_data.get('basin_id', 'N/A')}")
        print()

        # Execution metrics
        execution_data = result.get('execution', {}).get('result', {})
        if metrics := execution_data.get('metrics'):
            print("Metrics:")
            for key, value in metrics.items():
                print(f"  {key}: {value}")
            print()

        # Analysis
        analysis_data = result.get('analysis', {}).get('analysis', {})
        if analysis_data:
            print(f"Quality: {analysis_data.get('quality', 'N/A')}")
            if recs := analysis_data.get('recommendations'):
                print("Recommendations:")
                for i, rec in enumerate(recs, 1):
                    print(f"  {i}. {rec}")

    print_separator("═")


def run_single_query(agent, query: str):
    """Run a single query."""
    print_separator("═")
    print(f"Query: {query}")
    print_separator("═")
    print()

    print("🚀 Processing query through 4-Agent pipeline...")
    start_time = time.time()

    try:
        result = agent.run(query)
        elapsed_time = time.time() - start_time

        print_result(result, elapsed_time)
        return result

    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"❌ Pipeline failed: {str(e)}")
        logger.error(f"Pipeline failed", exc_info=True)
        return {"success": False, "error": str(e)}


def run_interactive(agent):
    """Run interactive mode."""
    print_separator("═")
    print("Interactive Mode - Enter your queries below.")
    print("Commands:")
    print("  'quit' or 'exit' - Exit the program")
    print("  'clear' - Clear screen")
    print("  'help' - Show help")
    print("  'history' - Show conversation history")
    print("  'workspace' - Show current workspace")
    print_separator("═")
    print()

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
                print("  history - Show conversation history")
                print("  workspace - Show current workspace")
                print("\nExample queries:")
                print("  率定GR4J模型，流域01013500")
                print("  评估XAJ模型在流域11532500的表现")
                print("  Calibrate GR5J for basin camels_01013500")
                continue

            if query.lower() == 'history':
                history = agent.get_history()
                print(f"\nConversation history ({len(history)} messages):")
                print_separator("─")
                for i, msg in enumerate(history[-10:], 1):  # Show last 10
                    role = msg['role']
                    content = msg['content'][:100]  # Truncate long messages
                    print(f"{i}. [{role}] {content}...")
                print_separator("─")
                continue

            if query.lower() == 'workspace':
                workspace = agent.get_workspace()
                print(f"\nCurrent workspace: {workspace}")
                continue

            query_count += 1
            run_single_query(agent, query)

        except KeyboardInterrupt:
            print("\n\nInterrupted by user. Goodbye! 👋")
            break
        except Exception as e:
            print(f"\n❌ Unexpected error: {str(e)}")
            logger.error(f"Unexpected error", exc_info=True)

    print(f"\nTotal queries processed: {query_count}")
    print(f"Log saved to: {log_file}")


def main():
    """Main function."""
    args = parse_args()

    print_banner()

    # Initialize HydroAgent
    print("Initializing HydroAgent system...")

    try:
        from hydroagent import HydroAgent

        # Determine workspace
        workspace_root = Path(args.workspace) if args.workspace else project_root / "results"

        # Create agent
        agent = HydroAgent(
            backend=args.backend,
            model=args.model,
            workspace_root=workspace_root,
            show_progress=not args.no_progress,
            enable_code_gen=not args.no_code_gen
        )

        model_desc = args.model or ("qwen3:8b" if args.backend == "ollama" else "qwen-turbo")
        print(f"✅ HydroAgent initialized")
        print(f"   Backend: {args.backend} ({model_desc})")
        print(f"   Workspace: {workspace_root}")
        if args.mock:
            print(f"   Mode: MOCK (hydromodel bypassed)")
        print()

        # Start session
        session_id = agent.start_session()
        print(f"✅ Session started: {session_id}\n")

        # Apply mock if requested
        if args.mock:
            from unittest.mock import Mock
            MOCK_RESULT = {
                "best_params": {"x1": 350.0, "x2": 0.5, "x3": 100.0, "x4": 2.0},
                "metrics": {"NSE": 0.85, "RMSE": 2.5, "KGE": 0.82, "PBIAS": 5.2}
            }
            agent.orchestrator.runner_agent._run_calibration = Mock(return_value=MOCK_RESULT)
            agent.orchestrator.runner_agent._run_evaluation = Mock(return_value=MOCK_RESULT)

    except Exception as e:
        print(f"❌ Failed to initialize HydroAgent: {str(e)}")
        logger.error(f"Initialization failed", exc_info=True)
        return 1

    # Run query or interactive mode
    if args.query:
        # Single query mode
        result = run_single_query(agent, args.query)
        return 0 if result.get("success") else 1
    else:
        # Interactive mode
        run_interactive(agent)
        return 0


if __name__ == "__main__":
    sys.exit(main())

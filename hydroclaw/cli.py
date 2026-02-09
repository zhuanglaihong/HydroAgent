"""
Author: HydroClaw Team
Date: 2026-02-08
Description: CLI entry point for HydroClaw.
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="HydroClaw - LLM-driven hydrological model calibration agent"
    )
    parser.add_argument("query", nargs="?", help="Query to process (interactive mode if omitted)")
    parser.add_argument("--config", "-c", default=None, help="Path to config.json")
    parser.add_argument("--workspace", "-w", default=None, help="Working directory for results")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    parser.add_argument("--log-file", default=None, help="Log file path")

    args = parser.parse_args()

    # Setup logging
    _setup_logging(args.verbose, args.log_file)

    # Determine workspace
    workspace = Path(args.workspace) if args.workspace else Path(".")

    # Import here to avoid slow startup for --help
    from hydroclaw.agent import HydroClaw

    agent = HydroClaw(config_path=args.config, workspace=workspace)

    if args.query:
        # Single query mode
        agent.run(args.query)
    else:
        # Interactive mode
        _interactive_loop(agent)


def _interactive_loop(agent):
    """Interactive REPL mode."""
    print("HydroClaw - Hydrological Model Calibration Agent")
    print("Type your query (Chinese or English). Type 'quit' to exit.\n")

    while True:
        try:
            query = input("You> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not query:
            continue
        if query.lower() in ("quit", "exit", "q"):
            print("Bye!")
            break

        try:
            agent.run(query)
        except KeyboardInterrupt:
            print("\n[Interrupted]")
        except Exception as e:
            print(f"\nError: {e}")
            logging.getLogger(__name__).error(f"Error: {e}", exc_info=True)


def _setup_logging(verbose: bool, log_file: str | None):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    handlers = [logging.StreamHandler(sys.stderr)]

    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    else:
        # Default log file
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        handlers.append(logging.FileHandler(logs_dir / f"hydroclaw_{ts}.log", encoding="utf-8"))

    logging.basicConfig(level=level, format=fmt, handlers=handlers)

    # Quiet noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


if __name__ == "__main__":
    main()

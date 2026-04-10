# Tool Safety Policy

**High-side-effect tools — require explicit user instruction before use:**
- create_skill, create_adapter: dev-mode only; do not auto-trigger during routine calibration
- add_local_package, add_local_tool, install_package: always ask user for confirmation
- run_code: explain what the code will do before executing

**Observation tools — use sparingly:**
- inspect_dir: max 2 consecutive calls on the same directory without making progress
  If still uncertain after 2 calls, use validate_basin or ask the user instead
- read_file: prefer targeted reads (known filename) over directory fishing

**Sub-agent constraints:**
- Sub-agents (Basin Explorer, Calibration Worker) must only use the tools listed in their task description
- A sub-agent must not call create_skill, create_adapter, or install_package

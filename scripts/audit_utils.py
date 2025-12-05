"""
Quick script to audit hydroagent/utils/ directory for unused modules
"""
import os
import re
from pathlib import Path

# List of utils modules to check
UTILS_MODULES = [
    'code_generator',
    'code_sandbox',
    'config_validator',
    'data_loader',
    'error_handler',
    'llm_config_reviewer',
    'param_range_adjuster',
    'path_manager',
    'plotting',
    'post_processor',
    'prompt_manager',
    'report_generator',
    'result_parser',
    'schema_validator',
    'session_summary',
    'task_detector'
]

def find_imports(module_name, root_dir='hydroagent'):
    """Find all imports of a given module"""
    count = 0
    files = []

    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Skip __pycache__ and the module itself
        if '__pycache__' in dirpath:
            continue

        for filename in filenames:
            if not filename.endswith('.py'):
                continue

            filepath = os.path.join(dirpath, filename)

            # Skip the module file itself
            if f'{module_name}.py' in filepath:
                continue

            # Read file
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Check for imports
                patterns = [
                    rf'from.*utils.*import.*{module_name}',
                    rf'import.*utils\.{module_name}',
                    rf'from.*utils\.{module_name}',
                ]

                for pattern in patterns:
                    if re.search(pattern, content):
                        count += 1
                        files.append(filepath)
                        break
            except:
                pass

    return count, files

# Run analysis
print("=" * 70)
print("HydroAgent Utils Module Usage Analysis")
print("=" * 70)
print()

used_modules = []
unused_modules = []

for module in UTILS_MODULES:
    count, files = find_imports(module)

    # Filter out __init__.py references
    actual_files = [f for f in files if '__init__.py' not in f]
    actual_count = len(actual_files)

    if actual_count > 0:
        used_modules.append((module, actual_count, actual_files))
        print(f"[+] {module:25s} USED ({actual_count} refs)")
    else:
        unused_modules.append(module)
        print(f"[-] {module:25s} UNUSED")

print()
print("=" * 70)
print(f"Summary: {len(used_modules)} used, {len(unused_modules)} unused")
print("=" * 70)
print()

if unused_modules:
    print("Unused modules (candidates for deletion):")
    for module in unused_modules:
        print(f"  - hydroagent/utils/{module}.py")
    print()

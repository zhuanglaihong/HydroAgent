"""
Quick script to remove emoji from system.py for Windows console compatibility
"""

import re
from pathlib import Path

def remove_emojis(text):
    """Remove emoji and replace with text equivalents"""
    replacements = {
        "⚠️": "[WARNING]",
        "👋": "[BYE]",
        "⏳": "[LOADING]",
        "📡": "[API]",
        "🖥️": "[LOCAL]",
        "🎯": "[INIT]",
        "✅": "[OK]",
        "❌": "[ERROR]",
        "📚": "[FEATURES]",
        "1️⃣": "1.",
        "2️⃣": "2.",
        "3️⃣": "3.",
        "4️⃣": "4.",
        "5️⃣": "5.",
        "6️⃣": "6.",
        "7️⃣": "7.",
        "8️⃣": "8.",
        "9️⃣": "9.",
        "💡": "[TIP]",
        "📖": "[HELP]",
        "🔧": "[ALGORITHMS]",
        "📊": "[METRICS]",
        "🧪": "[TEST]",
        "🌊": "[HYDRO]",
        "🔄": "[PROCESS]",
    }

    for emoji, replacement in replacements.items():
        text = text.replace(emoji, replacement)

    # Remove any remaining emoji using regex
    text = re.sub(r'[^\x00-\x7F\u4e00-\u9fff]+', '', text)

    return text

# Fix system.py
system_file = Path(__file__).parent.parent / "hydroagent" / "system.py"
content = system_file.read_text(encoding='utf-8')
fixed_content = remove_emojis(content)
system_file.write_text(fixed_content, encoding='utf-8')
print(f"Fixed {system_file}")

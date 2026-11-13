"""PostToolUse hook: run pyflakes on a Python file Claude just edited.

Reads the hook payload (JSON) from stdin. On problems prints them to stderr
and exits 2 so Claude sees the report and fixes it; otherwise exits 0.
"""
import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    tool_input = payload.get("tool_input") or {}
    path = tool_input.get("file_path") or (payload.get("tool_response") or {}).get("filePath")
    if not path or not path.endswith(".py") or not Path(path).is_file():
        return 0
    result = subprocess.run(
        [sys.executable, "-m", "pyflakes", path],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    report = (result.stdout + result.stderr).strip()
    if result.returncode != 0 and report:
        print(f"pyflakes found problems in {path}:\n{report}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

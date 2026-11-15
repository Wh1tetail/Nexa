"""PreToolUse hook (Bash / PowerShell): one pytest run at a time.

Every run recreates and fills the shared test database (`<db>_test`), so two
runs at once break each other. When the command starts pytest while another
pytest process is alive (started by Claude, a terminal or an IDE), the call is
blocked (exit code 2; stderr is shown to Claude). Anything else passes, and if
the process list cannot be read the command is allowed rather than blocked.
"""
import json
import os
import re
import subprocess
import sys

# the command runs tests: `python -m pytest ...`, `pytest ...`, `.venv/Scripts/pytest.exe ...`
# (pytest must be the program itself, so `grep pytest file` does not count)
RUNS_PYTEST = re.compile(r"-m\s+pytest\b|(?:^|[;&|(])\s*(?:\S*[\\/])?pytest(?:\.exe)?(?=\s|$|[;&|)])")
# a live process that is a pytest run
IS_PYTEST = re.compile(r"-m\s+pytest\b|(?:^|[\s\"\\/])pytest(?:\.exe)?(?=[\"\s]|$)", re.IGNORECASE)
# help/version calls do not touch the database
HARMLESS = re.compile(r"--version\b|(?:^|\s)(?:-h|--help)\b|--collect-only\b|--co\b")


def running_pytests() -> list[str] | None:
    """'PID  command line' of running pytest processes; None if unknown."""
    try:
        if os.name == "nt":
            script = (
                "Get-CimInstance Win32_Process -Filter \"Name='python.exe' or Name='pytest.exe'\" | "
                "ForEach-Object { \"$($_.ProcessId)`t$($_.CommandLine)\" }"
            )
            out = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True, text=True, timeout=10,
            ).stdout
        else:
            out = subprocess.run(["ps", "-eo", "pid=,args="], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    found = []
    for line in out.splitlines():
        pid, _, cmd = line.strip().replace("\t", " ").partition(" ")
        if pid.isdigit() and int(pid) != os.getpid() and IS_PYTEST.search(cmd) and not HARMLESS.search(cmd):
            found.append(f"{pid}  {cmd.strip()[:160]}")
    return found


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not RUNS_PYTEST.search(command) or HARMLESS.search(command):
        return 0
    active = running_pytests()
    if not active:
        return 0
    print(
        "Blocked: another pytest run is already active, and every run recreates the shared "
        "test database (<db>_test), so two runs at once break each other.\n"
        "Running now:\n  " + "\n  ".join(active) + "\n"
        "Wait for it to finish (its background-task notification), then run the tests again. "
        "If it is stuck, ask the user before stopping it.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())

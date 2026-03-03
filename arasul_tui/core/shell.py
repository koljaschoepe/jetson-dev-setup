from __future__ import annotations

import subprocess


def run_cmd(cmd: str, timeout: int = 4) -> str:
    """Run a shell command and return stripped output."""
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return (proc.stdout or proc.stderr or "").strip()
    except Exception as exc:
        return f"Error: {exc}"

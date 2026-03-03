from __future__ import annotations

from pathlib import Path
import re
import shlex
import subprocess


GITHUB_PATTERN = re.compile(
    r"^(https://github\.com/[\w\-\.]+/[\w\-\.]+(?:\.git)?|git@github\.com:[\w\-\.]+/[\w\-\.]+(?:\.git)?)$"
)


def valid_github_url(url: str) -> bool:
    return bool(GITHUB_PATTERN.match(url.strip()))


def clone_repo(url: str, target: Path, timeout: int = 300) -> tuple[bool, str]:
    target.parent.mkdir(parents=True, exist_ok=True)
    cmd = f"git clone {shlex.quote(url)} {shlex.quote(str(target))}"
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = (proc.stdout or proc.stderr or "").strip()
        return proc.returncode == 0, out or ("clone ok" if proc.returncode == 0 else "clone failed")
    except Exception as exc:
        return False, f"clone error: {exc}"


from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os
import signal
import time
import getpass


LOCK_PATH = Path("/tmp/arasul-tui.lock")


@dataclass
class LockInfo:
    pid: int
    user: str
    started_at: float


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def acquire_soft_lock() -> str | None:
    """Acquire a soft lock; return warning text when another session exists."""
    user = getpass.getuser()
    now = time.time()
    warning = None

    if LOCK_PATH.exists():
        try:
            data = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
            other = LockInfo(
                pid=int(data["pid"]),
                user=str(data["user"]),
                started_at=float(data["started_at"]),
            )
            if _pid_alive(other.pid) and other.pid != os.getpid():
                age = int(now - other.started_at)
                warning = (
                    f"Soft-Lock: aktive Session von {other.user} "
                    f"(PID {other.pid}, seit {age}s)."
                )
        except Exception:
            warning = "Soft-Lock Datei war defekt und wurde ersetzt."

    LOCK_PATH.write_text(
        json.dumps({"pid": os.getpid(), "user": user, "started_at": now}),
        encoding="utf-8",
    )
    return warning


def release_lock() -> None:
    if not LOCK_PATH.exists():
        return
    try:
        data = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        if int(data.get("pid", -1)) == os.getpid():
            LOCK_PATH.unlink(missing_ok=True)
    except Exception:
        pass


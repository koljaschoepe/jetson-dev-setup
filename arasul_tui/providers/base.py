from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
import datetime as dt
import shlex
import subprocess


class Provider(ABC):
    name: str
    binary: str

    @abstractmethod
    def launch_command(self) -> str:
        raise NotImplementedError

    def is_installed(self) -> bool:
        proc = subprocess.run(
            f"command -v {shlex.quote(self.binary)}",
            shell=True,
            check=False,
            capture_output=True,
            text=True,
        )
        return proc.returncode == 0

    def start_tmux_session(self, project: Path) -> tuple[bool, str, str | None]:
        win = f"{self.name}-{dt.datetime.now().strftime('%H%M%S')}"
        full = f"cd {shlex.quote(str(project))} && {self.launch_command()}"

        # Resolve a target session to work both inside and outside a tmux client.
        sess_proc = subprocess.run(
            "tmux list-sessions -F '#S' 2>/dev/null | head -1",
            shell=True,
            check=False,
            capture_output=True,
            text=True,
        )
        session = (sess_proc.stdout or "").strip()
        if not session:
            create = subprocess.run(
                "tmux new-session -d -s arasul-main",
                shell=True,
                check=False,
                capture_output=True,
                text=True,
            )
            if create.returncode != 0:
                out = (create.stdout or create.stderr or "").strip()
                return False, out or "tmux Server konnte nicht gestartet werden.", None
            session = "arasul-main"

        proc = subprocess.run(
            f"tmux new-window -t {shlex.quote(session)} -n {shlex.quote(win)} {shlex.quote(full)}",
            shell=True,
            check=False,
            capture_output=True,
            text=True,
        )
        out = (proc.stdout or proc.stderr or "").strip()
        if proc.returncode != 0:
            return False, out or "tmux Fehler", None
        subprocess.run(f"tmux select-window -t {shlex.quote(session)}:{shlex.quote(win)}", shell=True, check=False)
        target = f"{session}:{win}"
        return True, f"Neue {self.name} Session gestartet: {target}", target


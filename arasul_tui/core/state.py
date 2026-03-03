from __future__ import annotations

import getpass
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_PROJECT_ROOT = Path("/mnt/nvme/projects")


@dataclass
class TuiState:
    user: str = field(default_factory=getpass.getuser)
    active_project: Path | None = None
    active_provider: str | None = None
    active_session_window: str | None = None
    project_root: Path = DEFAULT_PROJECT_ROOT
    first_run: bool = True

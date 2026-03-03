from __future__ import annotations

import getpass
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_PROJECT_ROOT = Path("/mnt/nvme/projects")


@dataclass
class TuiState:
    user: str = field(default_factory=getpass.getuser)
    active_project: Path | None = None
    project_root: Path = DEFAULT_PROJECT_ROOT
    first_run: bool = True

    # Wizard state (set dynamically during wizard flows)
    _wizard_token: str | None = field(default=None, repr=False)
    _wizard_uuid: str | None = field(default=None, repr=False)
    _delete_target: Any = field(default=None, repr=False)

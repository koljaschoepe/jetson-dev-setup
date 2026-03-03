from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

REGISTRY_PATH = Path("~/.config/arasul/projects.yaml").expanduser()


@dataclass
class ProjectRecord:
    name: str
    path: str
    provider_default: str = "claude"
    created_at: str = ""
    git_remote: str | None = None


def _ensure_registry() -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not REGISTRY_PATH.exists():
        REGISTRY_PATH.write_text("projects: []\n", encoding="utf-8")


def load_registry() -> dict[str, list[dict[str, Any]]]:
    _ensure_registry()
    data = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")) or {}
    projects = data.get("projects", [])
    if not isinstance(projects, list):
        projects = []
    return {"projects": projects}


def save_registry(registry: dict[str, list[dict[str, Any]]]) -> None:
    _ensure_registry()
    REGISTRY_PATH.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")


def list_projects() -> list[ProjectRecord]:
    reg = load_registry()
    out: list[ProjectRecord] = []
    for item in reg["projects"]:
        out.append(
            ProjectRecord(
                name=str(item.get("name", "")),
                path=str(item.get("path", "")),
                provider_default=str(item.get("provider_default", "claude")),
                created_at=str(item.get("created_at", "")),
                git_remote=item.get("git_remote"),
            )
        )
    return [p for p in out if p.name and p.path]


def get_project(name: str) -> ProjectRecord | None:
    for rec in list_projects():
        if rec.name == name:
            return rec
    return None


def register_project(
    name: str, path: Path, provider_default: str = "claude", git_remote: str | None = None
) -> ProjectRecord:
    reg = load_registry()
    existing = [p for p in reg["projects"] if p.get("name") == name]
    created = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    record = ProjectRecord(
        name=name,
        path=str(path),
        provider_default=provider_default,
        created_at=created,
        git_remote=git_remote,
    )
    if existing:
        reg["projects"] = [p for p in reg["projects"] if p.get("name") != name]
    reg["projects"].append(asdict(record))
    save_registry(reg)
    return record

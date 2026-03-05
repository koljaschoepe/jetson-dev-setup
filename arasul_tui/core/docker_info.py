from __future__ import annotations

from dataclasses import dataclass

from arasul_tui.core.shell import run_cmd


@dataclass
class Container:
    id: str
    name: str
    image: str
    status: str
    ports: str


def list_containers(all_containers: bool = False) -> list[Container]:
    """List Docker containers. Set all_containers=True to include stopped."""
    flag = "-a" if all_containers else ""
    out = run_cmd(
        f"docker ps {flag} --format '{{{{.ID}}}}|{{{{.Names}}}}|{{{{.Image}}}}|{{{{.Status}}}}|{{{{.Ports}}}}' 2>/dev/null",
        timeout=10,
    )
    if not out or out.startswith("Error"):
        return []

    containers: list[Container] = []
    for line in out.splitlines():
        parts = line.split("|", 4)
        if len(parts) >= 4:
            containers.append(
                Container(
                    id=parts[0][:12],
                    name=parts[1],
                    image=parts[2],
                    status=parts[3],
                    ports=parts[4] if len(parts) > 4 else "",
                )
            )
    return containers


def docker_disk_usage() -> list[tuple[str, str]]:
    """Return Docker disk usage breakdown."""
    out = run_cmd("docker system df 2>/dev/null", timeout=10)
    if not out or out.startswith("Error"):
        return [("Docker", "Not available")]

    rows: list[tuple[str, str]] = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 4:
            type_name = parts[0]
            total = parts[1]
            active = parts[2]
            size = parts[3]
            rows.append((type_name, f"{active}/{total} active, {size}"))
    return rows


def docker_running_count() -> int:
    """Return number of running Docker containers."""
    out = run_cmd("docker ps -q 2>/dev/null | wc -l", timeout=5)
    try:
        return int(out.strip())
    except (ValueError, AttributeError):
        return 0

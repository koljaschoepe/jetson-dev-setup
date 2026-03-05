from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from arasul_tui.core.shell import run_cmd


@dataclass
class SSHKey:
    type: str
    bits: str
    fingerprint: str
    comment: str
    path: str


@dataclass
class AuditItem:
    label: str
    detail: str
    status: str  # "ok", "warn", "fail"


def list_ssh_keys() -> list[SSHKey]:
    """List SSH keys in ~/.ssh/."""
    keys: list[SSHKey] = []
    ssh_dir = Path.home() / ".ssh"
    if not ssh_dir.exists():
        return keys

    for pub in sorted(ssh_dir.glob("*.pub")):
        try:
            content = pub.read_text(encoding="utf-8").strip()
            parts = content.split(None, 2)
            key_type = parts[0] if parts else "unknown"
            comment = parts[2] if len(parts) > 2 else ""

            fp_out = run_cmd(f"ssh-keygen -lf {pub}")
            bits = ""
            fingerprint = ""
            if fp_out and not fp_out.startswith("Error"):
                fp_parts = fp_out.split()
                bits = fp_parts[0] if fp_parts else ""
                fingerprint = fp_parts[1] if len(fp_parts) > 1 else ""

            keys.append(
                SSHKey(
                    type=key_type,
                    bits=bits,
                    fingerprint=fingerprint,
                    comment=comment,
                    path=str(pub),
                )
            )
        except Exception:
            continue

    return keys


def recent_logins(count: int = 10) -> list[str]:
    """Return recent SSH login lines from last/journalctl."""
    out = run_cmd(f"last -n {count} -a 2>/dev/null", timeout=5)
    if out and not out.startswith("Error"):
        lines = [line for line in out.splitlines() if line.strip() and not line.startswith("wtmp")]
        return lines[:count]

    out = run_cmd(f"journalctl -u sshd -n {count} --no-pager 2>/dev/null", timeout=5)
    if out and not out.startswith("Error"):
        return out.splitlines()[:count]

    return ["Login history not available"]


def security_audit() -> list[AuditItem]:
    """Run security checks and return audit items."""
    items: list[AuditItem] = []

    # SSH key-only auth
    sshd_conf = Path("/etc/ssh/sshd_config.d/99-jetson-hardened.conf")
    if sshd_conf.exists():
        content = sshd_conf.read_text(encoding="utf-8", errors="replace")
        if "PasswordAuthentication no" in content:
            items.append(AuditItem("SSH key-only auth", "Password login disabled", "ok"))
        else:
            items.append(AuditItem("SSH key-only auth", "Password login may be enabled", "warn"))
    else:
        passwd_auth = run_cmd("sshd -T 2>/dev/null | grep -i passwordauthentication", timeout=3)
        if "no" in passwd_auth.lower():
            items.append(AuditItem("SSH key-only auth", "Password login disabled", "ok"))
        else:
            items.append(AuditItem("SSH key-only auth", "Password login enabled", "fail"))

    # fail2ban
    f2b = run_cmd("systemctl is-active fail2ban 2>/dev/null")
    if f2b == "active":
        jails = run_cmd("sudo fail2ban-client status 2>/dev/null | grep 'Jail list'", timeout=5)
        detail = jails.split(":", 1)[-1].strip() if ":" in jails else "active"
        items.append(AuditItem("fail2ban active", detail, "ok"))
    else:
        items.append(AuditItem("fail2ban", "Not running", "fail"))

    # UFW firewall
    ufw = run_cmd("sudo ufw status 2>/dev/null | head -1", timeout=5)
    if "active" in ufw.lower():
        rules = run_cmd("sudo ufw status 2>/dev/null | grep -c ALLOW", timeout=5)
        items.append(AuditItem("UFW firewall", f"{rules} rules active" if rules.isdigit() else "Active", "ok"))
    else:
        items.append(AuditItem("UFW firewall", "Inactive", "fail"))

    # Root login
    root_check = run_cmd("sshd -T 2>/dev/null | grep -i permitrootlogin", timeout=3)
    if "no" in root_check.lower():
        items.append(AuditItem("Root login disabled", "PermitRootLogin no", "ok"))
    elif "without-password" in root_check.lower() or "prohibit-password" in root_check.lower():
        items.append(AuditItem("Root login restricted", "Key-only root access", "warn"))
    else:
        items.append(AuditItem("Root login", "May be enabled", "fail"))

    # SSH key algorithm
    ssh_dir = Path.home() / ".ssh"
    if (ssh_dir / "id_ed25519.pub").exists():
        items.append(AuditItem("SSH key algorithm", "Ed25519", "ok"))
    elif (ssh_dir / "id_rsa.pub").exists():
        items.append(AuditItem("SSH key algorithm", "RSA (Ed25519 recommended)", "warn"))
    else:
        items.append(AuditItem("SSH key algorithm", "No key found", "warn"))

    # Unattended upgrades
    ua = run_cmd("systemctl is-active unattended-upgrades 2>/dev/null")
    if ua == "active":
        items.append(AuditItem("Auto security updates", "unattended-upgrades active", "ok"))
    else:
        items.append(AuditItem("Auto security updates", "Not configured", "warn"))

    return items

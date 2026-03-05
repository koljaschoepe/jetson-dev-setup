from __future__ import annotations

from unittest.mock import patch

from arasul_tui.core.security import AuditItem, SSHKey, list_ssh_keys, recent_logins, security_audit


def test_ssh_key_dataclass():
    key = SSHKey(
        type="ssh-ed25519",
        bits="256",
        fingerprint="SHA256:abc",
        comment="user@host",
        path="/home/user/.ssh/id_ed25519.pub",
    )
    assert key.type == "ssh-ed25519"
    assert key.bits == "256"


def test_audit_item_dataclass():
    item = AuditItem(label="SSH key-only auth", detail="Password login disabled", status="ok")
    assert item.status == "ok"
    assert item.label == "SSH key-only auth"


def test_list_ssh_keys_no_ssh_dir():
    with patch("arasul_tui.core.security.Path") as MockPath:
        mock_home = MockPath.home.return_value
        mock_ssh = mock_home.__truediv__.return_value
        mock_ssh.exists.return_value = False
        keys = list_ssh_keys()
    assert keys == []


def test_recent_logins_fallback():
    """Falls back gracefully when commands fail."""
    with patch("arasul_tui.core.security.run_cmd", return_value="Error: command not found"):
        result = recent_logins()
    assert len(result) >= 1


def test_security_audit_returns_items():
    """security_audit returns AuditItem list."""
    with patch("arasul_tui.core.security.run_cmd", return_value=""), patch("arasul_tui.core.security.Path") as MockPath:
        mock_home = MockPath.home.return_value
        mock_ssh = mock_home.__truediv__.return_value
        mock_ssh.exists.return_value = False
        # Mock sshd config path
        mock_conf = MockPath.return_value
        mock_conf.exists.return_value = False
        items = security_audit()
    assert isinstance(items, list)
    for item in items:
        assert isinstance(item, AuditItem)
        assert item.status in ("ok", "warn", "fail")

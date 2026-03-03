from __future__ import annotations

import json
import re
from pathlib import Path

from arasul_tui.core.constants import CLAUDE_JSON

PROFILE = Path.home() / ".profile"
BASHRC = Path.home() / ".bashrc"
TOKEN_VAR = "CLAUDE_CODE_OAUTH_TOKEN"
TOKEN_PREFIX = "sk-ant-oat01-"
_EXPORT_RE = re.compile(r'^export\s+CLAUDE_CODE_OAUTH_TOKEN=".*"', re.MULTILINE)

# .profile is used for the token because .bashrc has a non-interactive guard
# that prevents env vars from loading in non-interactive SSH commands.
_TOKEN_FILES = [PROFILE, BASHRC]


def is_claude_configured() -> bool:
    return _has_token() and _has_account()


def save_claude_auth(token: str, account_uuid: str, email: str) -> None:
    _write_token(token)
    _write_account(account_uuid, email)


def get_auth_env() -> dict[str, str]:
    token = _read_token()
    if token:
        return {TOKEN_VAR: token}
    return {}


def _has_token() -> bool:
    return bool(_read_token())


def _read_token() -> str | None:
    for path in _TOKEN_FILES:
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            continue
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(f"export {TOKEN_VAR}="):
                val = stripped.split("=", 1)[1].strip().strip('"').strip("'")
                if val.startswith(TOKEN_PREFIX):
                    return val
    return None


def _write_token(token: str) -> None:
    export_line = f'export {TOKEN_VAR}="{token}"'

    # Write to .profile (loaded for both interactive and non-interactive shells)
    try:
        text = PROFILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        text = ""

    if _EXPORT_RE.search(text):
        text = _EXPORT_RE.sub(export_line, text)
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        text += f"\n{export_line}\n"

    PROFILE.write_text(text, encoding="utf-8")

    # Also write to .bashrc for interactive shell convenience
    try:
        rc_text = BASHRC.read_text(encoding="utf-8")
    except FileNotFoundError:
        rc_text = ""

    if _EXPORT_RE.search(rc_text):
        rc_text = _EXPORT_RE.sub(export_line, rc_text)
    else:
        if rc_text and not rc_text.endswith("\n"):
            rc_text += "\n"
        rc_text += f"\n{export_line}\n"

    BASHRC.write_text(rc_text, encoding="utf-8")


def _has_account() -> bool:
    try:
        data = json.loads(CLAUDE_JSON.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    acct = data.get("oauthAccount")
    return isinstance(acct, dict) and bool(acct.get("accountUuid"))


def _write_account(account_uuid: str, email: str) -> None:
    try:
        data = json.loads(CLAUDE_JSON.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}

    data["oauthAccount"] = {
        "accountUuid": account_uuid,
        "emailAddress": email,
    }
    data["hasCompletedOnboarding"] = True

    CLAUDE_JSON.write_text(
        json.dumps(data, indent=2) + "\n",
        encoding="utf-8",
    )

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Prompt:
    message: str
    placeholder: str


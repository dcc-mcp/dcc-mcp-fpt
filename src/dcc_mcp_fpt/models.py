"""Small runtime data contracts for ShotGrid diagnostics."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class ShotGridConnectionInfo:
    """Connection information for the current ShotGrid session."""

    url: str
    script_name: str
    authenticated: bool = False
    server_version: Optional[str] = None

    def model_dump(self) -> Dict[str, object]:
        """Return the legacy diagnostics mapping without requiring Pydantic."""
        return asdict(self)

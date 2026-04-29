from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Ticker:
    """KRX ticker — immutable 6-digit code (e.g. '005930' for Samsung Electronics)."""

    code: str

    def __post_init__(self) -> None:
        if not self.code.isdigit() or len(self.code) != 6:
            raise ValueError(f"KRX ticker must be a 6-digit numeric string, got: {self.code!r}")

    @property
    def is_kospi(self) -> bool:
        """Heuristic: codes below 200000 are typically KOSPI."""
        return int(self.code) < 200000

    def __str__(self) -> str:
        return self.code

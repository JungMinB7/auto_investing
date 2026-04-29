from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Money:
    """KRW monetary value — immutable, integer-only (no fractional won)."""

    amount: int   # KRW

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValueError(f"Money amount cannot be negative: {self.amount}")

    def __add__(self, other: "Money") -> "Money":
        return Money(self.amount + other.amount)

    def __sub__(self, other: "Money") -> "Money":
        return Money(self.amount - other.amount)

    def __mul__(self, factor: int | float) -> "Money":
        return Money(int(self.amount * factor))

    def __le__(self, other: "Money") -> bool:
        return self.amount <= other.amount

    def __lt__(self, other: "Money") -> bool:
        return self.amount < other.amount

    def __str__(self) -> str:
        return f"₩{self.amount:,}"

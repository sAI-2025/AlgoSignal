"""Single validation dataclass for scanner parameters.

Used by the form, the API serializer and the management command so the rules exist once
(ARCHITECTURE §4.7, PRD S3 validation table).
"""

from __future__ import annotations

from dataclasses import dataclass

MESSAGES = {
    "short_period": "Short SMA must be a whole number greater than 0.",
    "long_period": "Long SMA must be greater than Short SMA.",
    "lookback_days": "Lookback must be a positive whole number.",
    "max_stocks": "Max stocks must be a positive whole number.",
}


@dataclass(frozen=True)
class ScannerParams:
    short_period: int = 7
    long_period: int = 30
    lookback_days: int = 10
    max_stocks: int = 25

    def errors(self) -> dict[str, str]:
        """Return a field → message map of validation errors (empty when valid)."""
        errors: dict[str, str] = {}
        if self.short_period <= 0:
            errors["short_period"] = MESSAGES["short_period"]
        if self.long_period <= self.short_period:
            errors["long_period"] = MESSAGES["long_period"]
        if self.lookback_days <= 0:
            errors["lookback_days"] = MESSAGES["lookback_days"]
        if self.max_stocks <= 0:
            errors["max_stocks"] = MESSAGES["max_stocks"]
        return errors

    @property
    def is_valid(self) -> bool:
        return not self.errors()

    def fetch_window(self, buffer: int = 10) -> int:
        """Bars to load per company so the first valid SMA never looks like a crossover."""
        return self.long_period + self.lookback_days + buffer

    @classmethod
    def from_mapping(cls, data: dict) -> ScannerParams:
        return cls(
            short_period=int(data.get("short_period", 7)),
            long_period=int(data.get("long_period", 30)),
            lookback_days=int(data.get("lookback_days", 10)),
            max_stocks=int(data.get("max_stocks", 25)),
        )

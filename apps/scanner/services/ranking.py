"""Deterministic ranking of crossover rows (PRD BR-06)."""

from __future__ import annotations

from apps.scanner.services.scanner import ScanRow


def rank_rows(rows: list[ScanRow]) -> list[ScanRow]:
    """Sort by crossover date desc → strength desc → ticker asc."""
    return sorted(
        rows,
        key=lambda row: (
            -row.crossover_date.toordinal(),
            -row.strength,
            row.nse_code,
        ),
    )


def apply_max_stocks(rows: list[ScanRow], max_stocks: int) -> list[ScanRow]:
    """Return at most *max_stocks* rows (one per company is guaranteed upstream)."""
    return rows[:max_stocks]

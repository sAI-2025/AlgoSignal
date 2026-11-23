from dataclasses import dataclass

import pandas as pd

ALIASES = {
    "company_name": ["company name", "name", "company"],
    "nse_code": ["symbol", "nse symbol", "ticker", "code"],
    "sector": ["industry", "sector"],
    "isin": ["isin", "isin code"],
    "series": ["series"],
}

REQUIRED_FIELDS = ("company_name", "nse_code")


@dataclass(frozen=True)
class MappedFrame:
    frame: pd.DataFrame
    missing_required: list[str]


def _normalize(col: str) -> str:
    return " ".join(col.strip().lower().replace("_", " ").split())


def _build_reverse_alias_map() -> dict[str, str]:
    reverse_map: dict[str, str] = {}
    for canonical, alias_list in ALIASES.items():
        for alias in alias_list:
            reverse_map[_normalize(alias)] = canonical
    return reverse_map


def map_columns(frame: pd.DataFrame) -> MappedFrame:
    reverse_map = _build_reverse_alias_map()
    rename_map: dict[str, str] = {}

    for column in frame.columns:
        normalized = _normalize(str(column))
        canonical = reverse_map.get(normalized)
        if canonical:
            rename_map[column] = canonical

    mapped = frame.rename(columns=rename_map)
    missing_required = [field for field in REQUIRED_FIELDS if field not in mapped.columns]

    return MappedFrame(frame=mapped, missing_required=missing_required)

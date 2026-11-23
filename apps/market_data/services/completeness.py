from __future__ import annotations

from datetime import datetime

import pandas as pd
from django.utils import timezone

from apps.core.market_hours import is_candle_complete


def filter_completed_candles(frame: pd.DataFrame, now: datetime | None = None) -> pd.DataFrame:
    if frame.empty:
        return frame

    current = now or timezone.now()
    date_series = pd.to_datetime(frame.index).date
    mask = [is_candle_complete(candle_date, current) for candle_date in date_series]
    return frame.loc[mask]

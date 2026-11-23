from __future__ import annotations

from datetime import datetime

import pandas as pd

from apps.market_data.services.completeness import filter_completed_candles


def test_filter_completed_candles_removes_incomplete_today_bar() -> None:
    frame = pd.DataFrame(
        {
            "close": [100.0, 101.0],
        },
        index=pd.to_datetime(["2026-11-22", "2026-11-23"]),
    )

    result = filter_completed_candles(frame, now=datetime(2026, 11, 23, 15, 30))

    assert len(result.index) == 1
    assert pd.Timestamp("2026-11-22") in result.index

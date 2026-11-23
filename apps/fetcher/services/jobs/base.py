"""A job is a small callable that performs one unit of work for a schedule.

The scheduler decides *whether* to run a job; the job itself decides *how* and returns a
:class:`JobResult`. Jobs never contain provider-specific code — they call ``market_data``
services, which own all provider interaction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class JobContext:
    """Runtime context handed to a job by the scheduler."""

    now: datetime
    batch_size: int = 10
    throttle_seconds: float = 2.0
    universe_index: str = "NIFTY100"
    provider: object | None = None


@dataclass
class JobResult:
    total_items: int = 0
    success_items: int = 0
    failed_items: int = 0
    rows_written: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)
    message: str = ""

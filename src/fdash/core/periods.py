"""Target periods: 2026 | 2026-Q1 | 2026-01 | 2026/27, and frequency conversion."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable

MONTHLY = re.compile(r"^(\d{4})-(\d{2})$")
QUARTERLY = re.compile(r"^(\d{4})-Q([1-4])$")
ANNUAL = re.compile(r"^(\d{4})$")
MARKETING = re.compile(r"^(\d{4})/(\d{2})$")

SEASON = {"M": 12, "Q": 4, "A": 1, "MY": 1}


def frequency_of(period: str) -> str:
    if MONTHLY.match(period):
        return "M"
    if QUARTERLY.match(period):
        return "Q"
    if ANNUAL.match(period):
        return "A"
    if MARKETING.match(period):
        return "MY"
    raise ValueError(f"Unknown period format: {period}")


def shift(period: str, steps: int) -> str:
    """Period `steps` ahead (negative — back) of the same frequency."""
    if m := MONTHLY.match(period):
        index = int(m.group(1)) * 12 + int(m.group(2)) - 1 + steps
        return f"{index // 12:04d}-{index % 12 + 1:02d}"
    if m := QUARTERLY.match(period):
        index = int(m.group(1)) * 4 + int(m.group(2)) - 1 + steps
        return f"{index // 4:04d}-Q{index % 4 + 1}"
    if m := ANNUAL.match(period):
        return f"{int(m.group(1)) + steps:04d}"
    if m := MARKETING.match(period):
        start = int(m.group(1)) + steps
        return f"{start:04d}/{(start + 1) % 100:02d}"
    raise ValueError(f"Unknown period format: {period}")


def season_index(period: str) -> int:
    """Month 0..11 or quarter 0..3; 0 for annual periods."""
    if m := MONTHLY.match(period):
        return int(m.group(2)) - 1
    if m := QUARTERLY.match(period):
        return int(m.group(2)) - 1
    return 0


def parent(period: str, target: str) -> str | None:
    """Period of a lower frequency that contains `period`, e.g. 2026-05 -> 2026-Q2 or 2026."""
    if m := MONTHLY.match(period):
        year, month = int(m.group(1)), int(m.group(2))
        if target == "Q":
            return f"{year:04d}-Q{(month - 1) // 3 + 1}"
        if target == "A":
            return f"{year:04d}"
    if (m := QUARTERLY.match(period)) and target == "A":
        return m.group(1)
    return None


def aggregate_mean(points: Iterable[tuple[str, float]], target: str) -> dict[str, float]:
    """Average of complete sub-periods: 12 months or 4 quarters per year, 3 months per quarter."""
    buckets: dict[str, list[float]] = defaultdict(list)
    source_freq = None
    for period, value in points:
        source_freq = source_freq or frequency_of(period)
        key = parent(period, target)
        if key:
            buckets[key].append(value)
    if source_freq is None:
        return {}
    need = {("M", "A"): 12, ("M", "Q"): 3, ("Q", "A"): 4}.get((source_freq, target))
    if need is None:
        return {}
    return {key: sum(v) / len(v) for key, v in buckets.items() if len(v) == need}

from __future__ import annotations

from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_time(value: int | float | str | None, default: int | None = None) -> int:
    if value is None:
        if default is None:
            raise ValueError("Missing time value")
        return int(default)
    if isinstance(value, (int, float)):
        return int(value)
    s = value.strip()
    if s.isdigit():
        return int(s)
    # Supports ISO datetimes. Naive values are interpreted as local/unspecified timestamps.
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return int(dt.timestamp() * 1_000_000)


def bucket_us(level: str) -> int:
    mapping = {
        "100ms": 100_000,
        "1s": 1_000_000,
        "10s": 10_000_000,
        "1min": 60_000_000,
        "10min": 600_000_000,
        "1h": 3_600_000_000,
        "raw": 0,
    }
    if level not in mapping:
        raise ValueError(f"Unknown pyramid level: {level}")
    return mapping[level]


def choose_level(duration_us: int, target_points: int, levels: list[str]) -> str:
    if target_points <= 0:
        target_points = 2000
    desired = max(1, duration_us // target_points)
    candidates = sorted([(bucket_us(lvl), lvl) for lvl in levels], key=lambda x: x[0])
    chosen = "raw"
    for size, lvl in candidates:
        if size <= desired:
            chosen = lvl
        else:
            break
    return chosen

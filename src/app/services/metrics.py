from __future__ import annotations

import time
from collections import deque
from typing import Any

MAX_LATENCY_SAMPLES = 1000


class MetricsCollector:
    def __init__(self) -> None:
        self._counters: dict[str, int] = {}
        self._latencies: dict[str, deque[float]] = {}
        self._start_time = time.time()

    def increment(self, name: str, value: int = 1) -> None:
        self._counters[name] = self._counters.get(name, 0) + value

    def observe_latency(self, name: str, seconds: float) -> None:
        if name not in self._latencies:
            self._latencies[name] = deque(maxlen=MAX_LATENCY_SAMPLES)
        self._latencies[name].append(seconds)

    def snapshot(self) -> dict[str, Any]:
        latency_stats: dict[str, float] = {}
        for name, values in self._latencies.items():
            if values:
                sorted_vals = sorted(values)
                count = len(sorted_vals)
                latency_stats[f"{name}_avg_ms"] = round(sum(sorted_vals) / count * 1000, 1)
                latency_stats[f"{name}_p95_ms"] = round(sorted_vals[int(count * 0.95)] * 1000, 1)
                latency_stats[f"{name}_count"] = count

        return {
            "uptime_seconds": round(time.time() - self._start_time),
            "counters": dict(self._counters),
            "latencies": latency_stats,
        }

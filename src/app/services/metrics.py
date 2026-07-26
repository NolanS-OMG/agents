from __future__ import annotations

import time
from typing import Any


class MetricsCollector:
    def __init__(self) -> None:
        self._counters: dict[str, int] = {}
        self._latencies: dict[str, list[float]] = {}
        self._start_time = time.time()

    def increment(self, name: str, value: int = 1) -> None:
        self._counters[name] = self._counters.get(name, 0) + value

    def observe_latency(self, name: str, seconds: float) -> None:
        if name not in self._latencies:
            self._latencies[name] = []
        self._latencies[name].append(seconds)

    def snapshot(self) -> dict[str, Any]:
        latency_avgs: dict[str, float] = {}
        for name, values in self._latencies.items():
            if values:
                latency_avgs[f"{name}_avg_ms"] = round(sum(values) / len(values) * 1000, 1)
                latency_avgs[f"{name}_count"] = len(values)

        return {
            "uptime_seconds": round(time.time() - self._start_time),
            "counters": dict(self._counters),
            "latencies": latency_avgs,
        }

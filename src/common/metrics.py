"""Metrics collection and reporting with namespace support."""

import time
from collections import defaultdict
from typing import Dict, List, Optional
from threading import Lock


class MetricsCollector:
    def __init__(self, namespace: str = ""):
        self._lock = Lock()
        self._namespace = namespace
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._timers: Dict[str, float] = {}

    def _ns(self, metric: str) -> str:
        return f"{self._namespace}.{metric}" if self._namespace else metric

    def increment(self, metric: str, value: int = 1) -> None:
        with self._lock:
            self._counters[self._ns(metric)] += value

    def gauge(self, metric: str, value: float) -> None:
        with self._lock:
            self._gauges[self._ns(metric)] = value

    def observe(self, metric: str, value: float) -> None:
        with self._lock:
            self._histograms[self._ns(metric)].append(value)

    def start_timer(self, metric: str) -> None:
        with self._lock:
            self._timers[self._ns(metric)] = time.time()

    def stop_timer(self, metric: str) -> float:
        with self._lock:
            ns_metric = self._ns(metric)
            if ns_metric in self._timers:
                duration = time.time() - self._timers.pop(ns_metric)
                self.observe(metric, duration)
                return duration
            return 0.0

    def snapshot(self) -> Dict:
        with self._lock:
            return {
                "namespace": self._namespace,
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {k: list(v) for k, v in self._histograms.items()},
            }

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._timers.clear()


class NamespacedMetricsCollector:
    """Wraps a MetricsCollector with a fixed prefix namespace."""

    def __init__(self, base: MetricsCollector, namespace: str):
        if not namespace:
            raise ValueError("NamespacedMetricsCollector requires a non-empty namespace")
        self._base = base
        self._namespace = namespace

    def increment(self, metric: str, value: int = 1) -> None:
        self._base.increment(f"{self._namespace}.{metric}", value)

    def gauge(self, metric: str, value: float) -> None:
        self._base.gauge(f"{self._namespace}.{metric}", value)

    def observe(self, metric: str, value: float) -> None:
        self._base.observe(f"{self._namespace}.{metric}", value)

    def start_timer(self, metric: str) -> None:
        self._base.start_timer(f"{self._namespace}.{metric}")

    def stop_timer(self, metric: str) -> float:
        return self._base.stop_timer(f"{self._namespace}.{metric}")

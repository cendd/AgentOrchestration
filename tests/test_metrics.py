"""Tests for metrics collector with namespace support."""
import pytest
from src.common.metrics import MetricsCollector, NamespacedMetricsCollector


class TestMetricsCollector:
    def test_increment_without_namespace(self):
        c = MetricsCollector()
        c.increment("requests")
        snap = c.snapshot()
        assert snap["counters"]["requests"] == 1

    def test_increment_with_namespace(self):
        c = MetricsCollector(namespace="agent1")
        c.increment("requests")
        snap = c.snapshot()
        assert snap["counters"]["agent1.requests"] == 1
        # raw name should not exist
        assert "requests" not in snap["counters"]

    def test_namespaced_agents_dont_conflict(self):
        a = MetricsCollector(namespace="agent_a")
        b = MetricsCollector(namespace="agent_b")
        a.increment("tasks", 5)
        b.increment("tasks", 3)
        snap_a = a.snapshot()
        snap_b = b.snapshot()
        assert snap_a["counters"]["agent_a.tasks"] == 5
        assert snap_b["counters"]["agent_b.tasks"] == 3
        assert "tasks" not in snap_a["counters"]

    def test_gauge(self):
        c = MetricsCollector(namespace="sys")
        c.gauge("memory", 85.5)
        snap = c.snapshot()
        assert snap["gauges"]["sys.memory"] == 85.5

    def test_observe(self):
        c = MetricsCollector(namespace="perf")
        c.observe("latency", 0.5)
        c.observe("latency", 1.2)
        snap = c.snapshot()
        assert len(snap["histograms"]["perf.latency"]) == 2

    def test_timer(self):
        c = MetricsCollector(namespace="perf")
        c.start_timer("request")
        import time
        time.sleep(0.01)
        dur = c.stop_timer("request")
        assert dur > 0
        assert len(c.snapshot()["histograms"]["perf.request"]) == 1

    def test_reset(self):
        c = MetricsCollector(namespace="ns")
        c.increment("count", 10)
        c.reset()
        snap = c.snapshot()
        assert len(snap["counters"]) == 0


class TestNamespacedMetricsCollector:
    def test_namespaced_prefix(self):
        base = MetricsCollector()
        ns = NamespacedMetricsCollector(base, "worker_1")
        ns.increment("jobs")
        snap = base.snapshot()
        assert snap["counters"]["worker_1.jobs"] == 1

    def test_empty_namespace_raises(self):
        base = MetricsCollector()
        with pytest.raises(ValueError):
            NamespacedMetricsCollector(base, "")

    def test_two_namespaced_independent(self):
        base = MetricsCollector()
        a = NamespacedMetricsCollector(base, "worker_a")
        b = NamespacedMetricsCollector(base, "worker_b")
        a.increment("processed", 10)
        b.increment("processed", 5)
        snap = base.snapshot()
        assert snap["counters"]["worker_a.processed"] == 10
        assert snap["counters"]["worker_b.processed"] == 5

from __future__ import annotations

import pytest

from cpstands.metrics import Registry


def test_counter_renders_with_help_type_and_sorted_labels() -> None:
    registry = Registry()
    counter = registry.counter("jobs_total", "Jobs done.", ("kind", "outcome"))
    counter.inc(kind="alert", outcome="ok")
    counter.inc(2, kind="alert", outcome="ok")
    counter.inc(kind="reminder", outcome="error")
    assert registry.render() == (
        "# HELP jobs_total Jobs done.\n"
        "# TYPE jobs_total counter\n"
        'jobs_total{kind="alert",outcome="ok"} 3\n'
        'jobs_total{kind="reminder",outcome="error"} 1\n'
    )


def test_gauge_and_unlabelled_metrics() -> None:
    registry = Registry()
    gauge = registry.gauge("queue_depth", "Depth.")
    gauge.set(4.5)
    assert "queue_depth 4.5\n" in registry.render()
    gauge.set(0)
    assert "queue_depth 0\n" in registry.render()


def test_histogram_buckets_are_cumulative_with_sum_and_count() -> None:
    registry = Registry()
    hist = registry.histogram("lat_seconds", "Latency.", ("method",), buckets=(1.0, 5.0))
    for value in (0.5, 2.0, 2.0, 9.0):
        hist.observe(value, method="get")
    lines = registry.render().splitlines()
    assert 'lat_seconds_bucket{method="get",le="1"} 1' in lines
    assert 'lat_seconds_bucket{method="get",le="5"} 3' in lines
    assert 'lat_seconds_bucket{method="get",le="+Inf"} 4' in lines
    assert 'lat_seconds_sum{method="get"} 13.5' in lines
    assert 'lat_seconds_count{method="get"} 4' in lines
    assert hist.count(method="get") == 4


def test_label_values_are_escaped() -> None:
    registry = Registry()
    counter = registry.counter("odd_total", "Odd.", ("name",))
    counter.inc(name='a"b\\c\nd')
    assert 'odd_total{name="a\\"b\\\\c\\nd"} 1' in registry.render()


def test_wrong_labels_and_negative_increments_are_rejected() -> None:
    registry = Registry()
    counter = registry.counter("x_total", "X.", ("a",))
    with pytest.raises(ValueError, match="expected labels"):
        counter.inc(b="1")
    with pytest.raises(ValueError, match="expected labels"):
        counter.inc()
    with pytest.raises(ValueError, match="only goes up"):
        counter.inc(-1, a="1")


def test_gauge_clear_removes_stale_series() -> None:
    registry = Registry()
    gauge = registry.gauge("chats", "Chats.", ("status",))
    gauge.set(3, status="active")
    gauge.clear()
    gauge.set(1, status="paused")
    text = registry.render()
    assert "active" not in text
    assert 'chats{status="paused"} 1' in text


def test_default_registry_has_the_documented_metrics() -> None:
    from cpstands import metrics

    text = metrics.REGISTRY.render()
    for name in (
        "cpstands_source_requests_total",
        "cpstands_source_request_seconds",
        "cpstands_sends_total",
        "cpstands_send_errors_total",
        "cpstands_reminders_sent_total",
        "cpstands_alert_delivery_latency_seconds",
        "cpstands_standings_age_seconds",
        "cpstands_queue_depth",
        "cpstands_process_uptime_seconds",
        "cpstands_build_info",
    ):
        assert f"# TYPE {name} " in text

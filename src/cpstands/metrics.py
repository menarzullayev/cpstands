"""A small Prometheus-compatible metrics registry (NFR-009): counters, gauges, histograms.

No labels ever carry chat ids or message text (privacy rule NFR-011); labels are method names,
outcomes and error classes only.
"""

from __future__ import annotations

import math
import threading
from collections.abc import Iterable, Mapping, Sequence

type Labels = tuple[tuple[str, str], ...]
type Sample = tuple[str, Labels, float]

_DEFAULT_BUCKETS = (0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0)


def _key(labelnames: Sequence[str], labels: Mapping[str, str]) -> Labels:
    if set(labels) != set(labelnames):
        raise ValueError(f"expected labels {sorted(labelnames)}, got {sorted(labels)}")
    return tuple((name, str(labels[name])) for name in labelnames)


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _format_labels(labels: Labels, extra: Labels = ()) -> str:
    pairs = [*labels, *extra]
    if not pairs:
        return ""
    return "{" + ",".join(f'{k}="{_escape(v)}"' for k, v in pairs) + "}"


def _number(value: float) -> str:
    if math.isinf(value):
        return "+Inf" if value > 0 else "-Inf"
    return repr(float(value)) if value != int(value) else str(int(value))


class _Metric:
    kind = "untyped"

    def __init__(self, name: str, help_text: str, labelnames: Sequence[str] = ()) -> None:
        self.name = name
        self.help = help_text
        self.labelnames = tuple(labelnames)
        self._lock = threading.Lock()

    def samples(self) -> Iterable[Sample]:  # pragma: no cover - overridden
        return ()


class Counter(_Metric):
    kind = "counter"

    def __init__(self, name: str, help_text: str, labelnames: Sequence[str] = ()) -> None:
        super().__init__(name, help_text, labelnames)
        self._values: dict[Labels, float] = {}

    def inc(self, amount: float = 1.0, **labels: str) -> None:
        if amount < 0:
            raise ValueError("a counter only goes up")
        key = _key(self.labelnames, labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + amount

    def value(self, **labels: str) -> float:
        return self._values.get(_key(self.labelnames, labels), 0.0)

    def samples(self) -> Iterable[Sample]:
        with self._lock:
            items = sorted(self._values.items())
        return [(self.name, labels, value) for labels, value in items]


class Gauge(_Metric):
    kind = "gauge"

    def __init__(self, name: str, help_text: str, labelnames: Sequence[str] = ()) -> None:
        super().__init__(name, help_text, labelnames)
        self._values: dict[Labels, float] = {}

    def set(self, value: float, **labels: str) -> None:
        with self._lock:
            self._values[_key(self.labelnames, labels)] = float(value)

    def clear(self) -> None:
        with self._lock:
            self._values.clear()

    def samples(self) -> Iterable[Sample]:
        with self._lock:
            items = sorted(self._values.items())
        return [(self.name, labels, value) for labels, value in items]


class Histogram(_Metric):
    kind = "histogram"

    def __init__(
        self,
        name: str,
        help_text: str,
        labelnames: Sequence[str] = (),
        buckets: Sequence[float] = _DEFAULT_BUCKETS,
    ) -> None:
        super().__init__(name, help_text, labelnames)
        self.buckets = tuple(sorted(buckets))
        self._counts: dict[Labels, list[int]] = {}
        self._sums: dict[Labels, float] = {}
        self._totals: dict[Labels, int] = {}

    def observe(self, value: float, **labels: str) -> None:
        key = _key(self.labelnames, labels)
        with self._lock:
            counts = self._counts.setdefault(key, [0] * len(self.buckets))
            for i, bound in enumerate(self.buckets):
                if value <= bound:
                    counts[i] += 1
            self._sums[key] = self._sums.get(key, 0.0) + value
            self._totals[key] = self._totals.get(key, 0) + 1

    def count(self, **labels: str) -> int:
        return self._totals.get(_key(self.labelnames, labels), 0)

    def samples(self) -> Iterable[Sample]:
        with self._lock:
            keys = sorted(self._counts)
            out: list[Sample] = []
            for key in keys:
                counts = self._counts[key]
                for bound, count in zip(self.buckets, counts, strict=True):
                    out.append(
                        (f"{self.name}_bucket", (*key, ("le", _number(bound))), float(count))
                    )
                total = self._totals[key]
                out.append((f"{self.name}_bucket", (*key, ("le", "+Inf")), float(total)))
                out.append((f"{self.name}_sum", key, self._sums[key]))
                out.append((f"{self.name}_count", key, float(total)))
        return out


class Registry:
    def __init__(self) -> None:
        self._metrics: list[_Metric] = []

    def counter(self, name: str, help_text: str, labelnames: Sequence[str] = ()) -> Counter:
        metric = Counter(name, help_text, labelnames)
        self._metrics.append(metric)
        return metric

    def gauge(self, name: str, help_text: str, labelnames: Sequence[str] = ()) -> Gauge:
        metric = Gauge(name, help_text, labelnames)
        self._metrics.append(metric)
        return metric

    def histogram(
        self,
        name: str,
        help_text: str,
        labelnames: Sequence[str] = (),
        buckets: Sequence[float] = _DEFAULT_BUCKETS,
    ) -> Histogram:
        metric = Histogram(name, help_text, labelnames, buckets)
        self._metrics.append(metric)
        return metric

    def render(self) -> str:
        """Prometheus text exposition format (version 0.0.4)."""
        lines: list[str] = []
        for metric in self._metrics:
            samples = list(metric.samples())
            lines.append(f"# HELP {metric.name} {metric.help}")
            lines.append(f"# TYPE {metric.name} {metric.kind}")
            for name, labels, value in samples:
                lines.append(f"{name}{_format_labels(labels)} {_number(value)}")
        return "\n".join(lines) + "\n"


REGISTRY = Registry()

SOURCE_REQUESTS = REGISTRY.counter(
    "cpstands_source_requests_total", "Source calls by method and outcome.", ("method", "outcome")
)
SOURCE_SECONDS = REGISTRY.histogram(
    "cpstands_source_request_seconds", "Source call duration.", ("method",)
)
SOURCE_ERRORS = REGISTRY.counter(
    "cpstands_source_errors_total", "Failed source calls.", ("source",)
)
SENDS = REGISTRY.counter(
    "cpstands_sends_total", "Messages handed to Telegram by kind and outcome.", ("kind", "outcome")
)
SEND_ERRORS = REGISTRY.counter(
    "cpstands_send_errors_total", "Telegram send failures by kind and class.", ("kind", "class")
)
TELEGRAM_REQUESTS = REGISTRY.counter(
    "cpstands_telegram_requests_total", "Bot API calls by method.", ("method",)
)
REMINDERS_SENT = REGISTRY.counter("cpstands_reminders_sent_total", "Reminders delivered.")
ALERTS_SENT = REGISTRY.counter("cpstands_alerts_sent_total", "Alert messages delivered.")
LIVE_EDITS = REGISTRY.counter("cpstands_live_edits_total", "Live standings edits delivered.")
REMINDER_LATENESS = REGISTRY.histogram(
    "cpstands_reminder_lateness_seconds", "Seconds between a reminder's due time and its send."
)
DELIVERY_LATENCY = REGISTRY.histogram(
    "cpstands_alert_delivery_latency_seconds", "Seconds between an alert's window end and its send."
)
UPTIME = REGISTRY.gauge("cpstands_process_uptime_seconds", "Seconds since the process started.")
STANDINGS_AGE = REGISTRY.gauge(
    "cpstands_standings_age_seconds", "Age of the newest standings copy of a running contest.",
    ("contest",),
)  # fmt: skip
QUEUE_DEPTH = REGISTRY.gauge("cpstands_queue_depth", "Work waiting in a queue.", ("queue",))
CHATS = REGISTRY.gauge("cpstands_chats", "Known chats by status.", ("status",))
SOURCE_STREAK = REGISTRY.gauge(
    "cpstands_source_consecutive_errors", "Consecutive failed calls of a source.", ("source",)
)
SOURCE_PAUSED = REGISTRY.gauge("cpstands_source_paused", "1 while a source is paused.", ("source",))
BUILD_INFO = REGISTRY.gauge(
    "cpstands_build_info", "Always 1; the labels say which build is running.", ("commit", "version")
)

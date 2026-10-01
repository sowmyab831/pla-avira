"""In-process request telemetry (R5).

Counters only — no request bodies, no PII. Path segments that look like ids
are bucketed to keep cardinality bounded. Exposed via GET /api/admin/metrics.
"""
from __future__ import annotations

import re
import threading
import time
from collections import defaultdict, deque
from typing import Any, Dict

_STARTED = time.time()
_lock = threading.Lock()
_requests_total = 0
_errors_total = 0
_status_counts: Dict[str, int] = defaultdict(int)
_path_counts: Dict[str, int] = defaultdict(int)
_path_ms: Dict[str, float] = defaultdict(float)
_latencies = deque(maxlen=2000)  # ring buffer for percentile estimates
_IDISH = re.compile(r"(?:[0-9a-f]{8,}|user_[0-9a-f]+|\d+)")


def _norm_path(path: str) -> str:
    parts = [_IDISH.sub("{id}", seg) for seg in path.split("/")]
    return "/".join(parts)[:120]


def record(method: str, path: str, status: int, elapsed_ms: float) -> None:
    key = f"{method} {_norm_path(path)}"
    with _lock:
        global _requests_total, _errors_total
        _requests_total += 1
        if status >= 500:
            _errors_total += 1
        _status_counts[str(status)] += 1
        _path_counts[key] += 1
        _path_ms[key] += elapsed_ms
        _latencies.append(elapsed_ms)


def snapshot() -> Dict[str, Any]:
    with _lock:
        lat = sorted(_latencies)
        def pct(p: float) -> float:
            if not lat:
                return 0.0
            return round(lat[min(len(lat) - 1, int(len(lat) * p))], 1)
        top = sorted(_path_counts.items(), key=lambda kv: -kv[1])[:25]
        return {
            "uptime_s": round(time.time() - _STARTED, 1),
            "requests_total": _requests_total,
            "errors_5xx": _errors_total,
            "by_status": dict(_status_counts),
            "latency_ms": {"p50": pct(0.50), "p95": pct(0.95), "p99": pct(0.99)},
            "top_endpoints": [
                {"endpoint": k, "count": v, "avg_ms": round(_path_ms[k] / v, 1)}
                for k, v in top
            ],
        }

from collections import defaultdict
from threading import Lock
from typing import Dict, Tuple


_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, float("inf"))
_lock = Lock()
_http_requests: Dict[Tuple[str, str, int], int] = defaultdict(int)
_http_durations: Dict[Tuple[str, str], list] = {}
_ai_operations: Dict[str, int] = defaultdict(int)
_ai_durations: Dict[str, list] = {}


def _observe(histograms: dict, key, seconds: float) -> None:
    state = histograms.setdefault(key, {"count": 0, "sum": 0.0, "buckets": [0] * len(_BUCKETS)})
    state["count"] += 1
    state["sum"] += seconds
    for index, upper_bound in enumerate(_BUCKETS):
        if seconds <= upper_bound:
            state["buckets"][index] += 1


def record_http_request(method: str, route: str, status_code: int, seconds: float) -> None:
    with _lock:
        _http_requests[(method, route, status_code)] += 1
        _observe(_http_durations, (method, route), seconds)


def record_ai_operation(operation: str, milliseconds: float) -> None:
    with _lock:
        _ai_operations[operation] += 1
        _observe(_ai_durations, operation, milliseconds / 1000.0)


def render_metrics() -> str:
    with _lock:
        requests = dict(_http_requests)
        http_durations = {key: {**value, "buckets": list(value["buckets"])} for key, value in _http_durations.items()}
        ai_operations = dict(_ai_operations)
        ai_durations = {key: {**value, "buckets": list(value["buckets"])} for key, value in _ai_durations.items()}

    lines = [
        "# HELP is_platform_http_requests_total Completed HTTP requests.",
        "# TYPE is_platform_http_requests_total counter",
    ]
    for (method, route, status_code), count in sorted(requests.items()):
        lines.append(f'is_platform_http_requests_total{{method="{method}",route="{route}",status="{status_code}"}} {count}')

    lines.extend([
        "# HELP is_platform_http_request_duration_seconds HTTP request duration.",
        "# TYPE is_platform_http_request_duration_seconds histogram",
    ])
    for (method, route), state in sorted(http_durations.items()):
        for index, upper_bound in enumerate(_BUCKETS):
            label = "+Inf" if upper_bound == float("inf") else f"{upper_bound:g}"
            lines.append(f'is_platform_http_request_duration_seconds_bucket{{method="{method}",route="{route}",le="{label}"}} {state["buckets"][index]}')
        lines.append(f'is_platform_http_request_duration_seconds_sum{{method="{method}",route="{route}"}} {state["sum"]:.9f}')
        lines.append(f'is_platform_http_request_duration_seconds_count{{method="{method}",route="{route}"}} {state["count"]}')

    lines.extend([
        "# HELP is_platform_ai_operations_total Completed AI and retrieval operations.",
        "# TYPE is_platform_ai_operations_total counter",
    ])
    for operation, count in sorted(ai_operations.items()):
        lines.append(f'is_platform_ai_operations_total{{operation="{operation}"}} {count}')

    lines.extend([
        "# HELP is_platform_ai_operation_duration_seconds AI and retrieval operation duration.",
        "# TYPE is_platform_ai_operation_duration_seconds histogram",
    ])
    for operation, state in sorted(ai_durations.items()):
        for index, upper_bound in enumerate(_BUCKETS):
            label = "+Inf" if upper_bound == float("inf") else f"{upper_bound:g}"
            lines.append(f'is_platform_ai_operation_duration_seconds_bucket{{operation="{operation}",le="{label}"}} {state["buckets"][index]}')
        lines.append(f'is_platform_ai_operation_duration_seconds_sum{{operation="{operation}"}} {state["sum"]:.9f}')
        lines.append(f'is_platform_ai_operation_duration_seconds_count{{operation="{operation}"}} {state["count"]}')
    return "\n".join(lines) + "\n"

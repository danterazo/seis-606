from __future__ import annotations

from typing import Any

_HEALTH_MAP = {
    "running": "healthy",
    "online": "healthy",
    "ok": "healthy",
    "healthy": "healthy",
    "stopped": "offline",
    "offline": "offline",
    "failed": "failed",
    "error": "failed",
    "degraded": "degraded",
    "warning": "degraded",
    "restarting": "degraded",
    "pending": "unknown",
    "timeout": "unknown",
    "unknown": "unknown",
    "unavailable": "unknown",
}


def classify_health_state(state: str | None) -> str:
    if state is None:
        return "unknown"
    normalized = str(state).strip().lower()
    return _HEALTH_MAP.get(normalized, "unknown")


def workload_health_finding(
    *,
    workload_id: str,
    name: str,
    reported_state: str,
    reason: str | None = None,
    restart_count: int = 0,
    architecture: str | None = None,
    node_id: str | None = None,
) -> dict[str, Any]:
    category = classify_health_state(reported_state)
    message = f"{name} ({workload_id}) is {reported_state}"
    if category == "failed":
        message = f"{name} ({workload_id}) failed"
    elif category == "degraded":
        message = f"{name} ({workload_id}) is degraded"
    elif category == "healthy":
        message = f"{name} ({workload_id}) is healthy"
    elif category == "offline":
        message = f"{name} ({workload_id}) is offline"

    return {
        "workload_id": workload_id,
        "name": name,
        "node_id": node_id,
        "category": category,
        "reported_state": reported_state,
        "reported_reason": reason,
        "restart_count": restart_count,
        "architecture": architecture,
        "message": message,
    }

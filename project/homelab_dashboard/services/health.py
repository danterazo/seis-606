from typing import Any, Dict, Final, Union

_HEALTH_MAP: Final[Dict[str, str]] = {
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

_MESSAGES: Final[Dict[str, str]] = {
    "failed": "{name} ({workload_id}) failed",
    "degraded": "{name} ({workload_id}) is degraded",
    "healthy": "{name} ({workload_id}) is healthy",
    "offline": "{name} ({workload_id}) is offline",
}


def classify_health_state(*, state: Union[str, None]) -> str:
    if state is None:
        return "unknown"
    return _HEALTH_MAP.get(str(state).strip().lower(), "unknown")


def workload_health_finding(
    *,
    workload_id: str,
    name: str,
    reported_state: str,
    reason: Union[str, None] = None,
    restart_count: int = 0,
    architecture: Union[str, None] = None,
    node_id: Union[str, None] = None,
) -> Dict[str, Any]:
    category: str = classify_health_state(state=reported_state)
    template: str = _MESSAGES.get(category, "{name} ({workload_id}) is " + reported_state)

    return {
        "workload_id": workload_id,
        "name": name,
        "node_id": node_id,
        "category": category,
        "reported_state": reported_state,
        "reported_reason": reason,
        "restart_count": restart_count,
        "architecture": architecture,
        "message": template.format(name=name, workload_id=workload_id),
    }

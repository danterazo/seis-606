from typing import Any, Dict

from homelab_dashboard.services.health import classify_health_state, workload_health_finding


def test_classify_health_state_requires_explicit_healthy_values() -> None:
    assert classify_health_state(state="running") == "healthy"
    assert classify_health_state(state="stopped") == "offline"
    assert classify_health_state(state="failed") == "failed"
    assert classify_health_state(state="unknown-state") == "unknown"
    assert classify_health_state(state=None) == "unknown"


def test_workload_health_finding_preserves_reported_reason() -> None:
    finding: Dict[str, Any] = workload_health_finding(
        workload_id="vm-1",
        name="api",
        reported_state="failed",
        reason="Out of memory",
        restart_count=4,
    )

    assert finding["category"] == "failed"
    assert finding["reported_reason"] == "Out of memory"
    assert "api" in finding["message"]


def test_unfamiliar_states_keep_the_reported_value_in_the_message() -> None:
    finding: Dict[str, Any] = workload_health_finding(workload_id="vm-2", name="db", reported_state="hibernating")

    assert finding["category"] == "unknown"
    assert finding["message"] == "db (vm-2) is hibernating"

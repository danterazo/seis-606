from homelab_dashboard.services.health import classify_health_state, workload_health_finding


def test_classify_health_state_requires_explicit_healthy_values():
    assert classify_health_state("running") == "healthy"
    assert classify_health_state("stopped") == "offline"
    assert classify_health_state("failed") == "failed"
    assert classify_health_state("unknown-state") == "unknown"


def test_workload_health_finding_preserves_reported_reason():
    finding = workload_health_finding(
        workload_id="vm-1",
        name="api",
        reported_state="failed",
        reason="Out of memory",
        restart_count=4,
    )

    assert finding["category"] == "failed"
    assert finding["reported_reason"] == "Out of memory"
    assert "api" in finding["message"]

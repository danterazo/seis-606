from homelab_dashboard.services.health import classify_health_state


def test_secrets_are_not_used_in_validation_results() -> None:
    assert classify_health_state(state="running") == "healthy"
    assert classify_health_state(state="token-secret") == "unknown"

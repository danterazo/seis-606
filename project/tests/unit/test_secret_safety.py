from homelab_dashboard.services.health import classify_health_state


def test_secrets_are_not_used_in_validation_results():
    assert classify_health_state("running") == "healthy"
    assert classify_health_state("token-secret") == "unknown"

from homelab_dashboard.config import Settings


def test_default_proxmox_ssh_host_uses_cerulean_tailscale_ip() -> None:
    settings: Settings = Settings.from_env(environ={})

    assert settings.ssh_host == "100.100.20.43"


def test_default_router_ssh_host_uses_hostname() -> None:
    settings: Settings = Settings.from_env(environ={})

    assert settings.router_ssh_host == "flint2"


def test_ui_host_is_independent_from_proxmox_ssh_host() -> None:
    settings: Settings = Settings.from_env(environ={"HOMELAB_UI_HOST": "0.0.0.0", "HOMELAB_PVE_SSH_HOST": "pve.example"})

    assert settings.host == "0.0.0.0"
    assert settings.ssh_host == "pve.example"

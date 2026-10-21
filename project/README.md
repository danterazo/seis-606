# Homelab Dashboard
A status dashboard with explicit guest reboot controls for a Proxmox VE cluster, styled after Frutiger Aero / Y2K desktops. The Homelab Haiku panel
pairs a randomized three-line poem with a cow illustration. Guest tags appear as badges, including VPN badges for tagged LXCs and a hard-drive badge
for NAS-tagged guests. Resource readings come from Proxmox; display profiles, fallback CPU models, and memory descriptions are configured separately.
SSH uses hostnames resolved by the local system.

This app was developed for personal use, and it assumes a trusted LAN environment with no public exposure. As such, it will not properly run if you 
simply clone this repo to your own machine. That's just the nature of this project.


## Run
Install dependencies before the first run with `poetry install`.

In VS Code, open this repository. The `Open Default Terminal Layout` task runs on folder open and starts the dashboard and an interactive Bash
terminal side by side. Allow automatic tasks when VS Code asks. The dashboard task runs `make run`, which starts the development server at
`http://127.0.0.1:8766` and reloads it when Python files change. If the dashboard-preview extension is installed, it opens or reuses the integrated
browser when the server is ready. The task stops any process already using port `8766` before starting; check that port before allowing it to run.

To start it manually from the repository root:

```bash
make run
```

For a direct run without the development reloader, use `poetry run python project/app.py`; it listens on `http://127.0.0.1:8765` by default. Stop
either process with `Ctrl+C`.

| Variable                              | Default              | Purpose                                                |
| :------------------------------------ | :------------------- | :----------------------------------------------------- |
| `HOMELAB_PVE_SSH_HOST`                | `cerulean`           | Proxmox node hostname, address, or SSH alias           |
| `HOMELAB_PVE_SSH_USER`                | `root`               | Account used for Proxmox SSH connections               |
| `HOMELAB_ROUTER_SSH_HOST`             | `samskeyti`          | Router hostname, address, or SSH alias                 |
| `HOMELAB_UI_HOST` / `HOMELAB_UI_PORT` | `127.0.0.1` / `8765` | Direct-run listen address; `make run` uses port `8766` |

### First Connection
Run `make init-ssh-trust` to review configured node and router host keys. Verify each fingerprint through a trusted channel before accepting it. This
does not configure SSH keys; key-based SSH access and local hostname resolution must already work.

## Security
The dashboard has no login (yet). The endpoints it reads expose detailed node, guest, device, lease, and activity-log data. It binds to loopback by 
default; do not expose it to untrusted networks or the public internet. A reverse proxy and HTTPS do not provide authentication.

Guest reboot and log-clear actions have loopback, origin, and app-header checks, but these are not user authentication. SSH uses verified host keys
and key authentication; it defaults to `root` on Proxmox and the router. Use an appropriately restricted account where practical, and never commit
private keys or credentials.

Guest reboot requests are confirmed in the UI and validated against current cluster inventory. A timeout does not establish whether a reboot happened;
check the guest before retrying. A successful response means the command was submitted, not that the guest finished rebooting.

In the near future, this app will be properly reverse proxied with HTTPS and WebAuthn / OAuth2 / Passkey authentication.

## Project Layout
- `project/homelab_dashboard/`: dashboard, data sources, and services
- `project/web/`: browser interface and assets
- `project/tests/`: automated tests
- `project/specs/`: feature design and requirements
- `project/deliverables/`: test results, checklist, and presentation

## Test
From the repository root:

```bash
python3 -m pytest project/tests
make lint
```

`make lint` checks Python and web code without changing files. `make fix` applies supported fixes and formatting, then runs the lint checks.

## Project 1 Deliverables
- [Test log](deliverables/test-log.md) and [automated test results](deliverables/automated-test-results.xml)
- [Preflight checklist](deliverables/preflight-checklist.md)
- [Presentation Slices](deliverables/project-presentation.pptx)
- Current SpecKit artifacts: `project/specs/001-homelab-inventory-dashboard/`

See [app-specs.md](app-specs.md) and `project/specs/` for plans; these describe proposed work, not necessarily implemented features.

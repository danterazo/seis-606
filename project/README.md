# Homelab Dashboard

A read-only status page for a Proxmox VE cluster, styled after Frutiger Aero / Y2K desktops.
Every value on the page comes from Proxmox at request time; nothing is hardcoded.

## Run

```bash
python3 project/app.py
```

Open the printed URL (default `http://127.0.0.1:8765`). The server needs only the Python
standard library and an OpenSSH client.

| Variable                | Default              | Purpose                                    |
| :---------------------- | :------------------- | :----------------------------------------- |
| `HOMELAB_PVE_SSH_HOST`  | `192.168.20.43`      | Host, IP, or SSH alias of any cluster node |
| `HOMELAB_PVE_SSH_USER`  | `root`               | Account used for every connection          |
| `HOMELAB_SSH_TIMEOUT`   | `15`                 | Seconds to wait for Proxmox                |
| `HOMELAB_CACHE_SECONDS` | `10`                 | Minimum seconds between Proxmox queries (one costs ~2 CPU-seconds on a node); the page itself polls every second |
| `HOMELAB_HOST` / `PORT` | `127.0.0.1` / `8765` | Where the dashboard listens                |

### First Connection

Trust Cerulean's host key once, after confirming the fingerprints match:

```bash
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub        # on Cerulean's console
ssh-keyscan -t ed25519 192.168.20.43 | ssh-keygen -lf -  # on this machine
ssh-keyscan -H -t ed25519 192.168.20.43 >> ~/.ssh/known_hosts
```

Connections use `root` by default. To use another account, set `HOMELAB_PVE_SSH_USER`;
a non-root account needs the `PVEAuditor` role to read cluster resources.

## Layout

```text
project/
├── app.py                      entry point
├── server.py                   static files + /api/status
├── web/                        index.html, aero.css, aero.js (type-checked with JSDoc)
└── homelab_dashboard/
    ├── models.py               frozen, typed Node / Guest / ClusterSnapshot
    ├── config.py               settings from the environment
    └── sources/
        ├── base.py             StatusSource protocol and safe error type
        ├── pve_parser.py       pure Proxmox JSON -> models
        └── proxmox_ssh.py      SSH transport
```

## Test

```bash
python3 -m pytest project/tests
python3 -m mypy --strict project/server.py project/homelab_dashboard
```

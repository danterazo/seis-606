# Homelab Dashboard

A read-only status page for a Proxmox VE cluster, styled after Frutiger Aero / Y2K desktops.
Every value on the page comes from Proxmox at request time; nothing is hardcoded.

## Run

```bash
python3 project/app.py
```

Open the printed URL (default `http://127.0.0.1:8765`). The server needs only the Python
standard library and an OpenSSH client.

| Variable | Default | Purpose |
| --- | --- | --- |
| `HOMELAB_PVE_SSH_TARGET` | `192.168.20.43` | Host, SSH alias, or `user@host` of any cluster node |
| `HOMELAB_SSH_TIMEOUT` | `15` | Seconds to wait for Proxmox |
| `HOMELAB_HOST` / `PORT` | `127.0.0.1` / `8765` | Where the dashboard listens |

## How it connects

Each refresh makes one noninteractive SSH connection that runs two read-only calls,
`pvesh get /cluster/resources` and `pvesh get /cluster/status`. It uses this machine's own
SSH configuration, keys, and agent; no password or API token is requested or stored.
Connections are public-key only and always verify the host key.

If Proxmox can't be reached, the page says why instead of showing stale or invented data.

### First connection

Trust Cerulean's host key once, after confirming the fingerprints match:

```bash
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub        # on Cerulean's console
ssh-keyscan -t ed25519 192.168.20.43 | ssh-keygen -lf -  # on this machine
ssh-keyscan -H -t ed25519 192.168.20.43 >> ~/.ssh/known_hosts
```

If the node needs a different account, set `HOMELAB_PVE_SSH_TARGET=user@192.168.20.43`.
A non-root account needs the `PVEAuditor` role to read cluster resources.

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
python3 -m pytest project/tests/unit/test_pve_source.py
```

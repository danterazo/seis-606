# Quickstart Validation Guide

The app is a custom HTML/CSS/JavaScript status page served by Python's
standard-library HTTP server. By default it reads PVE node and VM/LXC status
using this WSL instance's existing OpenSSH setup and read-only `pvesh` queries.

## Prerequisites

- Python 3.14+
- OpenSSH client
- A browser

## Install and run

From the repository root:

```bash
python3 project/app.py
```

Open `http://127.0.0.1:8765`. SSH uses public-key authentication in `BatchMode`;
it does not ask for a password or disable host-key checking. If you have a
configured host alias, set `HOMELAB_PVE_SSH_TARGET` to that alias. For the
manual fallback, run `HOMELAB_STATUS_SOURCE=manual python3 project/app.py`.
If Cerulean expects another account, use an alias or
`user@192.168.20.43`; SSH still uses existing WSL identities.

On first connection, compare the fingerprint from
`ssh-keyscan -t ed25519 192.168.20.43 | ssh-keygen -lf -` with the fingerprint
shown on Cerulean's local console by
`ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`. Only after they match, add
the verified host key with:

```bash
ssh-keyscan -H -t ed25519 192.168.20.43 >> ~/.ssh/known_hosts
```

Never use `StrictHostKeyChecking=no` or accept an unverified key.

## Automated checks

```bash
poetry run pytest project/tests
poetry run ruff check project
poetry run ruff format --check project
```

## Acceptance scenarios

1. Load the page and confirm `LIVE PVE / SSH`, node status, CPU/memory, and VM/
   container counts reflect the PVE response.
2. Confirm offline nodes are shown from the live cluster response.
3. Refresh manually and wait 30 seconds to verify automatic polling.
4. Break SSH access in a test environment and confirm the page shows an explicit
   error instead of falling back to the manual report.
5. Set `HOMELAB_STATUS_SOURCE=manual`; confirm the report is labeled manual and
   unknown values remain unknown.
6. Check desktop and mobile widths for clipped text or horizontal page overflow.

Future work includes per-guest details, status history, and reverse-proxy
base-path support. SSH reads do not modify cluster resources.

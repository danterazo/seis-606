# Quickstart Validation Guide

This guide validates the intended spec-kit feature: a Streamlit dashboard using a read-only Proxmox API token by default and fixtures only when
explicitly selected. It is not a run guide for the evolved SSH-based application currently in `project/`; see [project/README.md](../../README.md) and
the as-built note in [spec.md](spec.md) for that implementation.

## Prerequisites

- Python 3.14+
- Poetry
- A browser
- A Proxmox API token restricted to the read permissions required by the dashboard (for live mode)

## Install and run

From the repository root, install dependencies and start the planned Streamlit application:

```bash
poetry install
poetry run streamlit run project/app.py
```

Open the local URL printed by Streamlit. Configure the variables below through the deployment environment; never commit the token secret.

```text
HOMELAB_STATUS_SOURCE=proxmox
PROXMOX_API_URL=https://proxmox.example/api2/json
PROXMOX_TOKEN_ID=read-only-dashboard@pam!status
PROXMOX_TOKEN_SECRET=<deployment secret>
PROXMOX_VERIFY_TLS=true
PROXMOX_TIMEOUT_SECONDS=10
```

For deterministic test/demo data, select fixture mode explicitly with `HOMELAB_STATUS_SOURCE=mock`. The interface must label that data as mock.
Failure to connect in live mode must not silently select fixtures.

## Automated checks

```bash
poetry run pytest project/tests
poetry run ruff check project
poetry run ruff format --check project
```

## Acceptance scenarios

1. Configure the read-only token and confirm the source label identifies live Proxmox data.
2. Confirm returned node and workload values are source-driven, and that offline nodes retain identity and last-successful timestamps without stale
   values presented as current.
3. Refresh manually and wait 30 seconds to verify the shared refresh path is used by automatic refresh.
4. In a safe test environment, cause a timeout or incomplete response and confirm the dashboard reports the failure without exposing secrets or
   switching to mock data.
5. Explicitly select mock mode and confirm the interface labels fixture data as mock while preserving unknown values.
6. Check desktop and mobile widths and a configured reverse-proxy base path for clipping, routing, and reload behavior.

Inventory management, mutation controls, and automatic remediation remain out of scope for this feature.

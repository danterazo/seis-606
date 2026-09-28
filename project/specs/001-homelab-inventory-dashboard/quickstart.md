# Quickstart Validation Guide

This guide is the implementation target for the MVP. The application source is
created under `project/` during implementation.

## Prerequisites

- Python 3.14+
- Poetry
- A browser
- For live checks: an authorized Proxmox endpoint and a dedicated read-only API
  token with only status-read permissions
- For reverse-proxy checks: Caddy or an equivalent local proxy

## Install and run

From the repository root:

```bash
poetry install
poetry run streamlit run project/app.py
```

The default configuration must select live Proxmox when its required deployment
configuration is present. Never put the token secret in source control or in a
command copied into shell history.

For deterministic demo mode, explicitly select fixtures:

```bash
HOMELAB_STATUS_SOURCE=mock poetry run streamlit run project/app.py
```

The page must visibly label this mode as `Mock data`.

## Automated checks

```bash
poetry run pytest project/tests
poetry run ruff check project
poetry run ruff format --check project
```

Expected result: all unit and contract tests pass, fixture scenarios cover every
required state category, and no lint or formatting errors are reported.

## Acceptance scenarios

1. Start mock mode with multiple nodes and workloads. Confirm every node appears,
   counts are derived from returned data, duplicate workload names stay grouped by
   node, and the source label says `Mock data`.
2. Refresh after changing the fixture workload count. Confirm the new count
   appears without editing application configuration.
3. View healthy, degraded, failed, restarting, offline, pending, timeout,
   incomplete, and unfamiliar-state fixtures. Confirm no unfamiliar or missing
   value is displayed as healthy.
4. Use the ARM VM filter. Confirm every matching VM includes node, identity, and
   reported architecture, and non-matching VMs are absent.
5. Use an empty fixture. Confirm an explicit empty state appears and no fabricated
   node is shown. Use a loading fixture to confirm loading is distinct from empty.
6. Trigger a node failure after a successful observation. Confirm node identity
   and last successful update remain visible, current values are unavailable, and
   the error contains no token or authorization data.
7. Confirm automatic refresh occurs after 30 seconds and the manual control uses
   the same refresh path.
8. Run the app through a configured reverse-proxy path, reload the browser, and
   confirm the dashboard renders and refreshes without root-path assumptions.
9. For live verification, inspect only status endpoints using the dedicated
   read-only token. Confirm no test setup deletes, modifies, or restarts existing
   resources.

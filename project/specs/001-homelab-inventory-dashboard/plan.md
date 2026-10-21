# Implementation Plan: Homelab Status Dashboard

**Branch**: `001-homelab-inventory-dashboard` | **Date**: 2026-09-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-homelab-inventory-dashboard/spec.md`

## Summary

Build the specified read-only Streamlit dashboard around a normalized status-source boundary. Live Proxmox status is the default when configured and
uses a dedicated read-only API token; deterministic fixtures are available only when explicitly selected for tests or demo use. A live-source failure
must remain visible and must not silently switch to fixture data.

This plan describes the intended feature design, not the evolved application currently in `project/`. The implementation's SSH-based sources,
additional status panels, and state-changing controls are recorded in the as-built note in [spec.md](spec.md) and the convergence tasks in
[tasks.md](tasks.md).

## Technical Context

**Language/Version**: Python 3.14+

**Primary Dependencies**: Streamlit for the dashboard, `proxmoxer` for the Proxmox REST API, Pydantic for validated domain models, `pytest` for tests,
and `ruff` for linting and formatting.

**Storage**: No application database. API credentials are supplied by the deployment environment; the app stores no credentials or observation state.

**Testing**: `pytest` unit and source-contract tests for normalization, read-only API behavior, failures, and secret-safe errors, plus Streamlit
integration checks for live, fixture, empty, loading, and unavailable states.

**Target Platform**: Linux server running Streamlit behind Caddy or another reverse proxy; supported desktop and mobile browser viewports.

**Project Type**: Read-only Streamlit browser application.

**Performance Goals**: Render a representative environment of up to 20 nodes and 200 workloads within the dashboard's normal refresh interaction;
complete a refresh and expose offline status within 10 seconds after the check completes.

**Constraints**: Read-only integration only; no mutation endpoints or controls. Never display or log token values. Preserve node identity and last
successful timestamp during failures. Unknown, pending, timed-out, and unfamiliar source states must remain distinguishable. Automatic refresh is
every 30 seconds plus a manual action. The app must work under a reverse-proxy path.

**Scale/Scope**: One operator-facing dashboard, one live Proxmox source, one explicitly selected fixture source, node/workload overview, health
findings, ARM VM filtering, and freshness/connection visibility. Inventory management and system mutations are out of scope.

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Principle                                | Gate                                                                                                                                          | Status    |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | --------- |
| I. Safe and Reversible Operations        | Dashboard exposes status reads only; no mutation paths are planned.                                                                           | PASS      |
| II. MCP-First, Evidence-Based Automation | Verify whether a configured Proxmox MCP provides the required read-only status and freshness data before selecting the source implementation. | CONDITIONAL |
| III. Atomic and Auditable Changes        | No state-changing workflow exists in this MVP, so Discord mutation auditing is not applicable.                                                | PASS      |
| IV. Dynamic, Testable User Experience    | UI renders adapter results dynamically and tests empty, changing, offline, incomplete, and mobile/reverse-proxy behavior.                     | PASS      |
| V. Maintainable, Focused Architecture    | Streamlit UI with small Python domain, source, service, and presentation modules.                                                             | PASS      |

The feature requires read-only Proxmox API-token access but does not require a particular client. Resolve the conditional gate before implementation: use
an available Proxmox MCP if it supplies the required status and freshness data; otherwise use the planned direct REST adapter. In either case, restrict
the source to status reads and the required read-only token permissions.

## Project Structure

### Documentation (this feature)

```text
specs/001-homelab-inventory-dashboard/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── status-source.md
└── tasks.md                 # Created by /speckit-tasks
```

### Source Code (`project/`)

```text
project/
├── app.py                     # application entry point
├── homelab_dashboard/
│   ├── domain.py
│   ├── sources/
│   │   ├── proxmox.py         # read-only API-token integration
│   │   └── fixtures.py        # explicitly selected, labeled test/demo data
│   ├── services/
│   │   ├── health.py
│   │   └── refresh.py
│   └── ui/
│       ├── dashboard.py
│       └── components.py
└── tests/
    ├── unit/
    ├── contract/
    └── integration/
```

**Structure Decision**: Keep the Streamlit entry point in `project/app.py`, domain and source logic under `project/homelab_dashboard/`, and tests
under `project/tests/`. The UI remains independent of source credentials and consumes normalized snapshots so live and fixture sources share the same
validation and rendering path.

## Complexity Tracking

No constitution violations or compensating complexity are planned.

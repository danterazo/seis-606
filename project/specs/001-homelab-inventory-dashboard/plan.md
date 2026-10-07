# Implementation Plan: Homelab Status Dashboard

**Branch**: `001-homelab-inventory-dashboard` | **Date**: 2026-09-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-homelab-inventory-dashboard/spec.md`

## Summary

Build a read-only browser dashboard that gets current PVE cluster resources
through this WSL instance's OpenSSH configuration and identity. The default
source runs noninteractive, public-key-only, read-only `pvesh` commands and
retains strict host-key verification. A clearly labeled operator report is an
explicit fallback, never an automatic substitute for a failed live query.

## Technical Context

**Language/Version**: Python 3.14+

**Primary Dependencies**: Python's standard-library HTTP server and subprocess
OpenSSH client, Pydantic for validated domain models, `pytest` for tests, and
`ruff` for linting and formatting. The browser UI is vanilla HTML, CSS, and
JavaScript.

**Storage**: No application database. OpenSSH configuration, keys, agent, and
known-host entries remain owned by the WSL user; the app stores no credentials
or observation state.

**Testing**: `pytest` unit tests for SSH command safety and PVE resource
normalization, plus browser checks for live status, SSH failures, and manual
report labeling.

**Target Platform**: Linux server running the Python HTTP server behind Caddy or
another reverse proxy; supported desktop and mobile browser viewports.

**Project Type**: Read-only Python-served browser application.

**Performance Goals**: Render a representative environment of up to 20 nodes and
200 workloads within the dashboard's normal refresh interaction; complete a
refresh and expose offline status within 10 seconds after the check completes.

**Constraints**: Read-only integration only; no mutation endpoints or controls.
Never display or log token values. Preserve node identity and last successful
timestamp during failures. Unknown, pending, timed-out, and unfamiliar source
states must remain distinguishable. Automatic refresh is every 30 seconds plus a
manual action. The app must work under a reverse-proxy path.

**Scale/Scope**: One operator-facing dashboard, one live Proxmox source, one
fixture source, node/workload overview, health findings, ARM VM filtering, and
freshness/connection visibility. Inventory management and system mutations are
out of scope.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Safe and Reversible Operations | Dashboard exposes status reads only; no mutation paths are planned. | PASS |
| II. MCP-First, Evidence-Based Automation | Status values originate from the configured source adapter or clearly labeled fixtures; missing values remain unknown. | PASS |
| III. Atomic and Auditable Changes | No state-changing workflow exists in this MVP, so Discord mutation auditing is not applicable. | PASS |
| IV. Dynamic, Testable User Experience | UI renders adapter results dynamically and tests empty, changing, offline, incomplete, and mobile/reverse-proxy behavior. | PASS |
| V. Maintainable, Focused Architecture | Custom HTML/CSS/JavaScript UI with small Python source and server modules. | PASS |

No constitution violations require an exception.

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
├── server.py                  # static UI and read-only JSON endpoint
├── web/
│   ├── index.html
│   ├── console.css
│   └── console.js
├── homelab_dashboard/
│   ├── domain.py
│   ├── sources/
│   │   ├── proxmox_ssh.py     # read-only pvesh over existing SSH setup
│   │   └── operator_report.py # explicitly labeled manual fallback
│   └── services/
└── tests/
    ├── unit/
    └── integration/
```

**Structure Decision**: Keep the browser UI in `project/web/`, the local server
in `project/server.py`, and source adapters under
`project/homelab_dashboard/sources/`. The UI remains independent of source
credentials and receives normalized JSON, keeping fixtures and a future live
Proxmox adapter interchangeable.

## Complexity Tracking

No constitution violations or compensating complexity are planned.

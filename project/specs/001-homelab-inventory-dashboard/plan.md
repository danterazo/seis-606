# Implementation Plan: Homelab Status Dashboard

**Branch**: `001-homelab-inventory-dashboard` | **Date**: 2026-09-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-homelab-inventory-dashboard/spec.md`

## Summary

Build a read-only Streamlit dashboard that aggregates current Proxmox node and
workload status through a source adapter. Live Proxmox data, authenticated with
a dedicated read-only API token, is the default source; deterministic mock data
is available only for tests and explicitly labeled demo mode. The adapter keeps
source details out of the UI and preserves unavailable fields rather than
inferring them. The dashboard refreshes automatically every 30 seconds and also
supports a manual refresh.

## Technical Context

**Language/Version**: Python 3.14+

**Primary Dependencies**: Streamlit for UI, `proxmoxer` for the Proxmox API,
Pydantic for validated domain models, `pytest` for tests, and `ruff` for linting
and formatting. A small refresh helper may use Streamlit's supported rerun
mechanism; no client-side framework is required.

**Storage**: No application database for the MVP. Configuration and secrets come
from deployment environment variables or Streamlit secrets; session state holds
the latest observations only.

**Testing**: `pytest` unit tests for normalization and state classification,
contract tests for source adapters using fixtures, and Streamlit smoke tests for
empty, loading, changing, offline, and mock-labeled states.

**Target Platform**: Linux server running Streamlit behind Caddy or another
reverse proxy; supported desktop and mobile browser viewports.

**Project Type**: Read-only Python web application.

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
| V. Maintainable, Focused Architecture | Streamlit is the default, with small domain, source, and presentation modules. | PASS |

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

### Source Code (repository root)

```text
.
├── app.py
├── homelab_dashboard/
│   ├── domain.py              # Node, Workload, observations, findings, states
│   ├── config.py              # environment/secrets configuration and validation
│   ├── sources/
│   │   ├── base.py            # source protocol and normalized result
│   │   ├── proxmox.py         # read-only Proxmox API adapter
│   │   └── fixtures.py        # deterministic, explicitly mock source
│   ├── services/
│   │   ├── refresh.py         # refresh orchestration and freshness handling
│   │   └── health.py          # source-state normalization and findings
│   └── ui/
│       ├── dashboard.py       # page composition and refresh controls
│       └── components.py      # reusable node/workload/status components
└── tests/
    ├── unit/
    ├── contract/
    └── integration/
```

**Structure Decision**: Use a single Streamlit application rooted in the
Speckit project directory (`project/` in the coursework workspace)
with domain models independent of the UI and source adapters behind a narrow
protocol. This keeps live Proxmox, fixtures, and a future MCP-backed source
interchangeable while keeping the MVP small and testable. The `project/` source
tree does not exist yet and will be created during implementation.

## Complexity Tracking

No constitution violations or compensating complexity are planned.

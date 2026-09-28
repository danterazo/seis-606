---
description: "Actionable implementation tasks for the Homelab Status Dashboard"
---

# Tasks: Homelab Status Dashboard

**Input**: Design documents from `/specs/001-homelab-inventory-dashboard/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, and `quickstart.md`

**Tests**: Tests are included because the plan and quickstart require unit, contract, and Streamlit smoke coverage.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the Python application structure and development tooling.

- [x] T001 Create the application and test directory structure from `project/app.py`, `project/homelab_dashboard/`, and `project/tests/`
- [x] T002 Add Streamlit, proxmoxer, Pydantic, pytest, and ruff dependencies and project commands in `pyproject.toml`
- [x] T003 [P] Configure ruff linting and formatting rules in `pyproject.toml`
- [x] T004 [P] Add safe environment and Streamlit configuration examples in `project/.streamlit/config.toml.example` and `project/.env.example`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Implement shared domain, configuration, source, and refresh boundaries before story work.

**Checkpoint**: Foundation ready; user story implementation can proceed in priority order.

- [x] T005 [P] Define validated Node, Workload, StatusObservation, HealthFinding, and RefreshSnapshot models in `project/homelab_dashboard/domain.py`
- [x] T006 [P] Define source protocol, normalized result, safe source error, and connection-state types in `project/homelab_dashboard/sources/base.py`
- [x] T007 [P] Implement deployment configuration loading and validation for `HOMELAB_STATUS_SOURCE`, Proxmox URL, token ID, token secret, TLS verification, and timeout in `project/homelab_dashboard/config.py`
- [x] T008 [P] Implement state classification and evidence-preserving health finding helpers in `project/homelab_dashboard/services/health.py`
- [x] T009 Implement refresh orchestration, per-node freshness handling, failed-attempt identity retention, current-node replacement, and one in-flight refresh per session in `project/homelab_dashboard/services/refresh.py`
- [x] T010 [P] Add domain and source contract fixtures for healthy, degraded, failed, restarting, offline, pending, timed-out, incomplete, unknown, duplicate-name, ARM, and empty scenarios in `project/tests/fixtures/status_cases.py`
- [x] T011 Add shared test configuration and factories for timezone-aware observations and normalized snapshots in `project/tests/conftest.py`

---

## Phase 3: User Story 1 - View Homelab Overview (Priority: P1) MVP

**Goal**: Show every current node and its dynamically derived workload and health summary in one read-only dashboard.

**Independent Test**: Provide multiple fixture nodes and workloads, open the dashboard, and verify every node appears with its current state, architecture, workload counts, health summary, connection state, and source label.

### Tests for User Story 1

- [x] T012 [P] [US1] Add unit tests for node and workload normalization, derived counts, duplicate workload names by node, and explicit empty versus loading states in `project/tests/unit/test_domain.py`
- [x] T013 [P] [US1] Add fixture-source contract tests for dynamic multi-node snapshots and mock-data labeling in `project/tests/contract/test_fixtures_source.py`
- [x] T014 [P] [US1] Add Streamlit smoke tests for multi-node, changing-count, empty, and loading dashboard states in `project/tests/integration/test_dashboard_overview.py`

### Implementation for User Story 1

- [x] T015 [P] [US1] Implement deterministic, explicitly labeled fixture snapshots and scenario selection in `project/homelab_dashboard/sources/fixtures.py`
- [x] T016 [US1] Implement the dashboard page composition with source label, refresh state, node summaries, and empty/loading handling in `project/homelab_dashboard/ui/dashboard.py`
- [x] T017 [P] [US1] Implement reusable node, workload-count, health-summary, connection, and freshness components in `project/homelab_dashboard/ui/components.py`
- [x] T018 [US1] Wire configuration, source selection, refresh orchestration, and dashboard rendering from `project/app.py`

**Checkpoint**: User Story 1 is independently usable in labeled mock mode and renders current dynamic node data without mutation controls.

---

## Phase 4: User Story 2 - Investigate Workload Health (Priority: P2)

**Goal**: Surface failed, degraded, restarting, unavailable, and ARM-emulating workloads so the operator can find attention-worthy systems quickly.

**Independent Test**: Supply healthy, degraded, failed, restarting, and ARM-emulating workloads and verify classifications, safe reported reasons, grouped identities, and ARM filter results without changing any workload.

### Tests for User Story 2

- [ ] T019 [P] [US2] Add health-classification tests proving only explicit healthy values become healthy and unfamiliar values remain unknown in `project/tests/unit/test_health.py`
- [ ] T020 [P] [US2] Add ARM-filter and repeated-restart tests covering every matching VM and excluding non-ARM workloads in `project/tests/unit/test_workload_filters.py`
- [ ] T021 [P] [US2] Add dashboard smoke tests for healthy summaries, attention findings, reported reasons, grouped duplicate names, and ARM VM results in `project/tests/integration/test_workload_health.py`

### Implementation for User Story 2

- [ ] T022 [US2] Implement workload health findings from reported state, restart count, availability, and safe reported reasons in `project/homelab_dashboard/services/health.py`
- [ ] T023 [US2] Implement ARM-emulating virtual-machine filtering using reported architecture and return node ID, workload identity, name, and architecture in `project/homelab_dashboard/services/health.py`
- [ ] T024 [US2] Add grouped workload inspection, attention indicators, safe reason rendering, and ARM filter controls in `project/homelab_dashboard/ui/dashboard.py` and `project/homelab_dashboard/ui/components.py`
- [ ] T025 [US2] Extend fixture scenarios and snapshot wiring for degraded, failed, restarting, unknown, duplicate-name, and ARM workloads in `project/homelab_dashboard/sources/fixtures.py`

**Checkpoint**: User Stories 1 and 2 independently expose current overview data and actionable workload health findings.

---

## Phase 5: User Story 3 - Understand Connection and Data Freshness (Priority: P3)

**Goal**: Make offline, pending, timed-out, incomplete, and stale data visible without guessing missing values.

**Independent Test**: Simulate reachable, offline, timeout, incomplete, and recovery responses and verify node identity, connection category, missing fields, and last successful update behavior.

### Tests for User Story 3

- [ ] T026 [P] [US3] Add refresh-state tests for offline identity retention, unavailable current values, last successful timestamps, removed nodes, timeout, incomplete, and recovery in `project/tests/unit/test_refresh.py`
- [ ] T027 [P] [US3] Add Proxmox adapter contract tests for read-only endpoint mapping, timeouts, missing fields, unfamiliar states, and secret-safe errors in `project/tests/contract/test_proxmox_source.py`
- [ ] T028 [P] [US3] Add dashboard smoke tests for pending, offline, timed-out, incomplete, unknown, and per-node freshness states in `project/tests/integration/test_connection_states.py`

### Implementation for User Story 3

- [ ] T029 [P] [US3] Implement the read-only Proxmox adapter with dedicated API-token authentication, request timeouts, status-only endpoints, normalization, and secret-safe errors in `project/homelab_dashboard/sources/proxmox.py`
- [ ] T030 [US3] Implement live-versus-explicit-mock source selection and unavailable-live-configuration handling in `project/homelab_dashboard/config.py` and `project/app.py`
- [ ] T031 [US3] Render per-node connection state, missing fields, last successful update, pending/timeout indicators, and recovery transitions in `project/homelab_dashboard/ui/components.py` and `project/homelab_dashboard/ui/dashboard.py`
- [ ] T032 [US3] Add manual refresh and supported 30-second automatic refresh through the shared refresh path in `project/homelab_dashboard/services/refresh.py` and `project/homelab_dashboard/ui/dashboard.py`
- [ ] T033 [US3] Add reverse-proxy base-path settings and document live, mock, and safe-token startup behavior in `project/.streamlit/config.toml.example` and `project/README.md`

**Checkpoint**: All three stories distinguish current availability from stale or missing data and use live Proxmox by default when configured.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate the complete MVP against the quickstart and constitution.

- [ ] T034 [P] Add secret-safety tests ensuring token IDs, token secrets, authorization headers, and raw responses never reach errors or rendered UI in `project/tests/unit/test_secret_safety.py`
- [ ] T035 [P] Add responsive and reverse-proxy smoke coverage for desktop/mobile layout assumptions and configured base paths in `project/tests/integration/test_deployment_behavior.py`
- [ ] T036 Run the complete automated validation from `project/specs/001-homelab-inventory-dashboard/quickstart.md` and correct lint, formatting, and test failures in `project/`
- [ ] T037 Review `project/` against the constitution and document any remaining operational limitations in `project/README.md`

---

## Dependencies & Execution Order

### Phase Dependencies

1. Setup (Phase 1) before Foundational (Phase 2).
2. Foundational (Phase 2) before all user stories.
3. User Story 1 is the MVP and should complete before Story 2 UI integration.
4. User Story 2 builds on Story 1's normalized workloads and dashboard components.
5. User Story 3 builds on the shared refresh boundary and Story 1 dashboard, while its Proxmox adapter can be developed in parallel with Story 2 implementation.
6. Polish follows the completed stories and validates the full quickstart.

### Parallel Opportunities

- Phase 1: T003 and T004 can run in parallel after T001/T002 establish the project files.
- Phase 2: T005-T008 and T010 can run in parallel; T009 follows the domain/source contracts, and T011 follows the test fixture shape.
- User Story 1: T012-T014 can run in parallel; T015 and T017 can run in parallel before T016/T018 integration.
- User Story 2: T019-T021 can run in parallel; T022, T023, and T025 can run in parallel before T024 UI integration.
- User Story 3: T026-T028 can run in parallel; T029 and T033 can run in parallel with the refresh/UI work once the source contract exists.
- Polish: T034 and T035 can run in parallel before T036/T037.

## Implementation Strategy

1. Deliver the smallest independently testable MVP: foundational models, fixture source, refresh path, and User Story 1 dashboard.
2. Add workload findings and ARM filtering as a second increment without changing the source boundary.
3. Add live Proxmox connectivity, freshness/error states, and automatic refresh as the third increment.
4. Finish with secret-safety, responsive/reverse-proxy checks, and quickstart validation.

## Phase 7: Convergence

- [ ] T038 CRITICAL Remove the fabricated node snapshot and source-label heuristic from `project/app.py`; show "Live Proxmox" only for data returned by the configured live source per Constitution II, FR-001, and FR-003 (contradicts)
- [ ] T039 CRITICAL Preserve an absent restart count as unknown instead of defaulting it to zero, and keep health decisions evidence-based per Constitution II, FR-010, and US2/AC1 (contradicts)
- [ ] T040 Implement validated source configuration, a read-only Proxmox adapter using a dedicated read-only API token, and a deterministic fixture source; use live Proxmox when configured and require explicit fixture/demo selection per FR-017 and the plan's source decision (missing)
- [ ] T041 Render the source-driven node overview and workload inspection in Streamlit, including required node summaries, health findings and reported reasons, duplicate-name identity, ARM VM filtering, and empty/loading states per FR-001-FR-007, US1, and US2 (partial)
- [ ] T042 Replace unvalidated domain dataclasses with the plan's validated Pydantic models while preserving unknown and unavailable values per the plan's domain-model decision and T005 (partial)
- [ ] T043 Implement refresh orchestration with manual refresh, 30-second automatic refresh, per-node connection and freshness state, offline identity retention, timeout/incomplete handling, recovery, and replacement of removed nodes per FR-008-FR-011, FR-016, and US3 (missing)
- [ ] T044 Add tests proving credentials and raw responses cannot reach user-visible errors or output, status calls remain read-only, and live verification uses dedicated test resources without disrupting existing resources per FR-012, FR-015, SC-007, and Constitution II (partial)
- [ ] T045 Support configurable reverse-proxy base paths and responsive desktop/mobile rendering, and document live/mock startup, token configuration, and operational limitations in `project/README.md` per FR-014 and the deployment plan (missing)
- [ ] T046 Add acceptance coverage for 20 nodes and 200 workloads rendering within 30 seconds, then run the complete quickstart test and lint/format validation per SC-001, the plan's performance goal, and T036 (missing)
- [ ] T047 Review the unused `Workload.tags` field and remove it or document a requirement that justifies it (unrequested)

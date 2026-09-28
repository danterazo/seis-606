# Feature Specification: Homelab Status Dashboard

**Feature Branch**: `001-homelab-inventory-dashboard`

**Created**: 2026-09-27

**Status**: Draft

**Input**: User description: Create a visually appealing, responsive homelab and inventory management application. The MVP is a dashboard that aggregates system status from all Proxmox nodes, with mock inventory data available for later inventory workflows.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View Homelab Overview (Priority: P1)

As a homelab operator, I want one overview of my configured nodes and workloads so that I can understand the current state of my environment without checking several tools separately.

**Why this priority**: A trustworthy overview is the MVP and directly addresses the time and error cost of cross-referencing separate systems.

**Independent Test**: Provide representative data for multiple nodes and workloads, open the dashboard, and verify that every returned node appears with its current state and a summary of its workloads.

**Acceptance Scenarios**:

1. **Given** multiple configured nodes with current status data, **When** the operator opens or refreshes the dashboard, **Then** the dashboard displays one concise summary for each node, including node state, architecture, workload counts, health summary, and connection state.
2. **Given** a node has changing workload counts, **When** the operator refreshes the dashboard, **Then** the displayed counts reflect the latest available data and no fixed list or manually entered value remains visible.
3. **Given** no nodes are configured or available, **When** the operator opens the dashboard, **Then** it displays an explicit empty-state message and does not present fabricated node data.

### User Story 2 - Investigate Workload Health (Priority: P2)

As a homelab operator, I want to identify unhealthy containers and virtual machines quickly so that I can decide what needs attention.

**Why this priority**: Surfacing failures turns the overview into an operational tool and addresses errors that might otherwise go unnoticed.

**Independent Test**: Supply healthy, degraded, failed, and repeatedly restarting workloads, then verify that the dashboard classifies and exposes each state without changing the workloads.

**Acceptance Scenarios**:

1. **Given** a workload reports a failure, repeated restart, or unavailable state, **When** the dashboard is refreshed, **Then** the workload is visibly marked as needing attention and the reported reason is shown when available.
2. **Given** all workloads report healthy states, **When** the dashboard is viewed, **Then** it shows a clear healthy summary and does not create an alert for an absent problem.
3. **Given** a virtual machine reports an emulated ARM architecture, **When** the operator filters or asks for ARM-emulating virtual machines, **Then** the result includes every matching virtual machine and its reported architecture.

### User Story 3 - Understand Connection and Data Freshness (Priority: P3)

As a homelab operator, I want to know whether displayed information is current and whether a node is reachable so that I do not act on stale or uncertain status.

**Why this priority**: Clear uncertainty prevents unsafe assumptions and is required for a dashboard that can be trusted during outages.

**Independent Test**: Simulate a reachable node, an offline node, a timeout, and a response with missing fields, then verify the displayed state and freshness information for each case.

**Acceptance Scenarios**:

1. **Given** a node cannot be reached, **When** the dashboard refreshes, **Then** that node remains identifiable with an offline or unavailable state, the last successful update time is shown when known, and no missing values are guessed.
2. **Given** a node response times out or is incomplete, **When** the dashboard renders, **Then** it distinguishes the condition from a healthy response and identifies which information is unavailable.
3. **Given** a node was previously offline and becomes reachable, **When** the next connection check succeeds, **Then** the dashboard updates the node state and freshness indicator without requiring manually entered addresses or a page restart.

### Edge Cases

- A node returns some workload data but omits architecture or connection-quality information; the dashboard marks only the missing fields as unknown.
- A workload has an unfamiliar state; the dashboard shows the reported state as unknown or unclassified instead of mapping it to healthy.
- Two nodes expose workloads with the same name; the dashboard keeps them distinguishable by node.
- A refresh returns fewer nodes than the previous refresh; removed nodes disappear from the current summary and are not retained as if they were still active.
- Current data is unavailable during the first load; the dashboard shows a loading or unavailable state rather than an empty healthy environment.
- A connection check is slow; the dashboard remains usable and reports the check as pending or timed out.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST display every configured node returned by the available status sources in a single overview.
- **FR-002**: The system MUST display each node's current state, architecture when reported, workload counts, health summary, connection state, and data freshness.
- **FR-003**: The system MUST retrieve node and workload values dynamically and MUST NOT require hardcoded node addresses, node lists, workload counts, or architecture values.
- **FR-004**: The system MUST distinguish healthy, degraded, failed, offline, pending, unavailable, and unknown states whenever the source data supports that distinction.
- **FR-005**: The system MUST identify containers and virtual machines that report failures, repeated restarts, or other configured health problems and show the reported reason when available.
- **FR-006**: The system MUST allow the operator to inspect workloads by node and distinguish workloads with duplicate names on different nodes.
- **FR-007**: The system MUST support finding virtual machines that report ARM emulation and MUST show each matching virtual machine's node, identity, and reported architecture.
- **FR-008**: The system MUST show the time or age of the last successful data update for each node when available.
- **FR-009**: The system MUST preserve an offline or unavailable node's identity and last known update information without presenting stale values as current.
- **FR-010**: The system MUST label missing, incomplete, or uncertain information as unknown or unavailable and MUST NOT infer values that were not returned.
- **FR-011**: The system MUST provide a refresh or reconnection action that requests current status without modifying nodes, containers, virtual machines, or backups.
- **FR-012**: The system MUST avoid exposing credentials, tokens, or other secrets in the dashboard or user-visible error messages.
- **FR-013**: The dashboard MUST remain usable when the number of nodes or workloads changes between refreshes.
- **FR-014**: The dashboard MUST remain usable on supported desktop and mobile viewport sizes and when accessed through a reverse proxy.

### Out of Scope for This Feature

- Creating, restoring, rolling back, or deleting containers, virtual machines, or backups.
- Inventory quantity changes, part-to-node assignments, and shopping-list actions.
- Automatic remediation or any other action that changes system state.
- Treating mock inventory data as live inventory or combining inventory status with node health.

### Key Entities

- **Node**: A configured homelab host with an identity, reported state, architecture, connection state, freshness information, and associated workloads.
- **Workload**: A container or virtual machine associated with one node, including identity, type, reported state, health details, and architecture when available.
- **Status Observation**: A time-stamped set of values returned for a node or workload, including availability and any fields that could not be obtained.
- **Health Finding**: A user-visible indication that a node or workload is healthy, needs attention, unavailable, or unknown, with supporting reported details when available.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a representative environment of up to 20 nodes and 200 workloads, an operator can identify every currently reported node and its overall state from the overview within 30 seconds.
- **SC-002**: For a test dataset containing healthy, failed, restarting, offline, and unknown states, 100% of those states are displayed with the correct category and no unknown source value is presented as healthy.
- **SC-003**: For a test dataset containing ARM-emulating and non-ARM virtual machines across multiple nodes, every matching virtual machine is returned and no non-matching virtual machine is returned.
- **SC-004**: After a node becomes unreachable, the dashboard displays an unavailable or offline state and the last successful update within 10 seconds of the next completed check.
- **SC-005**: After a reachable node's workload count changes, the updated count appears after one successful refresh without editing application configuration.
- **SC-006**: In usability testing, at least 4 of 5 operators can locate a node needing attention and identify why it needs attention on their first attempt.
- **SC-007**: No acceptance test exposes a credential, token, or secret in the rendered interface or a user-visible failure message.

## Assumptions

- The operator is the authorized user for the configured homelab status sources.
- At least one status source and its access configuration are available for live verification; mock data may be used for repeatable tests.
- Status sources provide node identity, workload identity and type, state, and timestamps or enough information to determine freshness. Missing fields remain unknown.
- A refresh checks current status but does not perform remediation or any other state-changing action.
- Inventory management is a later feature and will have its own data model, requirements, and acceptance tests.
- Authentication, access control, and secret storage are supplied by the deployment environment and are not defined by this read-only dashboard feature.
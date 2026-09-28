# Research: Homelab Status Dashboard

## Decision: Streamlit with a modular Python domain layer

**Rationale**: The constitution names Streamlit as the default, the repository is
already Python/Poetry-based, and the MVP is a single operator dashboard. Keeping
models, source adapters, refresh orchestration, and rendering in separate modules
preserves maintainability without introducing a frontend build system.

**Alternatives considered**: A separate JavaScript frontend and API would add a
second deployment and authentication surface without being required by the MVP.
A custom HTML/CSS-only app would make responsive stateful dashboard behavior more
complex than Streamlit's existing primitives.

## Decision: Normalize all sources behind a read-only status-source protocol

**Rationale**: The UI must not know whether data came from live Proxmox, a future
MCP integration, or deterministic fixtures. A protocol returning validated Node,
Workload, observation, and source-error values gives all paths the same handling
for missing fields, unknown states, connection failures, and freshness. The live
Proxmox adapter is the default when configured; fixture mode is explicit and
labeled.

**Alternatives considered**: Calling Proxmox directly from Streamlit would couple
rendering to transport failures and make repeatable tests difficult. A database
would preserve history that the MVP does not require and could make stale data
look current.

## Decision: Use `proxmoxer` with a dedicated read-only API token

**Rationale**: `proxmoxer` provides a small Python client for the Proxmox REST
API and supports token-based authentication. The adapter will call only read
endpoints needed for cluster nodes and workload status, set connection and
request timeouts, and map transport/API errors to safe user-facing statuses.
Token ID and secret are loaded from deployment secrets, never placed in domain
objects, logs, exceptions, or rendered messages.

**Alternatives considered**: Shelling out to `pvesh` would tie the app to a local
Proxmox host and complicate reverse-proxy deployment. A generic HTTP client would
still need to recreate Proxmox authentication and endpoint mapping; it remains a
possible fallback if a required `proxmoxer` endpoint is unsupported.

## Decision: Treat freshness as per-node observation metadata

**Rationale**: A node can fail after a successful observation. Each refresh records
attempt time, completion time, connection state, and the last successful update
separately. On failure, identity and the last successful timestamp remain visible,
while current workload and health values are marked unavailable rather than
reused as current.

**Alternatives considered**: Reusing the last payload without a prominent stale
state risks operational mistakes. Clearing the node entirely loses the identity
needed to investigate an outage.

## Decision: Automatic 30-second refresh plus explicit manual refresh

**Rationale**: The requirement calls for both behaviors. Refresh orchestration will
be centralized so the timer and button invoke the same read-only operation, with
one in-flight refresh per session and a visible pending/failed state.

**Alternatives considered**: Browser polling or a background worker would add
lifecycle and deployment complexity. A longer interval would violate the feature
requirement.

## Decision: Deterministic fixture scenarios for testing and demo mode

**Rationale**: Fixtures can cover healthy, degraded, failed, restarting, offline,
pending, timeout, incomplete, unknown, duplicate-name, and ARM-emulating cases
without touching cluster resources. Every fixture-rendered view carries a
visible mock-data label and is unavailable as the default when live configuration
exists.

**Alternatives considered**: Tests against a real cluster are useful for a small
optional integration check, but cannot reliably produce all failure states and
must never mutate existing resources.

## Decision: Reverse-proxy-safe configuration is deployment-owned

**Rationale**: Streamlit should use its supported base-path and headless server
configuration rather than embedding absolute URLs. The quickstart will verify a
Caddy path, browser refresh, and static/session behavior. No application
credential or access-control system is invented for this read-only feature.

**Alternatives considered**: Hardcoding a root URL or adding application auth
would conflict with the constitution's deployment-owned authentication
assumption and fail when mounted at a different path.

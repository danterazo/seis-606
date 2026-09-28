# Status Source and Dashboard Contract

## Source adapter contract

The dashboard depends on one read-only operation:

```text
get_snapshot() -> RefreshResult
```

`RefreshResult` contains:

- `source_kind`: `live_proxmox`, `mcp`, or `mock`
- `source_label`: safe display label
- `attempted_at` and `completed_at`
- `nodes`: normalized current node records
- `source_error`: optional safe error category and message

The adapter MUST:

1. Use only read endpoints required for node and workload status.
2. Authenticate with the configured dedicated read-only API token.
3. Apply connection and request timeouts.
4. Return node identity on offline or unavailable results when known.
5. Preserve missing fields as null plus `missing_fields` metadata.
6. Preserve unfamiliar source state strings while classifying them as unknown.
7. Never include token IDs, token secrets, authorization headers, or raw response
   bodies in returned errors.
8. Avoid mutating nodes, workloads, backups, or configuration.

## Configuration contract

Live mode requires deployment-managed values equivalent to:

```text
HOMELAB_STATUS_SOURCE=proxmox
PROXMOX_API_URL=https://proxmox.example/api2/json
PROXMOX_TOKEN_ID=read-only-dashboard@pam!status
PROXMOX_TOKEN_SECRET=<deployment secret>
PROXMOX_VERIFY_TLS=true
PROXMOX_TIMEOUT_SECONDS=10
```

The secret placeholder above is documentation only and must never be committed.
If live configuration is unavailable, the application must fail clearly or run
only when the operator explicitly selects mock/demo mode.

## Dashboard contract

The page MUST provide:

- A visible source label, with `Mock data` for fixture mode.
- One current summary for every returned node.
- Node state, architecture, workload counts, health summary, connection state,
  and freshness/last successful update when available.
- Workload inspection grouped by node, preserving duplicate names.
- An ARM-emulating VM filter that returns every matching VM and its node,
  identity, and reported architecture.
- A manual refresh control and automatic refresh every 30 seconds.
- Loading, pending, empty, offline, timeout, incomplete, and unknown states.
- Safe error messages that do not expose credentials or raw secrets.

A successful refresh replaces the current node collection. A failed refresh must
not present the previous payload as current; it may retain node identity and last
successful timestamp with current values marked unavailable.

## HTTP/deployment expectations

The app is served by Streamlit and may be mounted behind a reverse-proxy path.
The deployment must pass the configured base path through Streamlit settings and
must not construct absolute root URLs in application code. Browser reload and
session state must continue to work at the configured path.

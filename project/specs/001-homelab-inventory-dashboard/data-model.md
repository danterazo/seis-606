# Data Model: Homelab Status Dashboard

## Node

A configured Proxmox host represented in the current refresh result.

| Field | Type | Rules |
|---|---|---|
| `node_id` | string | Stable source identity; required even when offline |
| `name` | string | Display name; required if returned, otherwise `unknown` |
| `architecture` | string or null | Reported architecture only; null renders as unknown |
| `reported_state` | enum/string | Preserve source value; unfamiliar values become `unknown` classification |
| `connection_state` | enum | `connected`, `offline`, `pending`, `timed_out`, `unavailable`, or `unknown` |
| `workloads` | list[Workload] | Current returned workloads; may be empty when data is valid |
| `workload_counts` | mapping | Derived only from returned workloads or explicitly reported counts |
| `health_findings` | list[HealthFinding] | Derived from reported node/workload conditions |
| `observation` | StatusObservation | Attempt/completion/freshness metadata |

Node identity is retained across failed refreshes. Current values that were not
returned during the failed attempt are null/unavailable, not copied as current.

## Workload

A container or virtual machine belonging to exactly one node in the normalized
snapshot.

| Field | Type | Rules |
|---|---|---|
| `node_id` | string | Required; distinguishes duplicate workload names |
| `workload_id` | string | Stable source identity within the node |
| `name` | string | Source name; unknown if omitted |
| `kind` | enum | `container`, `virtual_machine`, or `unknown` |
| `reported_state` | enum/string | Preserve source value; do not map unfamiliar values to healthy |
| `health_state` | enum | `healthy`, `degraded`, `failed`, `restarting`, `offline`, `pending`, `unavailable`, or `unknown` |
| `health_reason` | string or null | Reported reason only; never generated as a factual diagnosis |
| `architecture` | string or null | Reported architecture where available |
| `restart_count` | integer or null | Non-negative when returned; repeated restarts produce a finding |

## StatusObservation

Metadata for one node or workload read attempt.

| Field | Type | Rules |
|---|---|---|
| `attempted_at` | datetime | Required, timezone-aware |
| `completed_at` | datetime or null | Null while pending |
| `last_successful_at` | datetime or null | Updated only after a complete successful source read |
| `connection_state` | enum | Describes the current attempt, not the last known success |
| `missing_fields` | set[string] | Names fields omitted by the source |
| `error_kind` | enum/null | `timeout`, `authentication`, `transport`, `api`, `incomplete`, or null |

## HealthFinding

A user-visible finding derived from source evidence.

| Field | Type | Rules |
|---|---|---|
| `severity` | enum | `info`, `warning`, `critical`, or `unknown` |
| `subject_id` | string | Node or workload identity |
| `category` | enum | `healthy`, `degraded`, `failed`, `restarting`, `offline`, `unavailable`, or `unknown` |
| `message` | string | Safe, user-visible summary without secrets |
| `reported_reason` | string or null | Exact safe reason when supplied by the source |

## RefreshSnapshot

The immutable normalized result rendered by one refresh.

- `source_kind`: `live_proxmox`, `mcp`, or `mock`
- `source_label`: safe display label; mock snapshots must say `Mock data`
- `refreshed_at`: completion timestamp for the snapshot
- `nodes`: current returned node set, with no retention of removed nodes
- `global_findings`: source-level or aggregate findings

## State rules

- Only an explicit healthy source value may produce `healthy`.
- Failed, repeated restart, offline, pending, timeout, incomplete, and unfamiliar
  states retain distinct categories where the source supports them.
- Missing fields become `unknown` or `unavailable`; no values are inferred.
- ARM filtering selects virtual machines whose reported architecture indicates ARM
  emulation and returns node ID, workload identity, name, and architecture.
- A refresh replaces the current node set; a node absent from the new result is
  not retained as active.

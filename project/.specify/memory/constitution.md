<!--
Sync Impact Report
Version change: placeholder scaffold -> 0.1.0
Modified principles: none; all five principles are newly established
Added sections: Security and Operational Constraints; Development Workflow
Removed sections: none
Follow-up TODOs: confirm the original ratification date
-->

# Homelab Inventory Dashboard Constitution

## Core Principles

### I. Safe and Reversible Operations
Any operation that changes system state MUST be explicit, scoped, validated, and
reversible or accompanied by a documented rollback path. Destructive actions MUST
require user confirmation and MUST identify the affected nodes, containers,
backups, or inventory records before execution. The system MUST refuse to act
when the target or required context is uncertain.

### II. MCP-First, Evidence-Based Automation
Features MUST use the configured MCP integrations when they provide the required
capability, especially for Proxmox, ZFS, Thunderbird, Klipper, and TickTick.
Displayed status, architecture, health, inventory, and connection information
MUST come from current integration results or be clearly labeled as mock data.
The system MUST NOT invent missing facts; it MUST report uncertainty and suggest
missing integrations when appropriate.

### III. Atomic and Auditable Changes
State-changing workflows MUST be atomic at the application boundary: validate
the complete request before applying any mutation, isolate unrelated records,
and report success or failure with the resulting scope. Actions MUST produce an
auditable notification through the configured Discord webhook without exposing
secrets. Partial failure MUST leave a clear recovery state.

### IV. Dynamic, Testable User Experience
The dashboard MUST render changing nodes, containers, connections, and inventory
from programmatically retrieved data rather than hardcoded values. Every user-
facing workflow MUST have observable acceptance criteria covering normal,
missing, offline, and failure states. The interface MUST remain usable and
responsive behind a reverse proxy and on supported viewport sizes.

### V. Maintainable, Focused Architecture
The default implementation MUST use Streamlit unless a specific design need
justifies a small custom HTML/CSS layer. Features MUST remain modular, readable,
and appropriately scoped; existing integrations and reusable components MUST be
preferred over duplicate tooling. Complexity MUST be justified by a concrete
user or reliability requirement, and speculative features MUST stay out of the
MVP.

## Security and Operational Constraints

- Secrets, credentials, tokens, and sensitive integration responses MUST NOT be
	logged or rendered in the UI.
- System and inventory actions MUST distinguish their targets and MUST NOT mutate
	unrelated records.
- Dynamic addresses, node lists, versions, quantities, and health indicators
	MUST be discovered from configuration or integrations rather than hardcoded.
- Backup cleanup, restore, rollback, version pinning, and similar actions MUST
	verify the specific target before mutation.
- The application MUST support deployment behind Caddy or another reverse proxy
	without losing correct routing, session behavior, or data rendering.

## Development Workflow

- Specifications MUST describe observable behavior, constraints, and verification
	criteria before implementation begins.
- Tests or executable checks MUST cover integration contracts, mutation scoping,
	confirmation behavior, failure handling, and representative dynamic data.
- Changes involving MCPs or shared schemas MUST include focused integration
	verification; UI changes MUST verify offline, empty, and changing-data states
	where applicable.
- Reviews MUST check this constitution, especially safety, evidence provenance,
	secret handling, and reversibility, before a feature is considered complete.
- Documentation and example workflows MUST use copyable blocks where commands or
	notebook cells are part of the user workflow.

## Governance

This constitution is the governing quality standard for the Homelab Inventory
Dashboard. It supersedes conflicting local guidance. Every specification, plan,
implementation, and review MUST identify any applicable principles and explain
any justified exception. Exceptions require explicit documentation, affected
scope, risk, and a rollback or follow-up plan.

Amendments MUST update the version and last-amended date, include a sync impact
report, and preserve the intent of existing safety and truthfulness guarantees.
Versioning follows semantic versioning: MAJOR for incompatible principle changes,
MINOR for new principles or materially expanded governance, and PATCH for
clarifications or non-semantic wording changes. The constitution MUST be
reviewed whenever the architecture, integrations, or operational capabilities
change materially.

**Version**: 0.1.0 | **Ratified**: TODO(RATIFICATION_DATE): confirm original adoption date | **Last Amended**: 2026-09-27

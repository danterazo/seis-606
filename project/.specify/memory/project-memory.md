# Project Memory

Updated: 2026-10-21

## Operating Decision

- This is a personal homelab dashboard for one operator on the user's own hardware, not a public or multi-user product.
- Keep it local-only and operator-only. Do not broaden access or implement deferred hardening without an explicit request.
- Local-only limits intended reach, not all risk; compromised accounts, browsers, proxies, or LAN devices remain in scope.
- The app defaults to loopback. The README's LAN-access plan conflicts with the user's only-for-my-eyes decision and must be reconciled before
  implementation.

## Development Workflow

- On 2026-10-21, the user requested separate commits and PRs for independent concerns, specifically Copilot guidance versus Biome schema fixes. Keep
  implementation-specific memory with its corresponding concern. The existing combined commit is accepted as-is; do not rewrite it for this
  correction.
- On 2026-10-21, the user changed the commit workflow: after an approved commit, push to the configured remote unless explicitly told not to. Keep the
  existing commit-choice approval step; do not ask for separate push approval. This supersedes the former project-specific no-push default.
- On 2026-10-21, the user requested only the default split on workspace open. Local `.vscode/settings.json` now disables persistent sessions, process
  revival, and task reconnection, superseding the persistence settings below. Extra terminals opened during a session are not restored on reopen; the
  layout task itself does not close currently live extras. Configuration assertions pass; actual window close/reopen remains unverified to avoid
  interrupting the user-managed dashboard. The attached dashboard tab was cache-bypassing reloaded and returned HTTP 200. The sibling `seis-765-ops`
  has no startup layout, so no counterpart change applies.
- On 2026-10-20, the user requested a persistent/default VS Code split for this repo. `.vscode/tasks.json` defines an `Open default terminal layout`
  folder-open/manual task launching the left `dashboard` task and right `bash` shell in one presentation group; automatic tasks require workspace
  consent. The `dashboard` task executes `make run`, which stops any process already listening on port 8766 before starting the dashboard. New
  Terminal creates an ordinary teal shell, not the startup pair; use the layout task to recreate deleted panes. Persistence does not restore
  explicitly deleted terminals. The Pandoc PDF export task is separate and manual. Git-ignored `.vscode/settings.json` explicitly enables persistence,
  revival on exit/window close, task reconnection, and 10,000 lines of saved scrollback. JSON and configuration assertions pass; actual close/reopen
  restoration remains unverified to avoid disrupting user-managed terminals.
- The startup `dashboard` tab uses a pink/magenta play icon (`terminal.ansiMagenta`); the initial `bash` tab icon uses gold/yellow
  (`terminal.ansiYellow`). Keep later ordinary Bash terminals/splits on the user's default teal (`terminal.ansiCyan`); do not recolor the Bash profile
  or global default. Exact shades depend on the active theme; visual rendering remains unverified without recreating the user's terminals.
- Manage reusable class-wide maintenance across all top-level class repositories under `/home/dante/code/coursework` (currently `seis-606-vibe` and
  `seis-765-ops`). For changes applicable across classes, inspect each sibling's instructions and memory, apply every compatible counterpart, and
  validate and update affected documentation and memory in each repo during the same task. Preserve course-specific differences, unrelated work,
  independent Git histories, and per-repo commit/push approvals. Do not treat nested course-owned submodules as class repositories or apply
  assignment-specific changes to other classes. Recheck the sibling inventory for future classes; report incompatible or blocked counterparts.
- "Other class repos" and "neighboring class repos" mean all sibling class repositories in the current repo's enclosing `coursework` directory,
  excluding the current repository. Discover them without asking the user for paths or relying on a fixed class list; apply the requested work to
  every applicable sibling under the maintenance and approval rules above. Do not include nested course-owned submodules.
- The user runs the local dashboard server to observe changes, commonly on `127.0.0.1:8766`. Reuse its existing shared browser tab without asking the
  user to share it again.
- If no dashboard tab exists, open a browser tab at the already-running server; do not start a server to create a preview.
- Do not start, restart, or stop a server the user manages unless explicitly asked. If the existing server is unavailable, ask the user to start it.
- Avoid `make run` for previews because it kills the process on port `8766` before starting.
- `make deps` / `make update` pulls with `--ff-only` before updating dependencies, commits only tracked root Python and dashboard web dependency
  manifests/lockfiles with `Update dependencies` when changed, and pushes. Unrelated staged files are excluded; failed pulls stop the workflow.
- `make pull` updates submodules recursively, commits only changed submodule pointers with `Update submodules`, and pushes the main repository.
  Unrelated staged files are excluded; unchanged pointers do not create a commit. Failed update or commit steps prevent pushing.

## Presentation

- Explain the narrow threat model: one operator, personal data and infrastructure, owned homelab hardware, and no public or multi-user access.
- Acknowledge that there is no login, reads expose homelab data, and SSH defaults to root. Local deployment reduces reachability, not code-level risk.
- Be precise about the network boundary. Do not describe LAN access as only-for-my-eyes unless access is actually restricted to the operator.
- Frame additional security work as deferred and proportional to the intended use, not as evidence that the current app is risk-free.

## Deferred Work

These are discussion items, not authorization to change code or deployment. Update status only when the user requests or verifies the work.

- [ ] Reconcile the README's LAN reverse-proxy plan with the operator-only decision; confirm the access boundary before changing deployment guidance.
- [ ] Evaluate least-privilege Proxmox/router reads, including scoped PVE API tokens and restricted probes where suitable.
- [ ] Evaluate reducing root SSH privileges, especially for guest start/reboot actions; retain the current behavior unless a change is explicitly
      requested.
- [ ] If persistent data is introduced, define dev/production separation, backup/restore, and access controls before deployment.

## Code Cleanup

- On 2026-10-21, added matching `make clean` targets to all class repositories. They remove only SyncThing conflict copies and Windows `Zone.Identifier`
  files outside `.git`; the target is documented in each repository README.

- On 2026-10-21, aligned the web Biome schema with installed CLI `2.6.2`, clearing the informational schema-version warning from `make fix`. The
  complete `npm --prefix project/web run lint` chain passed, including JavaScript type-checking; lint rules and dependency policy are unchanged. A
  subsequent editor trust warning prompted use of the package-local schema instead of a versioned remote URL, avoiding remote schema downloads and
  keeping the schema aligned with the installed Biome package.
- Use `make fix` for supported Python/web lint fixes, Python/web/tracked-Markdown formatting, and final Python/web lint checks including JavaScript
  type-checking. `make format` is a compatibility alias; `make lint` is check-only. Unsupported fixes still require manual changes.
- On 2026-10-18, the web fix workflow automatically repaired the HTML `no-raw-characters` ampersand error, and web lint/type-checks passed.

## Verified Security Posture

### Bounded Activity Logging

- Implemented and tested on 2026-10-20: the active JSONL request log is capped at 1 MiB, with batched atomic compaction retaining recent complete
  records. Reads inspect only a bounded tail and return up to 500 recent records; oversized existing files shrink on the next successful write.
- Invalid JSON, invalid encoding, and incomplete records are skipped; subsequent writes recover incomplete trailing records. Logging errors do not
  break dashboard responses, and log read/clear failures return generic HTTP 503 responses. Failed compaction preserves the original file.
- Focused tests cover retention, old oversized files, concurrent writes, corruption, simulated filesystem/replacement failures, and API recovery.
- This is a local convenience log, not a durable audit trail. No deployment, authentication, SSH privilege, or server-lifecycle changes were made.

### Original Review

As reviewed on 2026-10-18:

- The application defaults to `127.0.0.1`.
- Read endpoints have no user authentication and expose detailed node, guest, device, lease, and activity-log information.
- Guest start/reboot and log-clear writes require loopback and matching same-origin checks plus an app-specific header. These are not user
  authentication.
- SSH defaults to root and uses public-key authentication, disabled password/keyboard-interactive authentication, batch mode, and strict host-key
  checking.
- The README proposes LAN clients can read through a reverse proxy; that conflicts with the user's current operator-only decision.

# SEIS 606: Vibe Coding: Copilot Instructions
Modify `.vscode/settings.json` only when the user explicitly requests it. Python import paths are configured in `pyproject.toml` under
`[tool.pyright]`; edit that file instead, and ask first if a change seems necessary.

## Project Memory
- Before working in this project, read `project/.specify/memory/project-memory.md` for durable decisions, verified context, and deferred work.
- Keep that file current when the user makes or changes a project decision, or when tracked work is started, completed, blocked, or deferred.
- Treat deferred items as notes, not authorization to implement them. Preserve the user's local-only, single-operator scope unless they explicitly
  change it.
- Distinguish verified implementation facts from intended deployment plans; do not mark work complete without verification.

## Documentation Sync
- When project code, configuration, endpoints, tests, or directory structure changes, inspect and update affected user-facing documentation, including
  hardcoded file trees, environment and configuration tables, endpoint summaries, and feature lists.
- Verify documented paths, settings, and endpoints against the current workspace and implementation; add new entries and remove stale ones.
- In README trees, mark explanatory annotations with `#` and keep annotation text lowercase. Preserve the exact case of real paths and identifiers.

## Interface Copy and Localization
- When changing dashboard interface text, update the English source and all supported locales (`es`, `pt`, `ja`, `is`, and `eo`) in the same change. Cover visible text, browser titles, accessible labels, and static HTML fallbacks where applicable; preserve interpolation placeholders and the project's capitalization and product-name decisions.
- Verify the changed text in all six locales, including Japanese, using the existing dashboard browser when available.

## Local Preview Servers
- Reuse the existing dashboard tab; do not ask the user to share it again. Use browser tooling to access it.
- If no dashboard tab exists, open a new one at the already-running server, commonly `http://127.0.0.1:8766`; do not start a server just for a
  preview.
- Do not start, restart, or stop a server the user manages unless explicitly asked. If the existing server is unavailable, ask the user to start it.

- Expect multiple agents to work in this repository concurrently.
- Track this thread's changes; preserve unrelated staged, unstaged, and untracked work. Unrelated changes are not blockers.
- After validation, offer to commit only this thread's changes. Provide a suggested commit message, accept a custom message, and offer no commit in
  one question form.
- Finalization gate: after validation, request the commit choice before replying unless already authorized or declined.
- Commit only approved thread-specific files or chunks. Preserve unrelated staging; never stage the entire worktree indiscriminately.
- Keep independent concerns in separate commits and PRs. In particular, do not bundle Copilot instructions or workflow preferences with application,
  dependency, or tooling fixes. Keep implementation-specific memory with its relevant concern.
- If changes overlap and cannot be confidently separated, ask.
- Do not commit without approval. After an approved commit, push to the configured remote unless the user explicitly says not to; do not ask for
  separate push approval.

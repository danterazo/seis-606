Modify `.vscode/settings.json` only when the user explicitly requests it. Python import paths are configured in `pyproject.toml` under
`[tool.pyright]`; edit that file instead, and ask first if a change seems necessary.

## Project Memory

- Before working in this project, read `project/.specify/memory/project-memory.md` for durable decisions, verified context, and deferred work.
- Keep that file current when the user makes or changes a project decision, or when tracked work is started, completed, blocked, or deferred.
- Treat deferred items as notes, not authorization to implement them. Preserve the user's local-only, single-operator scope unless they explicitly
  change it.
- Distinguish verified implementation facts from intended deployment plans; do not mark work complete without verification.

## Documentation sync

- When project code, configuration, endpoints, tests, or directory structure changes, inspect and update affected user-facing documentation, including
  hardcoded file trees, environment and configuration tables, endpoint summaries, and feature lists.
- Verify documented paths, settings, and endpoints against the current workspace and implementation; add new entries and remove stale ones.
- In README trees, mark explanatory annotations with `#` and keep annotation text lowercase. Preserve the exact case of real paths and identifiers.

## Concurrent Agents and Commits

- Expect multiple agents to work in this repository concurrently.
- Track this thread's changes; preserve unrelated staged, unstaged, and untracked work. Unrelated changes are not blockers.
- After validation, offer to commit only this thread's changes. Provide a suggested commit message, accept a custom message, and offer no commit in
  one question form.
- Commit only approved thread-specific files or hunks. Preserve unrelated staging; never stage the entire worktree indiscriminately.
- If changes overlap and cannot be confidently separated, ask.
- Do not commit without approval. Do not push unless explicitly requested.

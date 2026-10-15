Modify `.vscode/settings.json` only when the user explicitly requests it. Python import paths are configured in `pyproject.toml` under `[tool.pyright]`; edit that file instead, and ask first if a change seems necessary.

## Documentation sync

- When project code, configuration, endpoints, tests, or directory structure changes, inspect and update affected user-facing documentation, including hardcoded file trees, environment and configuration tables, endpoint summaries, and feature lists.
- Verify documented paths, settings, and endpoints against the current workspace and implementation; add new entries and remove stale ones.
- In README trees, mark explanatory annotations with `#` and keep annotation text lowercase. Preserve the exact case of real paths and identifiers.

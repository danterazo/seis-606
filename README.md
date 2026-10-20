# SEIS 606: Vibe Coding

## VS Code Terminals

Opening this repository in VS Code starts a split terminal group: the left `dashboard` pane runs `make run`, and the right `bash` pane is an
interactive shell. If prompted, allow automatic tasks for this trusted workspace; use **Tasks: Manage Automatic Tasks** to change that choice. To
reopen the pair after closing it, use **Tasks: Run Task** and select **Open default terminal layout**. The `make run` recipe stops any process already
listening on port 8766 before starting the dashboard.

The **New Terminal** button creates one ordinary shell, not the startup layout. Deleting a terminal intentionally removes it; session persistence
restores terminals left open when VS Code closes, not terminals explicitly deleted.

The manual **Markdown: Export PDF (Pandoc)** task exports the active Markdown file to PDF; it does not run automatically with the terminal layout.

The startup `dashboard` tab uses a pink/magenta play icon, and the initial `bash` tab icon uses gold/yellow, with exact shades supplied by the active
theme. These colors apply only to the two startup tasks; ordinary new Bash terminals and splits retain the default teal color.

Local workspace settings enable persistent terminal sessions, process revival on exit/window close, task reconnection, and 10,000 lines of saved
scrollback. These settings live in the Git-ignored `.vscode/settings.json`; the default split is versioned in `.vscode/tasks.json`. Window reloads can
reconnect to live processes, but full restarts revive shells rather than resume commands typed into them. WSL or host restarts terminate live
processes; the automatic tasks recreate the default split when the repository opens again.

## Dependencies

Run `make deps` (or `make update`) to pull with `--ff-only`, update dependencies, commit changed tracked dependency manifests and lockfiles with
`Update dependencies`, and push. Unrelated staged files are excluded. A failed pull stops the update; no commit is created when dependencies are
unchanged. Resolve overlapping local changes or diverged history manually before retrying.

## Submodules

Run `make pull` to pull the main repository, initialize and protect submodules against pushes, and update them recursively from `origin/main`. Changed
submodule pointers are committed in the main repository with `Update submodules`, then pushed. Unrelated staged files are excluded, and no commit is
created when the pointers are unchanged. A failed pull, submodule update, or commit stops the workflow before pushing.

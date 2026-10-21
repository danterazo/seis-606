# SEIS 606: Vibe Coding

## VS Code Terminals

Opening this repository in VS Code starts a split terminal group: the left `dashboard | make run` pane runs `make run`, and the right
`bash | workbench` pane is an interactive shell. If prompted, allow automatic tasks for this trusted workspace; use **Tasks: Manage Automatic Tasks**
to change that choice. To reopen the pair after closing it, use **Tasks: Run Task** and select **Open default terminal layout**. The `make run` recipe
stops any process already listening on port 8766 before starting the dashboard.

The local **Homelab Dashboard Preview** extension waits for the `dashboard | make run` task's server to respond successfully, then loads or refreshes
the integrated-browser tab at `http://127.0.0.1:8766/`. Existing dashboard tabs (including `localhost` URLs) are reused in place, preserving their pin
and position. It also handles a dashboard task already running when the extension activates. Failed or stopped tasks do not open a browser; readiness
checks stop after 60 seconds. Diagnostics appear in the **Homelab Dashboard Preview** output channel.

Install the bundled helper once in each VS Code environment using **Extensions: Install from VSIX...** and `.vscode/dashboard-preview.vsix`, or run
`code --install-extension .vscode/dashboard-preview.vsix` from this repository. Reload the window if VS Code requests it. Sources and focused tests
are in `.vscode/dashboard-preview/`; run `node --test .vscode/dashboard-preview/extension.test.js` to test them. Source sync does not install
extensions. The helper requires VS Code 1.142 or newer, a trusted workspace, and permitted folder-open tasks. It does not launch or restart the server
itself.

The **New Terminal** button creates one ordinary shell, not the startup layout. Extra terminals can be opened during a session, but are not restored
when this workspace opens again.

The manual **Markdown: Export PDF (Pandoc)** task exports the active Markdown file to PDF; it does not run automatically with the terminal layout.

The startup `dashboard` tab uses a pink/magenta play icon, and the initial `bash` tab icon uses gold/yellow, with exact shades supplied by the active
theme. These colors apply only to the two startup tasks; ordinary new Bash terminals and splits retain the default teal color.

Versioned workspace settings disable persistent terminal sessions, process revival, and task reconnection so old terminals are not restored alongside
the default split. `terminal.integrated.hideOnStartup: "whenEmpty"` prevents an empty terminal panel from creating an extra shell before the automatic
tasks reveal their split. Active terminals retain 10,000 lines of scrollback within the current session. These settings live in
`.vscode/settings.json`; the default split is defined in `.vscode/tasks.json`. Closing or reloading the window ends terminal sessions, including the
dashboard; the automatic tasks recreate the default split when the repository opens again. Running the layout task manually does not close unrelated
terminals already open in the current window.

The startup terminal names are `dashboard | make run` and `bash | workbench`. The workspace description template omits `${task}` to hide the small
`Task` suffix while retaining local-terminal and working-directory information when applicable. VS Code does not support independent per-task
description text, so the extra labels are part of the main names instead. New names apply when the startup terminals are next created; changing task
configuration does not rename existing live terminals or restart the dashboard.

## Dependencies

Run `make deps` (or `make update`) to pull with `--ff-only`, update dependencies, commit changed tracked dependency manifests and lockfiles with
`Update dependencies`, and push. Unrelated staged files are excluded. A failed pull stops the update; no commit is created when dependencies are
unchanged. Resolve overlapping local changes or diverged history manually before retrying.

## Submodules

Run `make pull` to pull the main repository, initialize and protect submodules against pushes, and update them recursively from `origin/main`. Changed
submodule pointers are committed in the main repository with `Update submodules`, then pushed. Unrelated staged files are excluded, and no commit is
created when the pointers are unchanged. A failed pull, submodule update, or commit stops the workflow before pushing.

## Cleanup

Run `make clean` to remove SyncThing conflict copies and Windows `Zone.Identifier` files. The command excludes files under the repository's `.git`
directory and leaves other files untouched.

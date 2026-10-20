# SEIS 606: Vibe Coding

## Dependencies

Run `make deps` (or `make update`) to pull with `--ff-only`, update dependencies, commit changed tracked dependency manifests and lockfiles with
`Update dependencies`, and push. Unrelated staged files are excluded. A failed pull stops the update; no commit is created when dependencies are
unchanged. Resolve overlapping local changes or diverged history manually before retrying.

## Submodules

Run `make pull` to pull the main repository, initialize and protect submodules against pushes, and update them recursively from `origin/main`. Changed
submodule pointers are committed in the main repository with `Update submodules`, then pushed. Unrelated staged files are excluded, and no commit is
created when the pointers are unchanged. A failed pull, submodule update, or commit stops the workflow before pushing.

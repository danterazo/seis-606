# SEIS 606: Vibe Coding

## Dependencies

Run `make deps` (or `make update`) to pull with `--ff-only`, update dependencies, commit changed tracked dependency manifests and lockfiles with
`Update dependencies`, and push. Unrelated staged files are excluded. A failed pull stops the update; no commit is created when dependencies are
unchanged. Resolve overlapping local changes or diverged history manually before retrying.

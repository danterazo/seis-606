#!/bin/bash
set -euo pipefail

# resolve and lock root dependencies
poetry lock
poetry update

# install root env
poetry install

# install lab envs (without mutating lockfiles)
find labs -mindepth 1 -type f -name pyproject.toml -printf '%h\n' | sort -u | while read -r DIR; do
	echo -e "Running 'uv sync --locked' in \033[1;34m$DIR\033[0m"
	(cd "$DIR" && uv sync --locked)
done

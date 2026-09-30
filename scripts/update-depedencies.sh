#!/bin/bash
set -euo pipefail

# resolve, update lock, and install python dependencies
poetry update

# install lab envs (without mutating lockfiles)
# support both naming conventions: 765 uses "labs", 606 uses "assignments"
LAB_DIRS=()
for d in labs assignments; do
  [ -d "$d" ] && LAB_DIRS+=("$d")
done

# conditional select
if [ "${#LAB_DIRS[@]}" -eq 0 ]; then
  echo -e "\033[1;33mNo \033[1;36mlabs/\033[1;33m or \033[1;36massignments/\033[1;33m directory found; skipping lab envs.\033[0m"
else
  find "${LAB_DIRS[@]}" -mindepth 1 -type f -name pyproject.toml -printf '%h\n' | sort -u | while read -r DIR; do
    echo -e "Running 'uv sync --locked' in \033[1;34m$DIR\033[0m"
    (cd "$DIR" && uv sync --locked)
  done
fi

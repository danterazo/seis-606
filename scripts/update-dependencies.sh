#!/bin/bash
set -euo pipefail

REPO_ROOT=$(git rev-parse --show-toplevel)
cd "$REPO_ROOT"
git -c merge.autostash=false pull --ff-only --no-rebase

# update system dependencies
uv tool upgrade --all

# resolve, update lock, and install python dependencies
poetry update

# update and install dashboard's web dependencies
REPO_NAME=$(basename "$REPO_ROOT")
if [[ "$REPO_NAME" == "seis-606-vibe" ]]; then
  npm update --prefix project/web
  npm ci --prefix project/web
fi

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

DEPENDENCY_FILES=()
mapfile -d '' -t DEPENDENCY_FILES < <(git ls-files -z -- pyproject.toml poetry.lock project/web/package.json project/web/package-lock.json)
if [[ ${#DEPENDENCY_FILES[@]} -gt 0 ]] && ! git diff --quiet HEAD -- "${DEPENDENCY_FILES[@]}"; then
  git commit --only -m "Update dependencies" -- "${DEPENDENCY_FILES[@]}"
else
  echo "No dependency changes to commit."
fi
git push

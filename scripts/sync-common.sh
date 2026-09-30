#!/bin/bash

# detect current repo
SRC="$(basename "$(pwd)")"

# determine destination / sibling repo
case "$SRC" in
  seis-606-vibe) DST="../seis-765-ops" ;;
  seis-765-ops) DST="../seis-606-vibe" ;;
  *)
    echo -e "\033[1;31mERROR:\033[0m Sync must be run from \033[1;36mseis-606-vibe\033[0m or \033[1;36mseis-765-ops\033[0m (got: \033[1;33m$SRC\033[0m)" >&2
    exit 1
    ;;
esac

# announce
echo -e "\n\033[1mSyncing\033[0m \033[1;36m$SRC\033[0m \033[1;33m->\033[0m \033[1;36m$(basename "$DST")\033[0m"

# sync directories
rsync -avh --mkpath .vscode/settings.json "$DST/.vscode/"
rsync -avh --mkpath scripts/ "$DST/"

# sync files
rsync -avh .envrc Makefile .editorconfig "$DST/"

# announce completion
echo -e "\033[1;32mSync complete\033[0m"

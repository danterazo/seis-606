#!/usr/bin/env bash

: 'SET WORKING DIR'
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"


: 'IMMUTABLE TOGGLE'
SETTINGS_FILE=".vscode/settings.json"
sudo chattr -i "$SETTINGS_FILE"
trap 'sudo chattr +i "$SETTINGS_FILE"' EXIT


: 'FIND ASSIGNMENT PATHS'
PATHS=(
    '${workspaceFolder}/project'
    '${workspaceFolder}/assignments'
)
while IFS= read -r ASSIGNMENT_DIR; do
    PATHS+=("\${workspaceFolder}/${ASSIGNMENT_DIR}")
done < <(find assignments -mindepth 1 -maxdepth 1 -type d | sort)


: 'UPDATE PATHS BLOCK'
{
    printf '{\n'
    printf '  "git.detectSubmodules": false,\n'
    printf '  "python.analysis.extraPaths": [\n'
    for ((INDEX = 0; INDEX < ${#PATHS[@]}; INDEX++)); do
        if ((INDEX < ${#PATHS[@]} - 1)); then
            printf '    "%s",\n' "${PATHS[$INDEX]}"
        else
            printf '    "%s"\n' "${PATHS[$INDEX]}"
        fi
    done
    printf '  ]\n'
    printf '}\n'
} > "$SETTINGS_FILE"


: 'RESTORE IMMUTABILITY'
sudo chattr +i "$SETTINGS_FILE"
trap - EXIT
echo 'Wrote .vscode/settings.json with assignment roots.'

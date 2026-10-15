#!/usr/bin/env bash
set -euo pipefail

ssh_dir="${HOME}/.ssh"
known_hosts="${ssh_dir}/known_hosts"
candidate="$(mktemp)"
trap 'rm -f "$candidate" "$candidate.old"' EXIT

hosts=(
    192.168.20.42
    192.168.20.43
    192.168.20.46
    100.100.20.42
    100.100.20.43
    100.100.20.46
    "${HOMELAB_ROUTER_SSH_HOST:-flint2}"
)

mkdir -p "$ssh_dir"
chmod 700 "$ssh_dir"
touch "$known_hosts"
chmod 600 "$known_hosts"

already_known=0
scanned_count=0
for host in "${hosts[@]}"; do
    if ssh-keygen -F "$host" -f "$known_hosts" >/dev/null 2>&1; then
        printf 'Already in known_hosts: %s\n' "$host"
        already_known=$((already_known + 1))
        continue
    fi

    if scanned="$(ssh-keyscan -T 4 -t ed25519 "$host" 2>/dev/null)" && [[ -n "$scanned" ]]; then
        printf '%s\n' "$scanned" >> "$candidate"
        fingerprints="$(printf '%s\n' "$scanned" | ssh-keygen -lf - | awk '{print $2}')"
        printf 'Found %s: %s\n' "$host" "$fingerprints"
        scanned_count=$((scanned_count + 1))
    else
        printf 'No ED25519 key found: %s\n' "$host"
    fi
done

if [[ ! -s "$candidate" ]]; then
    if (( already_known > 0 )); then
        printf 'No new host keys to add.\n'
        exit 0
    fi
    printf 'No host keys found. Check WSL networking and SSH host names.\n' >&2
    exit 1
fi

printf '\nScanned %d new host(s). Verify each fingerprint through a trusted channel.\n' "$scanned_count"
read -r -p 'Add these keys to known_hosts? [y/N] ' answer
if [[ ! "$answer" =~ ^[Yy]$ ]]; then
    printf 'No keys added.\n'
    exit 1
fi

ssh-keygen -H -f "$candidate" >/dev/null
printf '%s\n' "$(<"$candidate")" >> "$known_hosts"
printf 'Added scanned keys to %s.\n' "$known_hosts"
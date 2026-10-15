#!/usr/bin/env bash
set -euo pipefail

ssh_dir="${HOME}/.ssh"
known_hosts="${ssh_dir}/known_hosts"

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

missing_hosts=()
for host in "${hosts[@]}"; do
  if ssh-keygen -F "$host" -f "$known_hosts" >/dev/null 2>&1; then
    printf 'Already in known_hosts: %s\n' "$host"
  else
    missing_hosts+=("$host")
  fi
done

if ((${#missing_hosts[@]} == 0)); then
  printf 'SSH host keys are already set up.\n'
  exit 0
fi

ssh_client=/usr/bin/ssh
if [[ ! -x "$ssh_client" ]]; then
  printf 'OpenSSH client not found at %s.\n' "$ssh_client" >&2
  exit 1
fi

unaccepted_hosts=()
for host in "${missing_hosts[@]}"; do
  printf '\nConfirm the SSH host key for %s when prompted.\n' "$host"
  "$ssh_client" \
    -o StrictHostKeyChecking=ask \
    -o UserKnownHostsFile="$known_hosts" \
    -o ConnectTimeout=4 \
    -o PreferredAuthentications=none \
    -o PubkeyAuthentication=no \
    -o PasswordAuthentication=no \
    -o KbdInteractiveAuthentication=no \
    "$host" true || true

  if ssh-keygen -F "$host" -f "$known_hosts" >/dev/null 2>&1; then
    printf 'Host key added: %s\n' "$host"
  else
    printf 'Host key was not accepted or could not be reached: %s\n' "$host" >&2
    unaccepted_hosts+=("$host")
  fi
done

if ((${#unaccepted_hosts[@]} > 0)); then
  printf 'SSH host setup incomplete for: %s\n' "${unaccepted_hosts[*]}" >&2
  exit 1
fi

printf '\nAll SSH host keys are set up in %s.\n' "$known_hosts"
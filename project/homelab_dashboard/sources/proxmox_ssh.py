from __future__ import annotations

import json
import math
import os
import re
import subprocess
from collections import Counter
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any


def _run_pvesh(
    target: str,
    resource_type: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> list[dict[str, Any]]:
    if not re.fullmatch(r"[A-Za-z0-9_.@-]+", target) or target.startswith("-"):
        raise RuntimeError("Invalid SSH target. Use a host or alias from this WSL user's SSH configuration.")

    command = [
        "ssh",
        "-oBatchMode=yes",
        "-oConnectTimeout=6",
        "-oConnectionAttempts=1",
        "-oPreferredAuthentications=publickey",
        "-oPasswordAuthentication=no",
        "-oKbdInteractiveAuthentication=no",
        "-oStrictHostKeyChecking=yes",
        target,
        "pvesh",
        "get",
        "/cluster/resources",
        "--type",
        resource_type,
        "--output-format",
        "json",
    ]
    execute = runner or subprocess.run
    try:
        result = execute(command, capture_output=True, text=True, timeout=12, check=False)
    except FileNotFoundError as error:
        raise RuntimeError("The OpenSSH client is not available in this WSL environment.") from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"SSH to {target} timed out while reading PVE status.") from error

    if result.returncode:
        detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else ""
        if "permission denied" in detail.lower():
            message = f"SSH public-key authentication failed for {target}; check the existing WSL SSH identity and account access."
        elif "host key verification failed" in detail.lower():
            message = f"The SSH host key for {target} is not trusted by this WSL user's known_hosts file."
        else:
            message = f"PVE {resource_type} status query failed on {target}."
            if detail:
                message = f"{message} {detail[:200]}"
        raise RuntimeError(message)

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"PVE returned invalid {resource_type} status JSON.") from error
    if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
        raise RuntimeError(f"PVE returned an unexpected {resource_type} status response.")
    return payload


def _percent(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    if 0 <= number <= 1:
        number *= 100
    return round(max(0, min(100, number)), 1)


def _memory_percent(used: Any, maximum: Any) -> float | None:
    try:
        used_value = float(used)
        maximum_value = float(maximum)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(used_value) or not math.isfinite(maximum_value) or maximum_value <= 0:
        return None
    return round(max(0, min(100, used_value / maximum_value * 100)), 1)


def build_ssh_report(
    *,
    target: str | None = None,
    address: str | None = None,
    primary_name: str = "cerulean",
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> dict[str, Any]:
    ssh_target = target or os.getenv("HOMELAB_PVE_SSH_TARGET", "192.168.20.43")
    management_address = address or os.getenv("HOMELAB_PVE_ADDRESS", "192.168.20.43")
    node_rows = _run_pvesh(ssh_target, "node", runner=runner)
    guest_rows = _run_pvesh(ssh_target, "vm", runner=runner)

    guest_counts: dict[str, Counter[str]] = {}
    for guest in guest_rows:
        node_id = str(guest.get("node") or "")
        guest_type = str(guest.get("type") or "").lower()
        if guest_type in {"qemu", "vm"}:
            guest_counts.setdefault(node_id, Counter())["VM"] += 1
        elif guest_type == "lxc":
            guest_counts.setdefault(node_id, Counter())["LXC"] += 1

    nodes = []
    for row in node_rows:
        node_id = str(row.get("node") or row.get("id") or "").removeprefix("node/")
        if not node_id:
            continue
        status = str(row.get("status") or "unknown").lower()
        if status == "online":
            reported_state = "up"
        elif status in {"offline", "down"}:
            reported_state = "down"
        else:
            reported_state = "unknown"
        counts = guest_counts.get(node_id, Counter())
        nodes.append(
            {
                "node_id": node_id,
                "name": node_id,
                "address": management_address if node_id.casefold() == primary_name.casefold() else None,
                "role": "PVE HOST",
                "reported_state": reported_state,
                "architecture": None,
                "cpu_percent": _percent(row.get("cpu")),
                "memory_percent": _memory_percent(row.get("mem"), row.get("maxmem")),
                "workloads": {"VM": counts["VM"], "LXC": counts["LXC"]},
            }
        )

    primary = next((node for node in nodes if node["name"].casefold() == primary_name.casefold()), None)
    if primary is None:
        raise RuntimeError(f"PVE did not report the configured primary node '{primary_name}'.")

    online_count = sum(node["reported_state"] == "up" for node in nodes)
    down_count = sum(node["reported_state"] == "down" for node in nodes if node is not primary)
    other_count = sum(node is not primary for node in nodes)
    return {
        "source_label": "LIVE PVE / SSH",
        "is_live": True,
        "last_updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "target": ssh_target,
        "primary_node": primary,
        "nodes": nodes,
        "known_up_count": online_count,
        "down_count": down_count,
        "other_nodes_state": f"{down_count} DOWN" if down_count else ("NONE" if other_count == 0 else "UNKNOWN"),
        "other_node_identities_known": True,
    }

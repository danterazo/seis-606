from __future__ import annotations

import os

import streamlit as st

from homelab_dashboard.ui.dashboard import build_dashboard_snapshot


def main() -> None:
    st.set_page_config(page_title="Homelab Status Dashboard", layout="wide")

    source_label = os.getenv("HOMELAB_STATUS_SOURCE", "mock").lower()
    if source_label == "mock":
        source_label = "Mock data"
    else:
        source_label = "Live Proxmox"

    # TODO: replace with a real status source once sources/fixtures.py and sources/proxmox.py exist.
    snapshot = build_dashboard_snapshot(
        source_label=source_label,
        nodes=[
            {
                "node_id": "node-a",
                "name": "Node A",
                "reported_state": "running",
                "workloads": [
                    {"node_id": "node-a", "workload_id": "vm-1", "name": "api", "kind": "virtual_machine", "reported_state": "running"},
                    {"node_id": "node-a", "workload_id": "ct-1", "name": "db", "kind": "container", "reported_state": "running"},
                ],
            }
        ],
    )

    st.title("Homelab Status Dashboard")
    st.caption(f"Source: {snapshot['source_label']}")

    if snapshot["node_count"] == 0:
        st.info("No nodes reported.")
        return

    for node in snapshot["nodes"]:
        with st.container(border=True):
            st.subheader(f"{node['name']} — {node['reported_state']}")
            st.caption(f"{node['workload_count']} workload(s)")
            for workload in node["workloads"]:
                st.write(f"- {workload['name']} ({workload['kind']}): {workload['reported_state']}")


if __name__ == "__main__":
    main()

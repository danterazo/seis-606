from pathlib import Path
from typing import Any

from homelab_dashboard.presentation import present_payload


def make_payload(*, nodes: list[dict[str, Any]]) -> dict[str, Any]:
    return {"source": "test", "fetched_at": "2026-10-07T00:00:00+00:00", "nodes": nodes}


def test_new_nodes_sort_by_numeric_ip_not_name_or_profile_order(tmp_path: Path) -> None:
    payload = make_payload(
        nodes=[
            {"name": "alpha", "address": "192.168.20.100"},
            {"name": "kex", "address": "10.9.9.9"},
            {"name": "cerulean", "address": "192.168.20.43"},
            {"name": "zeta", "address": "192.168.20.9"},
            {"name": "missing", "address": None},
            {"name": "invalid", "address": "unknown"},
            {"name": "kveikur", "address": None},
        ]
    )
    presented = present_payload(payload=payload, image_dir=tmp_path)
    assert [node["name"] for node in presented["nodes"]] == ["zeta", "kex", "cerulean", "kveikur", "alpha", "invalid", "missing"]


def test_other_payload_fields_are_preserved(tmp_path: Path) -> None:
    presented = present_payload(payload=make_payload(nodes=[]), image_dir=tmp_path)

    assert presented["source"] == "test"
    assert presented["fetched_at"] == "2026-10-07T00:00:00+00:00"


def test_shared_names_apply_to_nodes_and_guests_without_changing_identity(tmp_path: Path) -> None:
    payload = make_payload(nodes=[{"name": "suika", "address": None, "guests": [{"name": "saru", "vmid": 101}]}])
    node = present_payload(payload=payload, image_dir=tmp_path)["nodes"][0]
    assert node["name"] == "suika"
    assert node["display_name"] == "\u3059\u3044\u304b"
    assert node["guests"][0] == {"name": "saru", "display_name": "\u3055\u308b", "vmid": 101}

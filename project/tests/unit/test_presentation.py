from pathlib import Path
from typing import Any, Dict, List

from homelab_dashboard.presentation import present_payload


def make_payload(*, nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"source": "test", "fetched_at": "2026-10-07T00:00:00+00:00", "nodes": nodes}


def test_nodes_are_ordered_kex_cerulean_kveikur(tmp_path: Path) -> None:
    payload = make_payload(
        nodes=[
            {"name": "kveikur", "address": None},
            {"name": "cerulean", "address": "192.168.20.43"},
            {"name": "kex", "address": None},
        ]
    )

    presented = present_payload(payload=payload, image_dir=tmp_path)

    assert [node["name"] for node in presented["nodes"]] == ["kex", "cerulean", "kveikur"]


def test_pinned_addresses_override_what_proxmox_reports(tmp_path: Path) -> None:
    payload = make_payload(
        nodes=[
            {"name": "kex", "address": "10.9.9.9"},
            {"name": "kveikur", "address": None},
            {"name": "cerulean", "address": "192.168.20.43"},
        ]
    )

    addresses = {node["name"]: node["address"] for node in present_payload(payload=payload, image_dir=tmp_path)["nodes"]}

    assert addresses == {"kex": "192.168.20.42", "cerulean": "192.168.20.43", "kveikur": "192.168.20.46"}


def test_display_fields_are_added_to_every_node(tmp_path: Path) -> None:
    (tmp_path / "kex.png").write_bytes(b"")
    payload = make_payload(nodes=[{"name": "kex", "address": None}, {"name": "cerulean", "address": None}])

    kex, cerulean = present_payload(payload=payload, image_dir=tmp_path)["nodes"]

    assert (kex["display_name"], kex["color"], kex["image"]) == ("Kex", "#c62839", "/images/nodes/kex.png")
    assert (cerulean["display_name"], cerulean["color"], cerulean["image"]) == ("Cerulean", "#0b7fc7", None)
    assert (kex["initial"], cerulean["initial"]) == ("K", "C")


def test_other_payload_fields_are_preserved(tmp_path: Path) -> None:
    presented = present_payload(payload=make_payload(nodes=[]), image_dir=tmp_path)

    assert presented["source"] == "test"
    assert presented["fetched_at"] == "2026-10-07T00:00:00+00:00"


def test_configured_memory_is_independent_of_live_hardware(tmp_path: Path) -> None:
    payload = make_payload(nodes=[{"name": name, "address": None} for name in ("kex", "cerulean", "kveikur", "stranger")])
    descriptions = {node["name"]: node["memory_description"] for node in present_payload(payload=payload, image_dir=tmp_path)["nodes"]}
    assert descriptions == {
        "kex": "DDR4 ECC RDIMM (configured)",
        "cerulean": "DDR4 SODIMM - 1 x 32 GB (configured)",
        "kveikur": "DDR4 ECC RDIMM (configured)",
        "stranger": None,
    }

import re
from typing import Final

import pytest
from homelab_dashboard.node_profiles import FALLBACK_PALETTE, NODE_PROFILES, display_name_for, node_sort_key, profile_for_node

HEX_COLOR: Final[str] = r"#[0-9a-f]{6}"


def test_configured_nodes_have_their_assigned_colors() -> None:
    assert profile_for_node(node_name="kex").color == "#c62839"
    assert profile_for_node(node_name="cerulean").color == "#0b7fc7"
    assert profile_for_node(node_name="kveikur").color == "#f28c1b"


def test_nodes_are_displayed_with_capital_letters() -> None:
    assert [profile_for_node(node_name=name).display_name for name in ("kex", "cerulean", "kveikur")] == ["Kex", "Cerulean", "Kveikur"]


def test_badge_initials_are_one_letter_and_unique_among_configured_nodes() -> None:
    initials = [profile.initial for profile in NODE_PROFILES.values()]

    assert all(len(initial) == 1 and initial.isupper() for initial in initials)
    assert len(set(initials)) == len(initials)


def test_configured_badge_initials() -> None:
    assert [profile_for_node(node_name=name).initial for name in ("kex", "cerulean", "kveikur")] == ["K", "C", "V"]


def test_unknown_nodes_use_their_first_letter_as_the_initial() -> None:
    assert profile_for_node(node_name="new-node").initial == "N"


def test_kex_and_kveikur_have_fixed_addresses() -> None:
    assert profile_for_node(node_name="kex").address == "192.168.20.42"
    assert profile_for_node(node_name="kveikur").address == "192.168.20.46"
    assert profile_for_node(node_name="cerulean").address is None


def test_lookup_ignores_case() -> None:
    assert profile_for_node(node_name="KEX") is NODE_PROFILES["kex"]


@pytest.mark.parametrize(
    ("name", "display_name"),
    [
        ("OVEDUR-10G", "\u00f3ve\u00f0ur-10g"),
        ("CREALITY-K1C-WIFI", "var\u00f0eldur"),
        ("suika", "\u3059\u3044\u304b"),
        ("ichigo", "\u3044\u3061\u3054"),
        ("saru", "\u3055\u308b"),
        ("ringoM4-wifi", "\u308a\u3093\u3054-m4"),
        ("ringoA20", "\u308a\u3093\u3054-a20"),
    ],
)
def test_shared_name_map_applies_to_future_nodes(name: str, display_name: str) -> None:
    assert display_name_for(name=name) == display_name
    assert profile_for_node(node_name=name).display_name == display_name


def test_unmapped_device_names_are_preserved() -> None:
    assert display_name_for(name="My-Device") == "My-Device"
    assert display_name_for(name="ringo-M4") == "ringo-M4"
    assert display_name_for(name="ringo-A20") == "ringo-A20"


def test_node_order_uses_ip_addresses_including_new_nodes() -> None:
    addresses = {"kveikur": "192.168.20.46", "cerulean": "192.168.20.43", "kex": "192.168.20.42", "new-node": "192.168.20.41"}
    assert sorted(addresses, key=lambda name: node_sort_key(node_name=name, address=addresses[name])) == ["new-node", "kex", "cerulean", "kveikur"]


def test_nodes_without_addresses_sort_last_alphabetically() -> None:
    names = ["zeta", "kveikur", "alpha", "kex"]

    assert sorted(names, key=lambda name: node_sort_key(node_name=name)) == ["kex", "kveikur", "alpha", "zeta"]


def test_invalid_addresses_sort_after_valid_addresses() -> None:
    assert node_sort_key(node_name="alpha", address="not-an-ip") > node_sort_key(node_name="zeta", address="192.168.20.100")


def test_duplicate_addresses_use_a_stable_name_tiebreaker() -> None:
    assert node_sort_key(node_name="alpha", address="192.168.20.100") < node_sort_key(node_name="zeta", address="192.168.20.100")


def test_unknown_nodes_get_a_stable_capitalized_profile() -> None:
    first = profile_for_node(node_name="new-node")

    assert first == profile_for_node(node_name="new-node")
    assert first.color in FALLBACK_PALETTE
    assert first.display_name == "New-node"


def test_every_color_is_a_plain_hex_value() -> None:
    for color in (*(profile.color for profile in NODE_PROFILES.values()), *FALLBACK_PALETTE):
        assert re.fullmatch(HEX_COLOR, color)


@pytest.mark.parametrize("fallback", FALLBACK_PALETTE)
def test_fallback_colors_never_collide_with_configured_nodes(*, fallback: str) -> None:
    assert fallback not in {profile.color for profile in NODE_PROFILES.values()}

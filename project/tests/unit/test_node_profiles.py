import re
from typing import Final

import pytest

from homelab_dashboard.node_profiles import FALLBACK_PALETTE, NODE_PROFILES, node_sort_key, profile_for_node

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


def test_kex_sorts_first_then_cerulean_then_kveikur() -> None:
    names = ["kveikur", "cerulean", "kex"]

    assert sorted(names, key=lambda name: node_sort_key(node_name=name)) == ["kex", "cerulean", "kveikur"]


def test_unknown_nodes_sort_after_known_ones_alphabetically() -> None:
    names = ["zeta", "kveikur", "alpha", "kex"]

    assert sorted(names, key=lambda name: node_sort_key(node_name=name)) == ["kex", "kveikur", "alpha", "zeta"]


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

import re
from typing import Final

import pytest

from homelab_dashboard.node_colors import FALLBACK_PALETTE, NODE_COLORS, color_for_node

HEX_COLOR: Final[str] = r"#[0-9a-f]{6}"


def test_configured_nodes_get_their_assigned_colors() -> None:
    assert color_for_node(node_name="kex") == "#800000"
    assert color_for_node(node_name="kveikur") == "#f28c1b"
    assert color_for_node(node_name="cerulean") == "#0b7fc7"


def test_lookup_ignores_case() -> None:
    assert color_for_node(node_name="KEX") == NODE_COLORS["kex"]


def test_unknown_nodes_get_a_stable_color_from_the_fallback_palette() -> None:
    first: str = color_for_node(node_name="new-node")

    assert first == color_for_node(node_name="new-node")
    assert first in FALLBACK_PALETTE


def test_every_color_is_a_plain_hex_value() -> None:
    for color in (*NODE_COLORS.values(), *FALLBACK_PALETTE):
        assert re.fullmatch(HEX_COLOR, color)


@pytest.mark.parametrize("fallback", FALLBACK_PALETTE)
def test_fallback_colors_never_collide_with_configured_nodes(*, fallback: str) -> None:
    assert fallback not in NODE_COLORS.values()

from pathlib import Path
from typing import Optional

import pytest

from homelab_dashboard.node_images import find_node_image


def touch(*, directory: Path, name: str) -> None:
    (directory / name).write_bytes(b"")


def test_finds_an_image_named_after_the_node(tmp_path: Path) -> None:
    touch(directory=tmp_path, name="cerulean.png")

    assert find_node_image(node_name="cerulean", image_dir=tmp_path) == "/images/nodes/cerulean.png"


def test_node_name_matching_ignores_case(tmp_path: Path) -> None:
    touch(directory=tmp_path, name="kveikur.webp")

    assert find_node_image(node_name="Kveikur", image_dir=tmp_path) == "/images/nodes/kveikur.webp"


def test_returns_none_when_no_image_exists(tmp_path: Path) -> None:
    assert find_node_image(node_name="kex", image_dir=tmp_path) is None


@pytest.mark.parametrize("node_name", ["../secret", "a/b", "", "name with space", "..", "x\x00y"])
def test_rejects_names_that_could_escape_the_image_folder(*, node_name: str, tmp_path: Path) -> None:
    result: Optional[str] = find_node_image(node_name=node_name, image_dir=tmp_path)

    assert result is None

import re
from pathlib import Path
from typing import Final, Tuple, Union

IMAGE_URL_PREFIX: Final[str] = "/images/nodes"
IMAGE_EXTENSIONS: Final[Tuple[str, ...]] = (".png", ".jpg", ".jpeg", ".webp", ".gif")

# Node names come from Proxmox, so keep them to a plain filename stem.
_STEM_PATTERN: Final[str] = r"[A-Za-z0-9_-]+"


def find_node_image(*, node_name: str, image_dir: Path) -> Union[str, None]:
    """Return the URL of `<image_dir>/<node name>.<ext>` if such a file exists."""
    stem: str = node_name.lower()
    if not re.fullmatch(_STEM_PATTERN, stem):
        return None
    for extension in IMAGE_EXTENSIONS:
        if (image_dir / f"{stem}{extension}").is_file():
            return f"{IMAGE_URL_PREFIX}/{stem}{extension}"
    return None

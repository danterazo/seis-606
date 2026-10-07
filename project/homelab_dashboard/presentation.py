from pathlib import Path
from typing import Any, Dict, List

from homelab_dashboard.node_images import find_node_image
from homelab_dashboard.node_profiles import NodeProfile, node_sort_key, profile_for_node


def present_payload(*, payload: Dict[str, Any], image_dir: Path) -> Dict[str, Any]:
    """Order the nodes and add the display fields (name, initial, color, image, pinned address) the page needs."""
    nodes: List[Dict[str, Any]] = sorted(payload["nodes"], key=lambda node: node_sort_key(node_name=node["name"]))
    for node in nodes:
        profile: NodeProfile = profile_for_node(node_name=node["name"])
        node["display_name"] = profile.display_name
        node["initial"] = profile.initial
        node["color"] = profile.color
        node["memory_description"] = profile.memory_description
        node["image"] = find_node_image(node_name=node["name"], image_dir=image_dir)
        if profile.address is not None:
            node["address"] = profile.address
    return {**payload, "nodes": nodes}

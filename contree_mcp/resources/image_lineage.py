import json
from urllib.parse import unquote

from contree_mcp.context import CLIENT


async def image_lineage(image: str) -> str:
    """View image parent-child relationships and history.

    View image parent-child relationships and history. Free (no VM).

    URI: contree://image/{image}/lineage

    Returns lineage information including:
    - parent: Immediate parent image
    - children: Direct children of this image
    - ancestors: Full parent chain up to root
    - root: Root imported image
    - depth: Number of ancestors
    - is_known: Whether the image is in our lineage database
    - data: Stored metadata (command, operation_id, etc.)

    Example: contree://image/abc-123-def/lineage
    """
    cache = CLIENT.get().cache
    # URL-decode image since it may contain encoded characters
    decoded_image = unquote(image)

    entry = await cache.get("image", decoded_image)
    ancestors = await cache.get_ancestors("image", decoded_image)
    children = await cache.get_children("image", decoded_image)

    # Extract root from ancestors (last one) or self if no ancestors
    root = ancestors[-1].key if ancestors else (entry.key if entry else None)

    lineage_data = {
        "image": decoded_image,
        "parent": entry.data.get("parent_image") if entry else None,
        "children": [c.key for c in children],
        "ancestors": [a.key for a in ancestors],
        "root": root,
        "depth": len(ancestors),
        "is_known": entry is not None,
        "data": dict(entry.data) if entry else None,
    }
    return json.dumps(lineage_data, indent=2)

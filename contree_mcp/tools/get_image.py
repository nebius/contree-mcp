from contree_mcp.backend_types import Image
from contree_mcp.context import CLIENT


async def get_image(image: str) -> Image:
    """
    Get image details by UUID or tag. Free (no VM).

    TL;DR:
    - PURPOSE: Verify image exists or resolve tag to UUID
    - FORMAT: Use "tag:python:3.11" to look up by tag
    - COST: Free (no VM)

    USAGE:
    - Look up image metadata (UUID, tag, creation time)
    - Verify image exists before running commands
    - Resolve tag to underlying UUID
    - Prefer verifying an existing image before using import_image

    RETURNS: uuid, tag, created_at

    GUIDES:
    - [USEFUL] contree://guide/quickstart - UUIDs vs tags guidance
    """
    client = CLIENT.get()
    if image.startswith("tag:"):
        img = await client.get_image_by_tag(image[4:])
    else:
        img = await client.get_image(image)
    return Image(uuid=img.uuid, tag=img.tag, created_at=img.created_at)

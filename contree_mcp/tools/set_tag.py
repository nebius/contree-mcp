from contree_mcp.context import CLIENT

from .get_image import ImageOutput, image_output


async def set_tag(image_uuid: str, tag: str | None = None) -> ImageOutput:
    """
    Set or remove tag for container image. Free (no VM).
    TL;DR:
    - PURPOSE: Tag frequently-used images for reuse across sessions
    - REMOVE: Omit tag parameter to remove existing tag
    - COST: Free (no VM)

    USAGE:
    - Assign memorable name to frequently-used base images
    - Omit tag to remove existing tag from image
    - Prefer UUIDs directly for one-off operations
    - Tag format: `{scope}/{purpose}/{base}` where base includes its tag
    - Scope: `common` for reusable deps, or project name for project-specific
    - Purpose: describe what you added (e.g., python-ml, web-deps)

    RETURNS: uuid, tag, created_at

    GUIDES:
    - [ESSENTIAL] contree://guide/tagging - Agent tagging convention
    """
    client = CLIENT.get()
    if tag:
        img = await client.update_image_tag(image_uuid, tag)
    else:
        await client.delete_image_tag(image_uuid)
        img = await client.inspect_image(image_uuid)
    return image_output(img)

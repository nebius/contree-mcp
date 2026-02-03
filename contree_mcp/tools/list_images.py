from pydantic import BaseModel, Field

from contree_mcp.backend_types import Image
from contree_mcp.context import CLIENT


class ListImagesOutput(BaseModel):
    images: list[Image] = Field(description="List of images")


async def list_images(
    limit: int = 100,
    offset: int = 0,
    tagged: bool | None = None,
    tag_prefix: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> ListImagesOutput:
    """
    List available container images. Free (no VM).

    TL;DR:
    - PURPOSE: Find existing images before importing new ones
    - FIRST STEP: Use this before import_image to avoid the most expensive operation (can take dozens of minutes)
    - FILTER: Use tag_prefix to find specific image types
    - COST: Free (no VM)

    USAGE:
    - Browse available images to find base images for commands
    - Filter by tag prefix to find specific image types
    - Use returned UUIDs directly in run
    - Tag prefixes are typically `common/` or `<project>/`
    - Examples: tag_prefix="common/python", tag_prefix="myproj/"

    RETURNS: images[] with uuid, tag, created_at

    GUIDES:
    - [USEFUL] contree://guide/tagging - Agent tagging convention
    """

    client = CLIENT.get()
    images = await client.list_images(
        limit=limit,
        offset=offset,
        tagged=tagged,
        tag_prefix=tag_prefix,
        since=since,
        until=until,
    )
    return ListImagesOutput(images=[Image(uuid=img.uuid, tag=img.tag, created_at=img.created_at) for img in images])

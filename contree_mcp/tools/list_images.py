from pydantic import BaseModel, Field

from contree_mcp.context import CLIENT

from .get_image import ImageOutput, image_output


class ListImagesOutput(BaseModel):
    images: list[ImageOutput] = Field(description="List of images")


async def list_images(
    limit: int = 100,
    offset: int = 0,
    tagged: bool = False,
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
    # Strip trailing separators - backend validates tag format strictly
    tag = tag_prefix.rstrip(":/.") if tag_prefix else None
    response = await client.list_images(
        limit=limit,
        offset=offset,
        tagged=tagged,
        tag=tag,
        since=since,
        until=until,
    )
    images = response.images if isinstance(response.images, list) else []
    return ListImagesOutput(images=[image_output(img) for img in images])

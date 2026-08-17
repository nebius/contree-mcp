from contree_client.models import Image
from pydantic import BaseModel, Field

from contree_mcp.client_util import resolved
from contree_mcp.context import CLIENT


class ImageOutput(BaseModel):
    uuid: str = Field(description="Image UUID")
    tag: str | None = Field(default=None, description="Image tag or null")
    created_at: str = Field(default="", description="ISO 8601 creation timestamp")
    operation_uuid: str | None = Field(
        default=None,
        description=(
            "UUID of the operation that created this image. Null for images from another"
            " namespace (public/shared) or images not created by an operation."
        ),
    )


def image_output(img: Image) -> ImageOutput:
    return ImageOutput(
        uuid=resolved(img.uuid, ""),
        tag=resolved(img.tag, None),
        created_at=resolved(img.created_at, ""),
        operation_uuid=resolved(img.operation_uuid, None),
    )


async def get_image(image: str) -> ImageOutput:
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

    RETURNS: uuid, tag, created_at, operation_uuid (UUID of the operation that
    produced the image, or null for public/shared images)

    GUIDES:
    - [USEFUL] contree://guide/quickstart - UUIDs vs tags guidance
    """
    client = CLIENT.get()
    if image.startswith("tag:"):
        image_uuid = await client.inspect_find_image_by_tag(image[4:])
        img = await client.inspect_image(image_uuid)
    else:
        img = await client.inspect_image(image)
    return image_output(img)

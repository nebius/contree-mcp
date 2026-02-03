import base64
from urllib.parse import unquote

from contree_mcp.context import CLIENT


async def read_file(image: str, path: str) -> str:
    """Read a file from a container image.

    Read text files, config files, scripts, etc. without incurring VM costs.
    Binary files will be returned as BASE64-encoded strings prefixed with "base64:".

    URI: contree://image/{image}/read/{path}

    Where:
    - image: Image UUID or tag prefixed with "tag:" (e.g., "tag:alpine:latest")
    - path: File path without leading slash (e.g., "etc/passwd")

    Examples:
    - contree://image/abc-123-def/read/etc/passwd
    - contree://image/abc-123-def/read/usr/local/bin/python
    - contree://image/tag:alpine:latest/read/etc/alpine-release
    """
    client = CLIENT.get()
    image_uuid = await client.resolve_image(image)
    file_path = "/" + unquote(path).lstrip("/")
    content = await client.read_file(image_uuid, file_path)

    try:
        return content.decode("utf-8")
    except (UnicodeDecodeError, AttributeError):
        b64_content = base64.b64encode(content).decode("utf-8")
        return f"base64:{b64_content}"

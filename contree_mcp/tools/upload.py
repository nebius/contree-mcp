import base64
import os

from contree_mcp.backend_types import FileResponse
from contree_mcp.context import CLIENT


async def upload(
    path: str | None = None, content: str | None = None, content_base64: str | None = None
) -> FileResponse:
    """
    Upload file to Contree for use in containers. Free (no VM).

    TL;DR:
    - PURPOSE: Upload single file, get UUID for run's tool files param
    - PREFER RSYNC: For multiple files or directories (has caching)
    - BINARY: Use content_base64 for binary files

    USAGE:
    - Upload single file for injection into containers
    - Pass returned UUID to run's tool via files parameter
    - Use rsync instead for multiple files or directories

    RETURNS: uuid, sha256

    GUIDES:
    - [USEFUL] contree://guide/quickstart - File sync + execute patterns
    """

    if not path and not content and not content_base64:
        raise ValueError("One of 'path', 'content', or 'content_base64' is required")

    if path:
        path = os.path.expanduser(path)
        if not os.path.exists(path):
            raise ValueError(f"File not found: {path}")

    client = CLIENT.get()

    if path:
        with open(path, "rb") as f:
            result = await client.upload_file(f)
        return FileResponse(uuid=result.uuid, sha256=result.sha256)
    elif content_base64:
        data = base64.b64decode(content_base64)
    else:
        data = content.encode("utf-8")  # type: ignore[union-attr]

    result = await client.upload_file(data)
    return FileResponse(uuid=result.uuid, sha256=result.sha256)

import base64

from pydantic import BaseModel

from contree_mcp.context import CLIENT


class ReadFileOutput(BaseModel):
    path: str
    content: str
    encoding: str = "utf-8"
    bytes_size: int


async def read_file(image: str, path: str) -> ReadFileOutput:
    """
    Read a file from a container image. Free (no VM).

    TL;DR:
    - PURPOSE: Inspect file contents without starting a VM
    - ADVANTAGE: Instant access to configs and scripts - no VM cost
    - COST: Free (no VM)

    USAGE:
    - Inspect configuration files to understand image setup
    - Review scripts before execution to verify behavior
    - Check expected content without downloading to local filesystem
    - Prefer over run("cat") when you just need file contents

    RETURNS: path, content, size, is_text

    GUIDES:
    - [USEFUL] contree://guide/reference - Tool reference and resources
    """

    client = CLIENT.get()
    image_uuid = await client.resolve_image(image)
    content = await client.read_file(image_uuid, path)

    try:
        content_str = content.decode("utf-8")
        encoding = "utf-8"
    except UnicodeDecodeError:
        content_str = base64.b64encode(content).decode("utf-8")
        encoding = "base64"

    return ReadFileOutput(path=path, content=content_str, encoding=encoding, bytes_size=len(content))

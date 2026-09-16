import stat
from datetime import datetime, timezone
from urllib.parse import unquote

from contree_client.models import FileItem

from contree_mcp.context import CLIENT


def format_entry(entry: FileItem) -> str:
    timestamp = datetime.fromtimestamp(entry.mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
    name = entry.path
    if entry.is_symlink and entry.symlink_to:
        name = f"{name} -> {entry.symlink_to}"
    return f"{stat.filemode(entry.mode)} {entry.size:>10} {timestamp} {name}"


async def image_ls(image: str, path: str) -> str:
    """List files and directories in a container image.

    List files and directories in a container image. Free (no VM).
    Output is ls -alh style text format.

    URI: contree://image/{image}/ls/{path}

    Where:
    - image: Image UUID or tag prefixed with "tag:" (e.g., "tag:alpine:latest")
    - path: Directory path without leading slash (e.g., "etc" or "usr/bin")
    - For root directory, use path "."

    Examples:
    - contree://image/abc-123-def/ls/.
    - contree://image/abc-123-def/ls/etc
    - contree://image/abc-123-def/ls/usr/local/bin
    - contree://image/tag:alpine:latest/ls/etc
    """

    client = CLIENT.get()
    # URL-decode image and path since they may contain encoded characters
    decoded_image = unquote(image)
    decoded_path = unquote(path)
    image_uuid = await client.resolve_image(decoded_image)
    dir_path = "/" if decoded_path in (".", "") else "/" + decoded_path
    listing = await client.inspect_image_list(image_uuid, dir_path)
    return "\n".join(format_entry(entry) for entry in listing.files)

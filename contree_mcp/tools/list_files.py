from pydantic import BaseModel

from contree_mcp.context import CLIENT


class FileEntry(BaseModel):
    """File entry in directory listing."""

    name: str
    path: str
    type: str  # "file", "directory", "symlink"
    size: int
    mode: str | None = None
    target: str | None = None  # For symlinks


class ListFilesOutput(BaseModel):
    """Output of list_files tool."""

    path: str
    count: int
    files: list[FileEntry]


async def list_files(image: str, path: str = "/") -> ListFilesOutput:
    """
    List files and directories in a container image. Free (no VM).

    TL;DR:
    - PURPOSE: Inspect container filesystem without starting a VM
    - ADVANTAGE: Instant results, no VM cost - use before run
    - COST: Free (no VM)

    USAGE:
    - Explore image structure before running commands
    - Verify expected files exist at target paths
    - Check file permissions and symlink targets
    - Prefer over run("ls") for simple listings

    RETURNS: path, count, files[] with name, path, type, size, mode, target

    GUIDES:
    - [USEFUL] contree://guide/reference - Tool reference and resources
    """

    client = CLIENT.get()
    image_uuid = await client.resolve_image(image)

    # Normalize path
    if not path.startswith("/"):
        path = "/" + path
    if path == "/.":
        path = "/"

    listing = await client.list_directory(image_uuid, path)

    # Handle text response (shouldn't happen with as_text=False default)
    if isinstance(listing, str):
        return ListFilesOutput(path=path, count=0, files=[])

    files = []
    for f in listing.files:
        if f.is_symlink:
            file_type = "symlink"
        elif f.is_dir:
            file_type = "directory"
        else:
            file_type = "file"

        entry = FileEntry(
            name=f.path.rsplit("/", 1)[-1] if "/" in f.path else f.path,
            path=f.path,
            type=file_type,
            size=f.size,
            mode=oct(f.mode) if f.mode is not None else None,
            target=f.symlink_to if f.is_symlink and f.symlink_to else None,
        )
        files.append(entry)

    return ListFilesOutput(path=listing.path, count=len(files), files=files)

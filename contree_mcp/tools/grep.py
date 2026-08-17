from typing import Literal

from pydantic import BaseModel, Field

from contree_mcp.context import CLIENT


class GrepMatchOutput(BaseModel):
    path: str = Field(description="File path relative to the image rootfs")
    line_number: int = Field(description="1-based line number of the match")
    line_text: str = Field(description="The matching line")


class GrepOutput(BaseModel):
    path: str = Field(description="The path inside the image that was searched")
    patterns: list[str] = Field(description="The patterns that were searched for")
    truncated: bool = Field(description="True when max_total or the search deadline stopped the search early")
    matches: list[GrepMatchOutput] = Field(description="Matching lines")


async def grep(
    image: str,
    pattern: str,
    path: str | None = None,
    glob: str | None = None,
    max_count: int | None = None,
    max_total: int | None = None,
    case: Literal["sensitive", "insensitive", "smart"] | None = None,
) -> GrepOutput:
    """
    Search file contents in a container image using ripgrep. Free (no VM).

    TL;DR:
    - PURPOSE: Search file contents without spawning a VM
    - ADVANTAGE: Instant results via ripgrep on the persisted rootfs
    - COST: Free (no VM)

    USAGE:
    - Find where a config key, symbol, or string is defined before running commands
    - Narrow with `glob` (e.g. "*.py") and `path` to scope the search
    - `pattern` is a Rust-flavored regex, not a plain substring
    - Prefer over run("grep ...") for content searches — no VM needed
    - Symlinks are never followed; binary files (containing a NUL byte) are skipped

    RETURNS: path, patterns, truncated, matches[] with path, line_number, line_text

    GUIDES:
    - [USEFUL] contree://guide/reference - Tool reference and resources
    """
    client = CLIENT.get()
    image_uuid = await client.resolve_image(image)
    result = await client.inspect_image_grep(
        image_uuid,
        pattern,
        path=path,
        glob=glob,
        max_count=max_count,
        max_total=max_total,
        case=case,
    )
    return GrepOutput(
        path=result.path,
        patterns=result.patterns,
        truncated=result.truncated,
        matches=[
            GrepMatchOutput(path=m.path, line_number=m.line_number, line_text=m.line_text) for m in result.matches
        ],
    )

from pathlib import Path

from contree_mcp.context import CLIENT, FILES_CACHE


async def rsync(
    source: str,
    destination: str,
    exclude: list[str] | None = None,
) -> int:
    """
    Sync local files to Contree for use in container instances. Free (no VM).

    TL;DR:
    - PURPOSE: Prepare files for run injection
    - WORKFLOW: rsync -> get directory_state_id -> pass to run
    - CACHE: Smart caching uploads only changed files
    - EXCLUDE: Always exclude __pycache__, .git, node_modules, .venv

    USAGE:
    - source: Absolute path to local directory (~ expansion supported)
    - Sync directory: source="/path/to/project", destination="/app"
    - Exclude patterns: exclude=["__pycache__", "*.pyc", ".git"]

    RETURNS: directory_state_id (int) for run tool

    GUIDES:
    - [ESSENTIAL] contree://guide/quickstart - File sync + execute patterns
    """

    client = CLIENT.get()
    files_cache = FILES_CACHE.get()

    source_path = Path(source).expanduser()
    if not source_path.is_absolute():
        raise ValueError(f"source must be an absolute path, got: {source}")
    if not source_path.exists():
        raise ValueError(f"source path does not exist: {source_path}")

    destination = destination.rstrip("/")
    exclude = exclude or []

    return await files_cache.sync_directory(
        client=client,
        path=source_path,
        destination=destination,
        excludes=exclude,
    )

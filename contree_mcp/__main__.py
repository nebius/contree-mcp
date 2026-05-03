import asyncio
import importlib.metadata
import logging
import os
import sys

from contree_mcp.arguments import Parser
from contree_mcp.server import amain


def _print_version_and_exit() -> None:
    try:
        version = importlib.metadata.version("contree-mcp")
    except importlib.metadata.PackageNotFoundError:
        version = "unknown"
    print(f"contree-mcp {version}")
    sys.exit(0)


def main() -> None:
    if any(arg in ("--version", "-V") for arg in sys.argv[1:]):
        _print_version_and_exit()

    parser = Parser(
        config_files=[os.getenv("CONTREE_MCP_CONFIG", "~/.config/contree/mcp.ini")],
        auto_env_var_prefix="CONTREE_MCP_",
    )
    parser.parse_args()

    logging.basicConfig(level=parser.log_level, format="[%(levelname)s] %(message)s", stream=sys.stderr)
    try:
        asyncio.run(amain(parser))
    except KeyboardInterrupt:
        logging.info("Gracefully exited on keyboard interrupt")


if __name__ == "__main__":
    main()

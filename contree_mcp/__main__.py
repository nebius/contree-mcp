import asyncio
import logging
import os
import sys

from contree_mcp.arguments import Parser
from contree_mcp.server import amain


def main() -> None:
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

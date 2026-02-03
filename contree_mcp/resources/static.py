from typing import Any

from mcp.server.fastmcp.resources import Resource


class StaticResource(Resource):
    def __init__(self, content: str, /, **data: Any) -> None:
        super().__init__(**data)
        self._content = content

    async def read(self) -> str | bytes:
        return self._content

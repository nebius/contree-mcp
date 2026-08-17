import pytest
from contree_client.exceptions import NotFoundError
from contree_client.models import GrepMatch, GrepResult

from contree_mcp.tools.grep import GrepOutput, grep

from . import TestCase


def make_grep_match(
    path: str = "/etc/ssh/sshd_config",
    line_number: int = 57,
    line_text: str = "#PermitRootLogin prohibit-password\n",
) -> GrepMatch:
    return GrepMatch(
        path=path,
        line_number=line_number,
        absolute_offset=1712,
        line_text=line_text,
        line_bytes=len(line_text),
        submatches=[],
    )


class TestGrepHappyPath(TestCase):
    @pytest.mark.asyncio
    async def test_matches_by_uuid(self, contree_client) -> None:
        contree_client.mock(
            "inspect_image_grep",
            GrepResult(path="/etc", patterns=["^PermitRootLogin"], matches=[make_grep_match()], truncated=False),
        )

        result = await grep(image="12345678-9abc-baba-deda-0123456789ab", pattern="^PermitRootLogin", path="/etc")

        assert isinstance(result, GrepOutput)
        assert result.path == "/etc"
        assert result.patterns == ["^PermitRootLogin"]
        assert result.truncated is False
        assert len(result.matches) == 1
        assert result.matches[0].path == "/etc/ssh/sshd_config"
        assert result.matches[0].line_number == 57

    @pytest.mark.asyncio
    async def test_matches_by_tag(self, contree_client) -> None:
        contree_client.mock("inspect_find_image_by_tag", "img-1")
        contree_client.mock(
            "inspect_image_grep",
            GrepResult(path="/", patterns=["root"], matches=[], truncated=False),
        )

        result = await grep(image="tag:alpine:latest", pattern="root")

        assert result.matches == []
        assert contree_client.calls_for("inspect_find_image_by_tag")[0].args == ("alpine:latest",)

    @pytest.mark.asyncio
    async def test_forwards_optional_params(self, contree_client) -> None:
        contree_client.mock(
            "inspect_image_grep",
            GrepResult(path="/app", patterns=["TODO"], matches=[], truncated=True),
        )

        result = await grep(
            image="12345678-9abc-baba-deda-0123456789ab",
            pattern="TODO",
            path="/app",
            glob="*.py",
            max_count=5,
            max_total=100,
            case="insensitive",
        )

        assert result.truncated is True
        call = contree_client.calls_for("inspect_image_grep")[0]
        assert call.kwargs["path"] == "/app"
        assert call.kwargs["glob"] == "*.py"
        assert call.kwargs["max_count"] == 5
        assert call.kwargs["max_total"] == 100
        assert call.kwargs["case"] == "insensitive"


class TestGrepErrorHandling(TestCase):
    @pytest.mark.asyncio
    async def test_image_not_found(self, contree_client) -> None:
        contree_client.mock("inspect_image_grep", error=NotFoundError(404, "image not found"))

        with pytest.raises(NotFoundError):
            await grep(image="12345678-9abc-baba-deda-0123456789ab", pattern="foo")

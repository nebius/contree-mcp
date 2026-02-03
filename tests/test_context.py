"""Tests for contree_mcp.context module."""

import pytest

from contree_mcp.context import StrictContextVar


class TestStrictContextVar:
    """Tests for StrictContextVar class."""

    def test_get_raises_when_not_set(self) -> None:
        """Test that get() raises LookupError when value is not set."""
        var: StrictContextVar[str] = StrictContextVar("test_var")

        with pytest.raises(LookupError) as exc_info:
            var.get()

        assert "test_var" in str(exc_info.value)

    def test_get_returns_value_after_set(self) -> None:
        """Test that get() returns value after set()."""
        var: StrictContextVar[str] = StrictContextVar("test_var")

        var.set("hello")
        result = var.get()

        assert result == "hello"

    def test_set_overwrites_previous_value(self) -> None:
        """Test that set() overwrites previous value."""
        var: StrictContextVar[int] = StrictContextVar("test_var")

        var.set(1)
        var.set(2)
        result = var.get()

        assert result == 2

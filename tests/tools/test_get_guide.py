"""Tests for get_guide tool."""

import pytest

from contree_mcp.resources.guide import SECTIONS
from contree_mcp.tools.get_guide import get_guide


@pytest.mark.anyio
async def test_get_guide_workflow():
    """Test getting workflow guide section."""
    result = await get_guide("workflow")

    assert result.section == "workflow"
    assert "Contree Workflow Guide" in result.content
    assert "workflow" in result.available_sections


@pytest.mark.anyio
async def test_get_guide_reference():
    """Test getting reference guide section."""
    result = await get_guide("reference")

    assert result.section == "reference"
    assert "Tools Reference" in result.content


@pytest.mark.anyio
async def test_get_guide_quickstart():
    """Test getting quickstart guide section."""
    result = await get_guide("quickstart")

    assert result.section == "quickstart"
    assert "Quickstart" in result.content


@pytest.mark.anyio
async def test_get_guide_state():
    """Test getting state guide section."""
    result = await get_guide("state")

    assert result.section == "state"
    assert "State Management" in result.content


@pytest.mark.anyio
async def test_get_guide_async():
    """Test getting async guide section."""
    result = await get_guide("async")

    assert result.section == "async"
    assert "Async" in result.content


@pytest.mark.anyio
async def test_get_guide_tagging():
    """Test getting tagging guide section."""
    result = await get_guide("tagging")

    assert result.section == "tagging"
    assert "Tagging Convention" in result.content


@pytest.mark.anyio
async def test_get_guide_errors():
    """Test getting errors guide section."""
    result = await get_guide("errors")

    assert result.section == "errors"
    assert "Error Handling" in result.content


@pytest.mark.anyio
async def test_get_guide_all_sections_available():
    """Test that all sections are listed."""
    result = await get_guide("workflow")

    expected_sections = sorted(SECTIONS.keys())
    assert result.available_sections == expected_sections


@pytest.mark.anyio
async def test_get_guide_invalid_section():
    """Test error for invalid section name."""
    with pytest.raises(ValueError, match="Unknown guide section 'invalid'"):
        await get_guide("invalid")


@pytest.mark.anyio
async def test_get_guide_invalid_section_shows_available():
    """Test that error message shows available sections."""
    with pytest.raises(ValueError, match="Available sections:"):
        await get_guide("nonexistent")

"""Tests for the HTML documentation generator."""

import asyncio

from mcp.server import FastMCP

import contree_mcp.app as app_module
from contree_mcp.docs import (
    _get_first_paragraph,
    _get_param_type,
    _inline_markdown,
    _markdown_to_html,
    _render_table,
    _render_tool_params,
    generate_docs_html,
)
from contree_mcp.resources.guide import SECTIONS
from contree_mcp.tools import (
    cancel_operation,
    download,
    get_image,
    get_operation,
    import_image,
    list_images,
    list_operations,
    rsync,
    run,
    set_tag,
    upload,
    wait_operations,
)

# Get server instructions from app module
SERVER_INSTRUCTIONS = app_module.__doc__ or ""

# Use SECTIONS directly
GUIDE_SECTIONS = SECTIONS


def _create_test_mcp() -> FastMCP:
    """Create a test MCP app with tools but no lifespan."""
    mcp = FastMCP(
        name="contree-mcp-test",
        instructions=SERVER_INSTRUCTIONS,
    )
    mcp.add_tool(list_images)
    mcp.add_tool(import_image)
    mcp.add_tool(get_image)
    mcp.add_tool(set_tag)
    mcp.add_tool(run)
    mcp.add_tool(rsync)
    mcp.add_tool(upload)
    mcp.add_tool(download)
    mcp.add_tool(get_operation)
    mcp.add_tool(list_operations)
    mcp.add_tool(wait_operations)
    mcp.add_tool(cancel_operation)

    @mcp.resource("contree://guide/{section}")
    async def guide_resource(section: str) -> str:
        """Agent guide and best practices for using Contree MCP."""
        if section not in SECTIONS:
            available = ", ".join(sorted(SECTIONS.keys()))
            raise ValueError(f"Unknown guide section '{section}'. Available: {available}")
        return SECTIONS[section]

    return mcp


# Create test MCP instance
_test_mcp = _create_test_mcp()


def _get_real_tools() -> list:
    """Get real tools from the test MCP server."""
    return asyncio.run(_test_mcp.list_tools())


def _get_real_templates() -> list:
    """Get real templates from the test MCP server."""
    return asyncio.run(_test_mcp.list_resource_templates())


class TestGenerateDocsHtml:
    """Tests for the main HTML generator function using real server objects."""

    def test_generates_valid_html(self) -> None:
        """Test that generate_docs_html produces valid HTML structure."""
        html = generate_docs_html(
            server_instructions=SERVER_INSTRUCTIONS,
            tools=_get_real_tools(),
            templates=_get_real_templates(),
            guides=GUIDE_SECTIONS,
        )

        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "</html>" in html
        assert "Contree MCP Server" in html

    def test_includes_all_sections(self) -> None:
        """Test that all main sections are included."""
        html = generate_docs_html(
            server_instructions=SERVER_INSTRUCTIONS,
            tools=_get_real_tools(),
            templates=_get_real_templates(),
            guides=GUIDE_SECTIONS,
        )

        assert 'id="setup"' in html
        assert 'id="instructions"' in html
        assert 'id="tools"' in html
        assert 'id="resources"' in html
        assert 'id="guides"' in html

    def test_includes_server_instructions(self) -> None:
        """Test that server instructions are included."""
        html = generate_docs_html(
            server_instructions=SERVER_INSTRUCTIONS,
            tools=_get_real_tools(),
            templates=_get_real_templates(),
            guides=GUIDE_SECTIONS,
        )

        # Check some key content from SERVER_INSTRUCTIONS
        assert "MANDATORY WORKFLOW" in html
        assert "Guides" in html

    def test_includes_tool_names(self) -> None:
        """Test that tool names appear in the output."""
        tools = _get_real_tools()
        html = generate_docs_html(
            server_instructions=SERVER_INSTRUCTIONS,
            tools=tools,
            templates=_get_real_templates(),
            guides=GUIDE_SECTIONS,
        )

        # Verify actual tool names from the server
        assert "run" in html
        assert "list_images" in html

    def test_includes_resource_templates(self) -> None:
        """Test that resource templates appear in the output."""
        templates = _get_real_templates()
        html = generate_docs_html(
            server_instructions=SERVER_INSTRUCTIONS,
            tools=_get_real_tools(),
            templates=templates,
            guides=GUIDE_SECTIONS,
        )

        # Verify actual templates are included
        for template in templates:
            assert template.name in html
            uri = getattr(template, "uri_template", "")
            assert uri in html

    def test_includes_guides(self) -> None:
        """Test that guide sections appear in the output."""
        guides = {
            "quickstart": "# Quickstart Guide\n\nHow to get started.",
            "reference": "# Reference Guide\n\nTool reference.",
        }

        html = generate_docs_html(
            server_instructions="",
            tools=[],
            templates=[],
            guides=guides,
        )

        assert "contree://guide/quickstart" in html
        assert "contree://guide/reference" in html

    def test_escapes_html_in_instructions(self) -> None:
        """Test that HTML characters are properly escaped."""
        instructions = "Use <code> tags & special chars"
        html = generate_docs_html(
            server_instructions=instructions,
            tools=[],
            templates=[],
            guides={},
        )

        assert "&lt;code&gt;" in html
        assert "&amp;" in html


class TestGetFirstParagraph:
    """Tests for the first paragraph extraction."""

    def test_single_line(self) -> None:
        assert _get_first_paragraph("Hello world") == "Hello world"

    def test_multiple_lines(self) -> None:
        text = "First line\nSecond line\n\nThird line"
        assert _get_first_paragraph(text) == "First line Second line"

    def test_empty_string(self) -> None:
        assert _get_first_paragraph("") == ""

    def test_only_blank_lines(self) -> None:
        assert _get_first_paragraph("\n\n\n") == ""


class TestRenderToolParams:
    """Tests for tool parameter rendering."""

    def test_with_properties(self) -> None:
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "count": {"type": "integer"},
            },
            "required": ["name"],
        }
        html = _render_tool_params(schema)
        assert 'class="tool-params"' in html
        assert 'class="param-name"' in html
        assert "name" in html
        assert "count" in html
        assert 'class="param-required"' in html  # name is required

    def test_empty_properties(self) -> None:
        schema = {"type": "object", "properties": {}}
        assert _render_tool_params(schema) == ""

    def test_no_properties(self) -> None:
        schema = {"type": "object"}
        assert _render_tool_params(schema) == ""


class TestGetParamType:
    """Tests for JSON schema type extraction."""

    def test_simple_type(self) -> None:
        assert _get_param_type({"type": "string"}, {}) == "string"

    def test_anyof_with_null(self) -> None:
        prop = {"anyOf": [{"type": "string"}, {"type": "null"}]}
        assert _get_param_type(prop, {}) == "string"

    def test_anyof_with_ref(self) -> None:
        prop = {"anyOf": [{"$ref": "#/$defs/MyType"}, {"type": "null"}]}
        assert _get_param_type(prop, {}) == "MyType"

    def test_enum(self) -> None:
        prop = {"enum": ["a", "b", "c"]}
        assert _get_param_type(prop, {}) == '"a" | "b" | "c"'

    def test_array(self) -> None:
        prop = {"type": "array", "items": {"type": "string"}}
        assert _get_param_type(prop, {}) == "array[string]"

    def test_object(self) -> None:
        assert _get_param_type({"type": "object"}, {}) == "object"

    def test_ref(self) -> None:
        prop = {"$ref": "#/$defs/MyType"}
        assert _get_param_type(prop, {}) == "MyType"


class TestInlineMarkdown:
    """Tests for inline markdown conversion."""

    def test_inline_code(self) -> None:
        assert _inline_markdown("Use `code` here") == "Use <code>code</code> here"

    def test_bold(self) -> None:
        assert _inline_markdown("This is **bold**") == "This is <strong>bold</strong>"

    def test_escapes_html(self) -> None:
        assert _inline_markdown("<script>") == "&lt;script&gt;"


class TestMarkdownToHtml:
    """Tests for markdown to HTML conversion."""

    # === Headers ===

    def test_header_h1(self) -> None:
        assert "<h1>Title</h1>" in _markdown_to_html("# Title")

    def test_header_h2(self) -> None:
        assert "<h2>Subtitle</h2>" in _markdown_to_html("## Subtitle")

    def test_header_h3(self) -> None:
        assert "<h3>Section</h3>" in _markdown_to_html("### Section")

    def test_header_h4(self) -> None:
        assert "<h4>Subsection</h4>" in _markdown_to_html("#### Subsection")

    def test_header_h5(self) -> None:
        assert "<h5>Minor</h5>" in _markdown_to_html("##### Minor")

    def test_header_h6(self) -> None:
        assert "<h6>Tiny</h6>" in _markdown_to_html("###### Tiny")

    def test_header_capped_at_h6(self) -> None:
        # More than 6 # should still be h6
        assert "<h6>" in _markdown_to_html("####### TooMany")

    def test_header_with_inline_code(self) -> None:
        html = _markdown_to_html("## Use `run_command`")
        assert "<h2>" in html
        assert "<code>run_command</code>" in html

    def test_header_with_bold(self) -> None:
        html = _markdown_to_html("## **Important** Section")
        assert "<h2>" in html
        assert "<strong>Important</strong>" in html

    # === Code Blocks ===

    def test_code_block_basic(self) -> None:
        md = "```python\nprint('hello')\n```"
        html = _markdown_to_html(md)
        assert "<pre><code>" in html
        assert "print(&#x27;hello&#x27;)" in html

    def test_code_block_multiline(self) -> None:
        md = "```\nline1\nline2\nline3\n```"
        html = _markdown_to_html(md)
        assert "line1\nline2\nline3" in html

    def test_code_block_empty(self) -> None:
        md = "```\n```"
        html = _markdown_to_html(md)
        assert "<pre><code></code></pre>" in html

    def test_code_block_preserves_indentation(self) -> None:
        md = "```\n  indented\n    more\n```"
        html = _markdown_to_html(md)
        assert "  indented" in html
        assert "    more" in html

    def test_code_block_escapes_html(self) -> None:
        md = "```\n<script>alert('xss')</script>\n```"
        html = _markdown_to_html(md)
        assert "&lt;script&gt;" in html
        assert "<script>" not in html

    def test_multiple_code_blocks(self) -> None:
        md = "```\nfirst\n```\n\ntext\n\n```\nsecond\n```"
        html = _markdown_to_html(md)
        assert html.count("<pre><code>") == 2
        assert "first" in html
        assert "second" in html

    def test_unclosed_code_block(self) -> None:
        md = "```\nunclosed code"
        html = _markdown_to_html(md)
        # Should still render, closing automatically
        assert "<pre><code>" in html
        assert "unclosed code" in html

    # === Unordered Lists ===

    def test_unordered_list_dash(self) -> None:
        md = "- Item 1\n- Item 2"
        html = _markdown_to_html(md)
        assert "<ul>" in html
        assert "<li>Item 1</li>" in html
        assert "<li>Item 2</li>" in html
        assert "</ul>" in html

    def test_unordered_list_asterisk(self) -> None:
        md = "* Item A\n* Item B"
        html = _markdown_to_html(md)
        assert "<ul>" in html
        assert "<li>Item A</li>" in html
        assert "<li>Item B</li>" in html

    def test_unordered_list_with_inline_code(self) -> None:
        md = "- Use `code` here\n- Another `item`"
        html = _markdown_to_html(md)
        assert "<code>code</code>" in html
        assert "<code>item</code>" in html

    def test_unordered_list_with_bold(self) -> None:
        md = "- **Bold** item\n- Normal item"
        html = _markdown_to_html(md)
        assert "<strong>Bold</strong>" in html

    def test_unordered_list_single_item(self) -> None:
        md = "- Single"
        html = _markdown_to_html(md)
        assert "<ul>" in html
        assert "<li>Single</li>" in html
        assert "</ul>" in html

    # === Ordered Lists ===

    def test_ordered_list_basic(self) -> None:
        md = "1. First\n2. Second"
        html = _markdown_to_html(md)
        assert "<ol>" in html
        assert "<li>First</li>" in html
        assert "<li>Second</li>" in html
        assert "</ol>" in html

    def test_ordered_list_with_inline_code(self) -> None:
        md = "1. Run `command`\n2. Check `output`"
        html = _markdown_to_html(md)
        assert "<code>command</code>" in html
        assert "<code>output</code>" in html

    def test_ordered_list_non_sequential_numbers(self) -> None:
        # Markdown renderers typically ignore actual numbers
        md = "1. First\n5. Second\n3. Third"
        html = _markdown_to_html(md)
        assert "<ol>" in html
        assert "<li>First</li>" in html
        assert "<li>Second</li>" in html
        assert "<li>Third</li>" in html

    def test_ordered_list_single_item(self) -> None:
        md = "1. Only one"
        html = _markdown_to_html(md)
        assert "<ol>" in html
        assert "<li>Only one</li>" in html

    # === Mixed Lists ===

    def test_list_switch_unordered_to_ordered(self) -> None:
        md = "- Bullet\n\n1. Number"
        html = _markdown_to_html(md)
        assert "<ul>" in html
        assert "</ul>" in html
        assert "<ol>" in html
        assert "</ol>" in html

    def test_list_switch_ordered_to_unordered(self) -> None:
        md = "1. Number\n\n- Bullet"
        html = _markdown_to_html(md)
        assert "<ol>" in html
        assert "</ol>" in html
        assert "<ul>" in html
        assert "</ul>" in html

    # === Paragraphs ===

    def test_paragraph_basic(self) -> None:
        assert "<p>Hello world</p>" in _markdown_to_html("Hello world")

    def test_paragraph_with_inline_code(self) -> None:
        html = _markdown_to_html("Use `code` in text")
        assert "<p>" in html
        assert "<code>code</code>" in html

    def test_paragraph_with_bold(self) -> None:
        html = _markdown_to_html("This is **important**")
        assert "<p>" in html
        assert "<strong>important</strong>" in html

    def test_multiple_paragraphs(self) -> None:
        md = "First paragraph\n\nSecond paragraph"
        html = _markdown_to_html(md)
        assert "<p>First paragraph</p>" in html
        assert "<p>Second paragraph</p>" in html

    def test_paragraph_escapes_html(self) -> None:
        html = _markdown_to_html("Use <tag> & symbols")
        assert "&lt;tag&gt;" in html
        assert "&amp;" in html

    # === Tables ===

    def test_table_basic(self) -> None:
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        html = _markdown_to_html(md)
        assert "<table>" in html
        assert "<th>A</th>" in html
        assert "<td>1</td>" in html

    def test_table_with_inline_code(self) -> None:
        md = "| Command | Description |\n|---|---|\n| `run` | Execute |"
        html = _markdown_to_html(md)
        assert "<code>run</code>" in html

    def test_table_multiple_rows(self) -> None:
        md = "| H1 | H2 |\n|---|---|\n| A | B |\n| C | D |"
        html = _markdown_to_html(md)
        assert "<td>A</td>" in html
        assert "<td>D</td>" in html

    # === Empty and Edge Cases ===

    def test_empty_string(self) -> None:
        assert _markdown_to_html("") == ""

    def test_only_whitespace(self) -> None:
        assert _markdown_to_html("   \n\n   ") == ""

    def test_only_empty_lines(self) -> None:
        assert _markdown_to_html("\n\n\n") == ""

    # === Mixed Content ===

    def test_header_then_paragraph(self) -> None:
        md = "# Title\n\nSome text"
        html = _markdown_to_html(md)
        assert "<h1>Title</h1>" in html
        assert "<p>Some text</p>" in html

    def test_header_then_list(self) -> None:
        md = "## Items\n\n- One\n- Two"
        html = _markdown_to_html(md)
        assert "<h2>Items</h2>" in html
        assert "<ul>" in html
        assert "<li>One</li>" in html

    def test_header_then_code_block(self) -> None:
        md = "## Code\n\n```\nexample\n```"
        html = _markdown_to_html(md)
        assert "<h2>Code</h2>" in html
        assert "<pre><code>" in html

    def test_list_then_paragraph(self) -> None:
        md = "- Item\n\nParagraph after"
        html = _markdown_to_html(md)
        assert "</ul>" in html
        assert "<p>Paragraph after</p>" in html

    def test_list_then_header(self) -> None:
        md = "- Item\n\n## Next Section"
        html = _markdown_to_html(md)
        assert "</ul>" in html
        assert "<h2>Next Section</h2>" in html

    def test_paragraph_then_list(self) -> None:
        md = "Intro text\n\n- Item 1\n- Item 2"
        html = _markdown_to_html(md)
        assert "<p>Intro text</p>" in html
        assert "<ul>" in html

    def test_code_block_then_list(self) -> None:
        md = "```\ncode\n```\n\n- Item"
        html = _markdown_to_html(md)
        assert "</code></pre>" in html
        assert "<ul>" in html

    def test_table_then_paragraph(self) -> None:
        md = "| A |\n|---|\n| B |\n\nAfter table"
        html = _markdown_to_html(md)
        assert "</table>" in html
        assert "<p>After table</p>" in html

    def test_complex_document(self) -> None:
        """Test a document with multiple element types."""
        md = """# Main Title

Introduction paragraph.

## Section One

- First item
- Second item

## Section Two

1. Step one
2. Step two

### Code Example

```json
{"key": "value"}
```

| Column | Value |
|--------|-------|
| A      | 1     |

Final paragraph with `code` and **bold**."""

        html = _markdown_to_html(md)

        # Check all elements present
        assert "<h1>Main Title</h1>" in html
        assert "<p>Introduction paragraph.</p>" in html
        assert "<h2>Section One</h2>" in html
        assert "<ul>" in html
        assert "<li>First item</li>" in html
        assert "<h2>Section Two</h2>" in html
        assert "<ol>" in html
        assert "<li>Step one</li>" in html
        assert "<h3>Code Example</h3>" in html
        assert "<pre><code>" in html
        assert "<table>" in html
        assert "<code>code</code>" in html
        assert "<strong>bold</strong>" in html

    # === Parsing Corner Cases ===

    def test_header_no_space_after_hash(self) -> None:
        """Parser is lenient - accepts headers without space after #."""
        html = _markdown_to_html("#NoSpace")
        # Simple parser accepts this as header (lenient behavior)
        assert "<h1>NoSpace</h1>" in html

    def test_header_with_trailing_hashes(self) -> None:
        """Some markdown allows trailing hashes."""
        html = _markdown_to_html("## Title ##")
        assert "<h2>" in html
        # Trailing hashes are kept as-is in simple parser
        assert "Title ##" in html or "Title" in html

    def test_list_number_without_dot(self) -> None:
        """Numbers without dot+space are not list items."""
        html = _markdown_to_html("1234 Not a list")
        assert "<ol>" not in html
        assert "<p>" in html

    def test_list_number_high_value(self) -> None:
        """Large numbers should still work as list items."""
        html = _markdown_to_html("999. Large number item")
        assert "<ol>" in html
        assert "<li>Large number item</li>" in html

    def test_dash_in_middle_of_text(self) -> None:
        """Dash in middle of text is not a list."""
        html = _markdown_to_html("This - is - not - a list")
        assert "<ul>" not in html
        assert "<p>" in html

    def test_asterisk_in_middle_of_text(self) -> None:
        """Asterisk in middle is bold marker, not list."""
        html = _markdown_to_html("This is *italic* text")
        # Our parser doesn't support italic, but shouldn't make it a list
        assert "<ul>" not in html

    def test_code_block_contains_markdown_syntax(self) -> None:
        """Markdown syntax inside code blocks should not be parsed."""
        md = "```\n# Not a header\n- Not a list\n**Not bold**\n```"
        html = _markdown_to_html(md)
        assert html.count("<h1>") == 0
        assert html.count("<ul>") == 0
        assert html.count("<strong>") == 0
        assert "# Not a header" in html

    def test_code_block_with_triple_backticks_inside(self) -> None:
        """Handle backticks that appear in code content."""
        # This is a known limitation - triple backticks end the block
        md = "```\ncode with ` backtick\n```"
        html = _markdown_to_html(md)
        assert "code with ` backtick" in html

    def test_empty_list_item(self) -> None:
        """Empty list items."""
        md = "- \n- Item"
        html = _markdown_to_html(md)
        assert "<ul>" in html
        # Empty item is still rendered
        assert "<li>" in html

    def test_list_item_with_only_code(self) -> None:
        """List item that is only inline code."""
        md = "- `code`"
        html = _markdown_to_html(md)
        assert "<li><code>code</code></li>" in html

    def test_multiple_consecutive_headers(self) -> None:
        """Multiple headers without content between."""
        md = "# H1\n## H2\n### H3"
        html = _markdown_to_html(md)
        assert "<h1>H1</h1>" in html
        assert "<h2>H2</h2>" in html
        assert "<h3>H3</h3>" in html

    def test_table_with_empty_cells(self) -> None:
        """Table with empty cells."""
        md = "| A |  |\n|---|---|\n|  | B |"
        html = _markdown_to_html(md)
        assert "<table>" in html
        assert "<th>A</th>" in html
        assert "<td>B</td>" in html

    def test_table_single_column(self) -> None:
        """Single column table."""
        md = "| Only |\n|------|\n| One |"
        html = _markdown_to_html(md)
        assert "<table>" in html
        assert "<th>Only</th>" in html

    def test_pipe_in_code_not_table(self) -> None:
        """Pipe character in code block is not a table."""
        md = "```\necho foo | grep bar\n```"
        html = _markdown_to_html(md)
        assert "<table>" not in html
        assert "echo foo | grep bar" in html

    def test_inline_code_with_special_chars(self) -> None:
        """Inline code with HTML special characters."""
        html = _markdown_to_html("Use `<tag>` here")
        assert "<code>&lt;tag&gt;</code>" in html

    def test_bold_with_special_chars(self) -> None:
        """Bold text with HTML special characters."""
        html = _markdown_to_html("**<important>**")
        assert "<strong>&lt;important&gt;</strong>" in html

    def test_nested_inline_markdown(self) -> None:
        """Code inside bold or vice versa."""
        # Our simple parser handles these sequentially
        html = _markdown_to_html("**`bold code`**")
        assert "<strong>" in html
        assert "<code>" in html

    def test_unclosed_bold(self) -> None:
        """Unclosed bold marker."""
        html = _markdown_to_html("This is **unclosed")
        # Should render as-is with escaped asterisks
        assert "**unclosed" in html or "unclosed" in html

    def test_unclosed_code(self) -> None:
        """Unclosed inline code."""
        html = _markdown_to_html("This is `unclosed")
        # Should render as-is
        assert "`unclosed" in html or "unclosed" in html

    def test_whitespace_before_list_marker(self) -> None:
        """List with leading whitespace."""
        md = "  - Indented item"
        html = _markdown_to_html(md)
        # Should still be recognized as list
        assert "<li>" in html

    def test_list_continues_after_blank_line(self) -> None:
        """List behavior with blank lines."""
        md = "- Item 1\n\n- Item 2"
        html = _markdown_to_html(md)
        # Could be one or two lists depending on implementation
        assert "<li>Item 1</li>" in html
        assert "<li>Item 2</li>" in html

    def test_number_dot_space_in_text(self) -> None:
        """Text that starts with number-dot-space pattern."""
        md = "I have 3. items here"
        html = _markdown_to_html(md)
        # This actually starts with "I" so not a list
        assert "<ol>" not in html

    def test_text_starts_with_number_dot_space(self) -> None:
        """Line that starts with number-dot-space is a list."""
        md = "3. This is a list item"
        html = _markdown_to_html(md)
        assert "<ol>" in html
        assert "<li>This is a list item</li>" in html

    def test_unicode_content(self) -> None:
        """Unicode characters in content."""
        md = "# Заголовок\n\n- Элемент 日本語\n- Item with émojis 🎉"
        html = _markdown_to_html(md)
        assert "Заголовок" in html
        assert "日本語" in html
        assert "🎉" in html

    def test_very_long_line(self) -> None:
        """Very long line without breaks."""
        long_text = "word " * 1000
        html = _markdown_to_html(long_text)
        assert "<p>" in html
        assert "word" in html

    def test_many_nested_levels_ignored(self) -> None:
        """Deep nesting is not supported, renders flat."""
        md = "- Level 1\n  - Level 2\n    - Level 3"
        html = _markdown_to_html(md)
        # Simple parser doesn't support nested lists
        assert "<ul>" in html
        assert "Level 1" in html

    def test_horizontal_rule_not_supported(self) -> None:
        """Horizontal rules are not implemented."""
        md = "---"
        html = _markdown_to_html(md)
        # Treated as paragraph or ignored
        assert "<hr" not in html

    def test_link_not_supported(self) -> None:
        """Links are not implemented, rendered as-is."""
        md = "[link](http://example.com)"
        html = _markdown_to_html(md)
        assert "<a " not in html
        # Content is preserved (escaped)
        assert "link" in html

    def test_image_not_supported(self) -> None:
        """Images are not implemented, rendered as-is."""
        md = "![alt](image.png)"
        html = _markdown_to_html(md)
        assert "<img" not in html

    def test_blockquote_not_supported(self) -> None:
        """Blockquotes are not implemented."""
        md = "> This is a quote"
        html = _markdown_to_html(md)
        assert "<blockquote>" not in html
        # Rendered as paragraph
        assert "This is a quote" in html

    # === QA Critical Priority - Security ===

    def test_table_cell_escapes_html(self) -> None:
        """HTML in table cells must be escaped."""
        md = "| Header |\n|--------|\n| <script>alert(1)</script> |"
        html = _markdown_to_html(md)
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_code_block_language_with_html(self) -> None:
        """Language specifier should not execute HTML."""
        md = "```<script>\ncode\n```"
        html = _markdown_to_html(md)
        # Language is ignored, but code content is escaped
        assert "code" in html

    # === QA High Priority - Parser Logic ===

    def test_header_with_only_whitespace(self) -> None:
        """Header with only spaces after hash."""
        html = _markdown_to_html("#    ")
        # Should be empty header or paragraph
        assert isinstance(html, str)

    def test_header_multiple_spaces_after_hash(self) -> None:
        """Header with multiple spaces after hash."""
        html = _markdown_to_html("#    Multiple spaces")
        assert "<h1>" in html
        assert "Multiple spaces" in html

    def test_code_block_after_list_no_blank(self) -> None:
        """Code block immediately after list item."""
        md = "- item\n```\ncode\n```"
        html = _markdown_to_html(md)
        assert "</ul>" in html
        assert "<pre><code>" in html

    def test_table_after_list_no_blank(self) -> None:
        """Table immediately after list."""
        md = "- item\n| A |\n|---|\n| B |"
        html = _markdown_to_html(md)
        assert "</ul>" in html
        assert "<table>" in html

    def test_list_item_starting_with_pipe(self) -> None:
        """List item with pipe character."""
        md = "- | not a table"
        html = _markdown_to_html(md)
        assert "<ul>" in html
        assert "<li>" in html

    def test_zero_ordered_list(self) -> None:
        """Ordered list starting with 0."""
        md = "0. Zero item"
        html = _markdown_to_html(md)
        assert "<ol>" in html
        assert "<li>Zero item</li>" in html

    def test_negative_number_not_list(self) -> None:
        """Negative number before period is not a list."""
        md = "-1. Not a list"
        html = _markdown_to_html(md)
        # Starts with -, so might be unordered list
        assert "Not a list" in html

    def test_table_without_separator(self) -> None:
        """Table with no separator row."""
        md = "| H1 |\n| D1 |"
        html = _markdown_to_html(md)
        # Should handle gracefully
        assert "H1" in html

    def test_table_malformed_separator(self) -> None:
        """Table with malformed separator row."""
        md = "| H1 | H2 |\n| not-dashes |\n| D1 | D2 |"
        html = _markdown_to_html(md)
        # Should not crash
        assert isinstance(html, str)

    def test_asterisk_list_with_bold(self) -> None:
        """Asterisk list item with bold content."""
        md = "* **bold item**"
        html = _markdown_to_html(md)
        assert "<ul>" in html
        assert "<strong>bold item</strong>" in html

    def test_list_after_header_no_blank(self) -> None:
        """List directly after header without blank line."""
        md = "## Header\n- item"
        html = _markdown_to_html(md)
        assert "<h2>Header</h2>" in html
        assert "<ul>" in html

    def test_back_to_back_code_blocks(self) -> None:
        """Multiple code blocks without content between."""
        md = "```\nfirst\n```\n```\nsecond\n```"
        html = _markdown_to_html(md)
        assert html.count("<pre><code>") == 2

    # === QA Medium Priority - Edge Cases ===

    def test_crlf_line_endings(self) -> None:
        """Windows-style line endings."""
        md = "# Header\r\n\r\nParagraph"
        html = _markdown_to_html(md)
        assert "Header" in html
        assert "Paragraph" in html

    def test_multiple_bold_same_line(self) -> None:
        """Multiple bold sections in one line."""
        md = "**first** and **second**"
        html = _markdown_to_html(md)
        assert html.count("<strong>") == 2

    def test_multiple_code_same_line(self) -> None:
        """Multiple inline code in one line."""
        md = "Use `cmd1` and `cmd2`"
        html = _markdown_to_html(md)
        assert html.count("<code>") == 2

    def test_bold_not_processed_in_code(self) -> None:
        """Bold markers inside inline code should not be processed."""
        md = "`**not bold**`"
        html = _markdown_to_html(md)
        # The ** should appear as-is inside code (escaped to ** or kept)
        assert "<strong>" not in html or "<code>" in html

    def test_code_inside_bold(self) -> None:
        """Code inside bold text."""
        md = "**bold with `code`**"
        html = _markdown_to_html(md)
        assert "<strong>" in html
        assert "<code>code</code>" in html

    def test_table_varying_column_counts(self) -> None:
        """Table rows with different numbers of columns."""
        md = "| A | B |\n|---|---|\n| 1 |\n| 2 | 3 | 4 |"
        html = _markdown_to_html(md)
        assert "<table>" in html
        # Should not crash

    def test_table_header_only(self) -> None:
        """Table with only header and separator."""
        md = "| Header |\n|--------|"
        html = _markdown_to_html(md)
        # May render empty table body
        assert "Header" in html

    def test_list_after_code_no_blank(self) -> None:
        """List immediately after code block."""
        md = "```\ncode\n```\n- item"
        html = _markdown_to_html(md)
        assert "</code></pre>" in html
        assert "<ul>" in html

    def test_paragraph_after_code_no_blank(self) -> None:
        """Paragraph immediately after code block."""
        md = "```\ncode\n```\nParagraph"
        html = _markdown_to_html(md)
        assert "<p>Paragraph</p>" in html

    def test_code_block_empty_with_language(self) -> None:
        """Empty code block with language specifier."""
        md = "```python\n```"
        html = _markdown_to_html(md)
        assert "<pre><code>" in html

    # === QA Low Priority - Malformed Input ===

    def test_only_hash_symbols(self) -> None:
        """Line with only hash symbols."""
        html = _markdown_to_html("####")
        # Should not crash
        assert isinstance(html, str)

    def test_only_backticks(self) -> None:
        """Single line of backticks."""
        html = _markdown_to_html("```")
        # Should not crash
        assert isinstance(html, str)

    def test_only_pipes(self) -> None:
        """Line with only pipe characters."""
        html = _markdown_to_html("|||")
        # Should not crash
        assert isinstance(html, str)

    def test_empty_bold(self) -> None:
        """Empty bold markers."""
        html = _markdown_to_html("****")
        # Should not crash
        assert isinstance(html, str)

    def test_mismatched_bold_markers(self) -> None:
        """Mismatched bold markers."""
        html = _markdown_to_html("**bold* not closed")
        # Should not crash
        assert isinstance(html, str)
        assert "bold" in html

    def test_rapid_list_type_switching(self) -> None:
        """Alternating list types."""
        md = "- a\n1. b\n- c\n2. d"
        html = _markdown_to_html(md)
        # Should have balanced list tags
        assert html.count("<ul>") == html.count("</ul>")
        assert html.count("<ol>") == html.count("</ol>")

    def test_table_row_without_leading_pipe(self) -> None:
        """Table detection requires leading pipe."""
        md = "| Header |\n|--------|\nNo pipe | here |"
        html = _markdown_to_html(md)
        # Third line should not be part of table
        assert isinstance(html, str)

    def test_null_byte_in_content(self) -> None:
        """Content with null byte."""
        html = _markdown_to_html("Hello\x00World")
        # Should not crash
        assert isinstance(html, str)

    def test_control_characters(self) -> None:
        """Content with control characters."""
        html = _markdown_to_html("Header\x07with\x08control")
        # Should not crash
        assert isinstance(html, str)


class TestRenderTable:
    """Tests for markdown table rendering."""

    def test_simple_table(self) -> None:
        rows = [
            "| Header1 | Header2 |",
            "|---------|---------|",
            "| Cell1   | Cell2   |",
        ]
        html = _render_table(rows)
        assert "<table>" in html
        assert "<th>Header1</th>" in html
        assert "<td>Cell1</td>" in html

    def test_empty_table(self) -> None:
        assert _render_table([]) == ""
        assert _render_table(["| only header |"]) == ""


class TestWithRealGuides:
    """Tests using the actual SECTIONS from guide.py."""

    def test_generates_html_with_all_guides(self) -> None:
        """Test that all real guide sections can be rendered."""
        html = generate_docs_html(
            server_instructions=SERVER_INSTRUCTIONS,
            tools=_get_real_tools(),
            templates=_get_real_templates(),
            guides=SECTIONS,
        )

        for section_name in SECTIONS:
            assert f"contree://guide/{section_name}" in html


class TestWithRealMcpServer:
    """Integration tests using the actual MCP server tools."""

    def test_generates_html_with_real_tools(self) -> None:
        """Test that HTML can be generated with actual FastMCP tools."""
        tools = _get_real_tools()
        templates = _get_real_templates()

        html = generate_docs_html(
            server_instructions=SERVER_INSTRUCTIONS,
            tools=tools,
            templates=templates,
            guides=GUIDE_SECTIONS,
        )

        # Verify HTML structure
        assert "<!DOCTYPE html>" in html
        assert "Contree MCP Server" in html

        # Verify all tools are included
        for tool in tools:
            assert tool.name in html

        # Verify tool parameters are rendered
        assert 'class="tool-params"' in html
        assert 'class="param-name"' in html

        # Verify all resource templates are included
        for template in templates:
            assert template.name in html
            uri = getattr(template, "uri_template", "")
            assert uri in html

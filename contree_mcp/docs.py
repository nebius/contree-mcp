"""HTML documentation page generator for Contree MCP server."""

from __future__ import annotations

import html
from collections.abc import Mapping
from typing import Any

CSS_STYLES = """\
:root {
  --bg-primary: #0d1117;
  --bg-secondary: #161b22;
  --bg-tertiary: #21262d;
  --text-primary: #e6edf3;
  --text-secondary: #8b949e;
  --text-muted: #6e7681;
  --border-color: #30363d;
  --accent: #58a6ff;
  --accent-hover: #79b8ff;
  --success: #3fb950;
  --warning: #d29922;
  --code-bg: #343a42;
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
  background: var(--bg-primary);
  color: var(--text-primary);
  line-height: 1.6;
  padding: 0;
  min-height: 100vh;
}

header {
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
  padding: 2rem;
  text-align: center;
}

header h1 {
  font-size: 2.5rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.tagline {
  color: var(--text-secondary);
  font-size: 1.1rem;
}

nav {
  background: var(--bg-tertiary);
  border-bottom: 1px solid var(--border-color);
  padding: 0.75rem 2rem;
  display: flex;
  gap: 1.5rem;
  flex-wrap: wrap;
  justify-content: center;
  position: sticky;
  top: 0;
  z-index: 100;
}

nav a {
  color: var(--text-secondary);
  text-decoration: none;
  font-weight: 500;
  transition: color 0.2s;
}

nav a:hover {
  color: var(--accent);
}

main {
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem;
}

section {
  margin-bottom: 3rem;
}

h2 {
  font-size: 1.75rem;
  font-weight: 600;
  margin-bottom: 1.5rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border-color);
  color: var(--text-primary);
}

h3 {
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
  color: var(--text-primary);
}

.connection-box {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 1.5rem;
  margin-bottom: 1rem;
}

.connection-box p {
  color: var(--text-secondary);
  margin-bottom: 0.75rem;
}

.endpoint {
  display: block;
  background: var(--code-bg);
  padding: 0.75rem 1rem;
  border-radius: 6px;
  font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
  font-size: 0.95rem;
  color: var(--accent);
  margin-bottom: 0.75rem;
}

.hint {
  font-size: 0.9rem;
  color: var(--text-muted);
}

.hint code {
  background: var(--code-bg);
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-size: 0.85rem;
}

.instructions-box {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 1.5rem;
}

.instructions-box pre {
  background: var(--code-bg);
  padding: 1rem;
  border-radius: 6px;
  overflow-x: auto;
  font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
  font-size: 0.9rem;
  line-height: 1.5;
  color: var(--text-secondary);
}

.tools-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--bg-secondary);
  border-radius: 8px;
  overflow: hidden;
}

.tools-table th {
  background: var(--bg-tertiary);
  padding: 1rem;
  text-align: left;
  font-weight: 600;
  border-bottom: 1px solid var(--border-color);
}

.tools-table td {
  padding: 1rem;
  border-bottom: 1px solid var(--border-color);
  vertical-align: top;
}

.tools-table tr:last-child td {
  border-bottom: none;
}

.tool-name {
  font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
  color: var(--accent);
  font-weight: 500;
}

.tool-desc {
  color: var(--text-secondary);
  font-size: 0.95rem;
}

.tool-params {
  font-size: 0.85rem;
  color: var(--text-muted);
  margin-top: 0.5rem;
}

.param-name {
  color: var(--success);
  font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
}

.param-required {
  color: var(--warning);
  font-size: 0.75rem;
  margin-left: 0.25rem;
}

.resources-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--bg-secondary);
  border-radius: 8px;
  overflow: hidden;
}

.resources-table th {
  background: var(--bg-tertiary);
  padding: 1rem;
  text-align: left;
  font-weight: 600;
  border-bottom: 1px solid var(--border-color);
}

.resources-table td {
  padding: 1rem;
  border-bottom: 1px solid var(--border-color);
  vertical-align: top;
}

.resources-table tr:last-child td {
  border-bottom: none;
}

.resource-name {
  font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
  color: var(--accent);
  font-weight: 500;
}

.uri-template {
  font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
  font-size: 0.9rem;
  color: var(--text-secondary);
  background: var(--code-bg);
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
}

.guide-item {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  margin-bottom: 1rem;
  overflow: hidden;
}

.guide-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.5rem;
  cursor: pointer;
  background: var(--bg-secondary);
  transition: background 0.2s;
}

.guide-header:hover {
  background: var(--bg-tertiary);
}

.guide-title {
  font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
  color: var(--accent);
  font-weight: 500;
}

.guide-toggle {
  color: var(--text-muted);
  font-size: 1.25rem;
  transition: transform 0.2s;
}

.guide-item.open .guide-toggle {
  transform: rotate(180deg);
}

.guide-content {
  display: none;
  padding: 1.5rem;
  border-top: 1px solid var(--border-color);
  background: var(--bg-primary);
}

.guide-item.open .guide-content {
  display: block;
}

.guide-content h1 {
  font-size: 1.5rem;
  margin-bottom: 1rem;
  color: var(--text-primary);
}

.guide-content h2 {
  font-size: 1.25rem;
  margin: 1.5rem 0 1rem 0;
  padding-bottom: 0.25rem;
  border-bottom: 1px solid var(--border-color);
}

.guide-content h3 {
  font-size: 1.1rem;
  margin: 1.25rem 0 0.75rem 0;
}

.guide-content p {
  margin-bottom: 1rem;
  color: var(--text-secondary);
}

.guide-content ul, .guide-content ol {
  margin-bottom: 1rem;
  padding-left: 1.5rem;
  color: var(--text-secondary);
}

.guide-content li {
  margin-bottom: 0.5rem;
}

.guide-content code {
  background: var(--code-bg);
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
  font-size: 0.9rem;
}

.guide-content .code-block pre,
.guide-content pre {
  background: var(--code-bg);
  border: 1px solid var(--border-color);
  padding: 1rem;
  padding-right: 3rem;
  border-radius: 6px;
  overflow-x: auto;
  margin: 0;
  font-family: 'SF Mono', Monaco, 'Cascadia Code', Consolas, monospace;
  font-size: 0.85rem;
  line-height: 1.6;
  color: var(--text-primary);
}

.guide-content .code-block {
  margin-bottom: 1rem;
}

.guide-content pre code {
  background: none;
  padding: 0;
}

.guide-content table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 1rem;
}

.guide-content th, .guide-content td {
  padding: 0.75rem;
  border: 1px solid var(--border-color);
  text-align: left;
}

.guide-content th {
  background: var(--bg-tertiary);
  font-weight: 600;
}

.guide-content strong {
  color: var(--text-primary);
}

footer {
  background: var(--bg-secondary);
  border-top: 1px solid var(--border-color);
  padding: 2rem;
  text-align: center;
  color: var(--text-muted);
  margin-top: 2rem;
}

@media (max-width: 768px) {
  header {
    padding: 1.5rem 1rem;
  }

  header h1 {
    font-size: 1.75rem;
  }

  nav {
    padding: 0.75rem 1rem;
    gap: 1rem;
  }

  main {
    padding: 1rem;
  }

  .tools-table, .resources-table {
    display: block;
    overflow-x: auto;
  }

  .connection-box {
    padding: 1rem;
  }
}

@media (prefers-color-scheme: light) {
  :root {
    --bg-primary: #ffffff;
    --bg-secondary: #f6f8fa;
    --bg-tertiary: #eaeef2;
    --text-primary: #1f2328;
    --text-secondary: #656d76;
    --text-muted: #8c959f;
    --border-color: #d0d7de;
    --accent: #0969da;
    --accent-hover: #0550ae;
    --success: #1a7f37;
    --warning: #9a6700;
    --code-bg: #eaeff5;
  }
}

.setup-box {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  margin-bottom: 1.5rem;
  overflow: hidden;
}

.setup-box h3 {
  padding: 1rem 1.5rem;
  margin: 0;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.setup-box h3 .icon {
  font-size: 1.25rem;
}

.tabs {
  display: flex;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-tertiary);
}

.tab-btn {
  padding: 0.75rem 1.5rem;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 500;
  transition: all 0.2s;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
}

.tab-btn:hover {
  color: var(--text-primary);
  background: var(--bg-secondary);
}

.tab-btn.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
  background: var(--bg-secondary);
}

.tab-content {
  display: none;
  padding: 1.5rem;
}

.tab-content.active {
  display: block;
}

.tab-content p {
  color: var(--text-secondary);
  margin-bottom: 1rem;
}

.tab-content code {
  background: var(--code-bg);
  padding: 0.2rem 0.4rem;
  border-radius: 4px;
  font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
  font-size: 0.85rem;
}

.tab-content .note {
  font-size: 0.85rem;
  color: var(--text-muted);
  padding: 0.75rem 1rem;
  background: var(--bg-tertiary);
  border-radius: 6px;
  border-left: 3px solid var(--accent);
}

.code-block {
  position: relative;
  margin-bottom: 1rem;
}

.code-block pre {
  background: var(--code-bg);
  border: 1px solid var(--border-color);
  padding: 1rem;
  padding-right: 3rem;
  border-radius: 6px;
  overflow-x: auto;
  font-family: 'SF Mono', Monaco, 'Cascadia Code', Consolas, monospace;
  font-size: 0.85rem;
  line-height: 1.6;
  color: var(--text-primary);
  margin: 0;
}

.code-block pre .comment {
  color: var(--text-muted);
}

.code-block .copy-btn {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  padding: 0.25rem 0.5rem;
  cursor: pointer;
  font-size: 0.75rem;
  color: var(--text-secondary);
  transition: all 0.2s;
  opacity: 0;
}

.code-block:hover .copy-btn {
  opacity: 1;
}

.code-block .copy-btn:hover {
  background: var(--accent);
  color: white;
  border-color: var(--accent);
}

.code-block .copy-btn.copied {
  background: var(--success);
  color: white;
  border-color: var(--success);
}
"""

JS_SCRIPTS = """\
document.querySelectorAll('.guide-header').forEach(header => {
  header.addEventListener('click', () => {
    const item = header.parentElement;
    item.classList.toggle('open');
  });
});

document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const container = btn.closest('.setup-box');
    const mode = btn.dataset.mode;
    container.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    container.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    container.querySelector('.tab-content[data-mode=\"' + mode + '\"]').classList.add('active');
  });
});

// Wrap pre elements in code-block with copy button
document.querySelectorAll('.tab-content pre, .guide-content pre').forEach(pre => {
  if (pre.parentElement.classList.contains('code-block')) return;
  const wrapper = document.createElement('div');
  wrapper.className = 'code-block';
  pre.parentNode.insertBefore(wrapper, pre);
  wrapper.appendChild(pre);

  const copyBtn = document.createElement('button');
  copyBtn.className = 'copy-btn';
  copyBtn.textContent = 'Copy';
  copyBtn.addEventListener('click', async () => {
    const text = pre.textContent;
    try {
      await navigator.clipboard.writeText(text);
      copyBtn.textContent = 'Copied!';
      copyBtn.classList.add('copied');
      setTimeout(() => {
        copyBtn.textContent = 'Copy';
        copyBtn.classList.remove('copied');
      }, 2000);
    } catch (err) {
      copyBtn.textContent = 'Failed';
      setTimeout(() => { copyBtn.textContent = 'Copy'; }, 2000);
    }
  });
  wrapper.appendChild(copyBtn);
});
"""


def generate_docs_html(
    server_instructions: str,
    tools: list[Any],
    templates: list[Any],
    guides: Mapping[str, str],
    http_port: int = 8080,
) -> str:
    """Generate HTML documentation page.

    Args:
        server_instructions: The SERVER_INSTRUCTIONS from server.py
        tools: List of registered MCP tools
        templates: List of registered resource templates
        guides: Dict mapping section names to guide content
        http_port: The HTTP port the server is running on

    Returns:
        Complete HTML document as string
    """
    tools_html = _render_tools_section(tools)
    resources_html = _render_resources_section(templates)
    guides_html = _render_guides_section(guides)
    instructions_html = _render_instructions_section(server_instructions)

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Contree MCP Server</title>
  <style>
{CSS_STYLES}
  </style>
</head>
<body>
  <header>
    <h1>Contree MCP Server</h1>
    <p class="tagline">Container execution for AI agents</p>
  </header>

  <nav>
    <a href="#setup">Setup</a>
    <a href="#instructions">Instructions</a>
    <a href="#tools">Tools</a>
    <a href="#resources">Resources</a>
    <a href="#guides">Guides</a>
  </nav>

  <main>
    <section id="setup">
      <h2>Setup</h2>

      <div class="setup-box">
        <h3><span class="icon">🔑</span> Authentication (Required First)</h3>
        <div class="tab-content active" style="display: block;">
          <p>Create a config file to store your API token securely:</p>
<pre>mkdir -p ~/.config/contree</pre>
          <p>Add your credentials:</p>
<pre>cat &gt; ~/.config/contree/mcp.ini &lt;&lt; 'EOF'
[DEFAULT]
url = https://contree.dev/
token = your-token-here
EOF</pre>
          <p>Alternatively, use a custom config location:</p>
<pre>export CONTREE_MCP_CONFIG="/path/to/custom/config.ini"</pre>
          <p class="note">With token in config, MCP configs below don't need env vars.</p>
        </div>
      </div>

      <div class="setup-box">
        <h3><span class="icon">🖥️</span> Claude Code</h3>
        <div class="tabs">
          <button class="tab-btn active" data-mode="stdio">Stdio</button>
          <button class="tab-btn" data-mode="http">HTTP</button>
        </div>
        <div class="tab-content active" data-mode="stdio">
          <p>Using CLI:</p>
<pre>claude mcp add contree -- uvx contree-mcp</pre>
          <p>Or add to config file (<code>~/.claude.json</code> or <code>.mcp.json</code>):</p>
<pre>{{
  "mcpServers": {{
    "contree": {{
      "type": "stdio",
      "command": "uvx",
      "args": ["contree-mcp"]
    }}
  }}
}}</pre>
          <p>To use a custom config path, add <code>env</code>:</p>
<pre>{{
  "mcpServers": {{
    "contree": {{
      "type": "stdio",
      "command": "uvx",
      "args": ["contree-mcp"],
      "env": {{
        "CONTREE_MCP_CONFIG": "/path/to/config.ini"
      }}
    }}
  }}
}}</pre>
          <p class="note">Verify with <code>claude mcp list</code></p>
        </div>
        <div class="tab-content" data-mode="http">
          <p>Start the HTTP server:</p>
<pre>uvx contree-mcp --mode http --port {http_port}</pre>
          <p>Using CLI:</p>
<pre>claude mcp add contree --transport http http://localhost:{http_port}/mcp</pre>
          <p>Or add to config file:</p>
<pre>{{
  "mcpServers": {{
    "contree": {{
      "type": "http",
      "url": "http://localhost:{http_port}/mcp"
    }}
  }}
}}</pre>
        </div>
      </div>

      <div class="setup-box">
        <h3><span class="icon">⌨️</span> Codex CLI</h3>
        <div class="tabs">
          <button class="tab-btn active" data-mode="stdio">Stdio</button>
          <button class="tab-btn" data-mode="http">HTTP</button>
        </div>
        <div class="tab-content active" data-mode="stdio">
          <p>Using CLI:</p>
<pre>codex mcp add contree -- uvx contree-mcp</pre>
          <p>Or add to config file (<code>~/.codex/config.toml</code>):</p>
<pre>[mcp_servers.contree]
command = "uvx"
args = ["contree-mcp"]</pre>
          <p>To use a custom config path, add <code>env</code>:</p>
<pre>[mcp_servers.contree]
command = "uvx"
args = ["contree-mcp"]
env = {{ CONTREE_MCP_CONFIG = "/path/to/config.ini" }}</pre>
          <p class="note">Use <code>mcp_servers</code> (underscore).</p>
        </div>
        <div class="tab-content" data-mode="http">
          <p>Start the HTTP server:</p>
<pre>uvx contree-mcp --mode http --port {http_port}</pre>
          <p>Add to config file (<code>~/.codex/config.toml</code>):</p>
<pre>[mcp_servers.contree]
url = "http://localhost:{http_port}/mcp"</pre>
        </div>
      </div>

      <div class="setup-box">
        <h3><span class="icon">🔓</span> OpenCode</h3>
        <div class="tabs">
          <button class="tab-btn active" data-mode="stdio">Stdio</button>
          <button class="tab-btn" data-mode="http">HTTP</button>
        </div>
        <div class="tab-content active" data-mode="stdio">
          <p>Using CLI (interactive TUI wizard):</p>
<pre>opencode mcp add</pre>
          <p>Or add to config file (<code>~/.config/opencode/opencode.json</code>):</p>
<pre>{{
  "mcp": {{
    "contree": {{
      "type": "local",
      "command": ["uvx", "contree-mcp"],
      "enabled": true
    }}
  }}
}}</pre>
          <p>To use a custom config path, add <code>environment</code>:</p>
<pre>{{
  "mcp": {{
    "contree": {{
      "type": "local",
      "command": ["uvx", "contree-mcp"],
      "environment": {{
        "CONTREE_MCP_CONFIG": "/path/to/config.ini"
      }},
      "enabled": true
    }}
  }}
}}</pre>
          <p class="note">Verify with <code>opencode mcp list</code></p>
        </div>
        <div class="tab-content" data-mode="http">
          <p>Start the HTTP server:</p>
<pre>uvx contree-mcp --mode http --port {http_port}</pre>
          <p>Add to config file (<code>~/.config/opencode/opencode.json</code>):</p>
<pre>{{
  "mcp": {{
    "contree": {{
      "type": "remote",
      "url": "http://localhost:{http_port}/mcp",
      "enabled": true
    }}
  }}
}}</pre>
        </div>
      </div>

    </section>

{instructions_html}

{tools_html}

{resources_html}

{guides_html}
  </main>

  <footer>
    <p>Contree MCP Server &mdash; Container execution for AI agents</p>
  </footer>

  <script>
{JS_SCRIPTS}
  </script>
</body>
</html>
"""


def _render_instructions_section(instructions: str) -> str:
    """Render the server instructions section."""
    content_html = _markdown_to_html(instructions)
    return f"""\
    <section id="instructions">
      <h2>Server Instructions</h2>
      <div class="guide-content" style="display: block; background: var(--bg-secondary);
border: 1px solid var(--border-color); border-radius: 8px;">
        {content_html}
      </div>
    </section>
"""


def _render_tools_section(tools: list[Any]) -> str:
    """Render the tools reference section."""
    rows = []
    for tool in sorted(tools, key=lambda t: t.name):
        desc = _get_first_paragraph(tool.description or "")
        # Handle both mcp.types.Tool (inputSchema) and FastMCP Tool (parameters)
        schema = getattr(tool, "inputSchema", None) or getattr(tool, "parameters", {})
        params_html = _render_tool_params(schema)

        rows.append(f"""\
      <tr>
        <td><span class="tool-name">{html.escape(tool.name)}</span></td>
        <td>
          <div class="tool-desc">{html.escape(desc)}</div>
          {params_html}
        </td>
      </tr>""")

    return f"""\
    <section id="tools">
      <h2>Tools Reference</h2>
      <table class="tools-table">
        <thead>
          <tr>
            <th style="width: 200px;">Tool</th>
            <th>Description &amp; Parameters</th>
          </tr>
        </thead>
        <tbody>
{"".join(rows)}
        </tbody>
      </table>
    </section>
"""


def _render_tool_params(schema: dict[str, Any]) -> str:
    """Render tool input parameters from JSON schema."""
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    if not properties:
        return ""

    # Handle $defs for nested types
    defs = schema.get("$defs", {})

    params = []
    for name, prop in properties.items():
        param_type = _get_param_type(prop, defs)
        req_marker = '<span class="param-required">*</span>' if name in required else ""
        param_html = f'<span class="param-name">{html.escape(name)}</span>'
        params.append(f"{param_html}{req_marker}: {html.escape(param_type)}")

    return f'<div class="tool-params">{", ".join(params)}</div>'


def _get_param_type(prop: dict[str, Any], defs: dict[str, Any]) -> str:
    """Extract parameter type from JSON schema property."""
    # Handle anyOf (optional types)
    if "anyOf" in prop:
        types = []
        for option in prop["anyOf"]:
            if option.get("type") == "null":
                continue
            if "$ref" in option:
                ref_name = option["$ref"].split("/")[-1]
                types.append(ref_name)
            else:
                types.append(option.get("type", "any"))
        return " | ".join(types) if types else "any"

    # Handle $ref
    if "$ref" in prop:
        ref = prop["$ref"]
        return str(ref).split("/")[-1] if ref else "any"

    # Handle enum
    if "enum" in prop:
        return " | ".join(f'"{v}"' for v in prop["enum"])

    # Handle array
    if prop.get("type") == "array":
        items = prop.get("items", {})
        item_type = _get_param_type(items, defs)
        return f"array[{item_type}]"

    # Handle object
    if prop.get("type") == "object":
        return "object"

    # Basic type
    type_val = prop.get("type", "any")
    return str(type_val) if type_val else "any"


def _render_resources_section(templates: list[Any]) -> str:
    """Render the resources reference section."""
    rows = []
    for template in sorted(templates, key=lambda t: t.name):
        desc = _get_first_paragraph(template.description or "")
        # Handle both mcp.types.ResourceTemplate (uriTemplate) and FastMCP (uri_template)
        uri = getattr(template, "uriTemplate", None) or getattr(template, "uri_template", "") or ""
        rows.append(f"""\
      <tr>
        <td><span class="resource-name">{html.escape(template.name)}</span></td>
        <td><code class="uri-template">{html.escape(str(uri))}</code></td>
        <td>{html.escape(desc)}</td>
      </tr>""")

    return f"""\
    <section id="resources">
      <h2>Resources Reference</h2>
      <table class="resources-table">
        <thead>
          <tr>
            <th style="width: 150px;">Resource</th>
            <th style="width: 300px;">URI Template</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
{"".join(rows)}
        </tbody>
      </table>
    </section>
"""


def _render_guides_section(guides: Mapping[str, str]) -> str:
    """Render the guides section with collapsible items."""
    items = []
    for section_name in sorted(guides.keys()):
        content = guides[section_name]
        content_html = _markdown_to_html(content)

        items.append(f"""\
    <div class="guide-item">
      <div class="guide-header">
        <span class="guide-title">contree://guide/{html.escape(section_name)}</span>
        <span class="guide-toggle">&#9662;</span>
      </div>
      <div class="guide-content">
        {content_html}
      </div>
    </div>""")

    return f"""\
    <section id="guides">
      <h2>Guides</h2>
      {"".join(items)}
    </section>
"""


def _get_first_paragraph(text: str) -> str:
    """Extract first paragraph from text."""
    lines: list[str] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line and lines:
            break
        if line:
            lines.append(line)
    return " ".join(lines)


def _markdown_to_html(md: str) -> str:
    """Convert simple markdown to HTML.

    Handles: headers, code blocks, inline code, lists, tables, bold, paragraphs.
    """
    lines = md.split("\n")
    html_parts = []
    in_code_block = False
    code_block_lines: list[str] = []
    in_list = False
    list_type = ""
    in_table = False
    table_rows: list[str] = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Code blocks
        if line.startswith("```"):
            if in_code_block:
                code_content = html.escape("\n".join(code_block_lines))
                html_parts.append(f"<pre><code>{code_content}</code></pre>")
                code_block_lines = []
                in_code_block = False
            else:
                if in_list:
                    html_parts.append(f"</{list_type}>")
                    in_list = False
                in_code_block = True
            i += 1
            continue

        if in_code_block:
            code_block_lines.append(line)
            i += 1
            continue

        # Tables
        if "|" in line and line.strip().startswith("|"):
            if not in_table:
                if in_list:
                    html_parts.append(f"</{list_type}>")
                    in_list = False
                in_table = True
                table_rows = []
            table_rows.append(line)
            i += 1
            continue
        elif in_table:
            html_parts.append(_render_table(table_rows))
            in_table = False
            table_rows = []

        # Headers
        if line.startswith("#"):
            if in_list:
                html_parts.append(f"</{list_type}>")
                in_list = False
            level = len(line) - len(line.lstrip("#"))
            level = min(level, 6)
            text = line[level:].strip()
            text = _inline_markdown(text)
            html_parts.append(f"<h{level}>{text}</h{level}>")
            i += 1
            continue

        # Unordered lists
        if line.strip().startswith("- ") or line.strip().startswith("* "):
            if not in_list or list_type != "ul":
                if in_list:
                    html_parts.append(f"</{list_type}>")
                html_parts.append("<ul>")
                in_list = True
                list_type = "ul"
            text = line.strip()[2:]
            text = _inline_markdown(text)
            html_parts.append(f"<li>{text}</li>")
            i += 1
            continue

        # Ordered lists
        if line.strip() and line.strip()[0].isdigit() and ". " in line:
            if not in_list or list_type != "ol":
                if in_list:
                    html_parts.append(f"</{list_type}>")
                html_parts.append("<ol>")
                in_list = True
                list_type = "ol"
            text = line.strip().split(". ", 1)[1]
            text = _inline_markdown(text)
            html_parts.append(f"<li>{text}</li>")
            i += 1
            continue

        # End list if line doesn't continue it
        if in_list and line.strip() and not line.startswith(" "):
            html_parts.append(f"</{list_type}>")
            in_list = False

        # Empty lines
        if not line.strip():
            i += 1
            continue

        # Regular paragraph
        if in_list:
            html_parts.append(f"</{list_type}>")
            in_list = False
        text = _inline_markdown(line)
        html_parts.append(f"<p>{text}</p>")
        i += 1

    # Close any open elements
    if in_list:
        html_parts.append(f"</{list_type}>")
    if in_table:
        html_parts.append(_render_table(table_rows))
    if in_code_block:
        code_content = html.escape("\n".join(code_block_lines))
        html_parts.append(f"<pre><code>{code_content}</code></pre>")

    return "\n".join(html_parts)


def _inline_markdown(text: str) -> str:
    """Convert inline markdown (code, bold, links) to HTML."""
    import re

    # Escape HTML first
    text = html.escape(text)

    # Inline code (backticks)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)

    # Bold (**text**)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)

    return text


def _render_table(rows: list[str]) -> str:
    """Render a markdown table to HTML."""
    if len(rows) < 2:
        return ""

    def parse_row(row: str) -> list[str]:
        cells = row.strip().split("|")
        # Remove empty first/last from | delimiters
        if cells and not cells[0].strip():
            cells = cells[1:]
        if cells and not cells[-1].strip():
            cells = cells[:-1]
        return [c.strip() for c in cells]

    header_cells = parse_row(rows[0])

    # Skip separator row (|---|---|)
    data_rows = rows[2:] if len(rows) > 2 else []

    header_html = "".join(f"<th>{_inline_markdown(c)}</th>" for c in header_cells)
    body_html = ""
    for row in data_rows:
        cells = parse_row(row)
        body_html += "<tr>" + "".join(f"<td>{_inline_markdown(c)}</td>" for c in cells) + "</tr>"

    return f"<table><thead><tr>{header_html}</tr></thead><tbody>{body_html}</tbody></table>"

# Configuration file for the Sphinx documentation builder.

import datetime
import shutil
from pathlib import Path

import tomllib

# Read version from pyproject.toml
pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
with open(pyproject_path, "rb") as f:
    pyproject = tomllib.load(f)

project = "contree-mcp"
version = pyproject["project"]["version"]
release = version
author = "Nebius"
copyright = f"{datetime.datetime.now().year}, {author}"

# -- General configuration ---------------------------------------------------

extensions = [
    "myst_parser",
    "sphinx_design",
    "sphinx_copybutton",
    "sphinxcontrib.mermaid",
    "sphinx.ext.intersphinx",
]

# MyST configuration
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "fieldlist",
    "tasklist",
    "attrs_inline",
    "attrs_block",
]

myst_heading_anchors = 3

# Templates and exclusions
templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options for HTML output -------------------------------------------------

html_theme = "furo"
html_title = "ConTree MCP Server Documentation"
html_logo = "_static/logo.svg"
html_static_path = ["_static"]

html_theme_options = {
    "source_repository": "https://github.com/nebius/contree",
    "source_branch": "main",
    "source_directory": "contree/static/contree-mcp/docs/",
    "navigation_with_keys": True,
    "sidebar_hide_name": False,
    "light_css_variables": {
        "color-brand-primary": "#2962ff",
        "color-brand-content": "#2962ff",
    },
    "dark_css_variables": {
        "color-brand-primary": "#82b1ff",
        "color-brand-content": "#82b1ff",
    },
}

# Copy button settings
copybutton_prompt_text = r">>> |\.\.\. |\$ "
copybutton_prompt_is_regexp = True

# Mermaid settings
mermaid_version = "10.6.1"

# Intersphinx
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}


# -- Sphinx hooks ------------------------------------------------------------


def copy_llm_txt(app, exception):
    """Copy llm.txt to docs root after HTML build."""
    if exception is None and app.builder.name == "html":
        src = Path(__file__).parent / "llm.txt"
        dst = Path(app.outdir) / "llm.txt"
        if src.exists():
            shutil.copy2(src, dst)


def setup(app):
    app.connect("build-finished", copy_llm_txt)

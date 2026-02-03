"""
## MANDATORY WORKFLOW

Every task MUST follow this sequence:

### Step 1: CHECK for Prepared Environment
```
list_images(tag_prefix="common/")
```
Search for existing prepared images before creating new ones.

### Step 2: PREPARE Environment (if not found)
```
import_image(registry_url="docker://python:3.11-slim")
run(command="pip install ...", image="<uuid>", disposable=false)
set_tag(image_uuid="<result>", tag="common/python-ml/python:3.11-slim")
```
Build and TAG prepared images for reuse. CRITICAL: Use `disposable=false` to save state.

### Step 3: EXECUTE Task
```
run(command="...", image="tag:common/python-ml/python:3.11-slim")
```
Use tagged image for efficient execution.

---

## Tagging Convention

```
{scope}/{purpose}/{base}:{tag}
```

| Component | Description | Examples |
|-----------|-------------|----------|
| `{scope}` | `common` or project name | `common`, `myproject` |
| `{purpose}` | What was added/configured | `rust-toolchain`, `python-ml`, `web-deps` |
| `{base}:{tag}` | Original base image | `ubuntu:noble`, `python:3.11-slim` |

**Examples:**
- `common/rust-toolchain/ubuntu:noble` - Ubuntu with Rust
- `common/python-ml/python:3.11-slim` - Python with ML libraries
- `myproject/dev-env/python:3.11-slim` - Project-specific setup

---

## NEVER DO THESE

| Anti-pattern | Consequence | Correct approach |
|--------------|-------------|------------------|
| Import without checking | Wastes 10s-30min on duplicate imports | `list_images(tag_prefix="...")` first |
| Skip tagging prepared images | Rebuilds from scratch next time | `set_tag()` after installing deps |
| Chain commands in one run | Cannot rollback individual steps | One step per `run` |
| Use `disposable=true` for installs | Loses all installed packages | `disposable=false` for setup |

---

## Tool Cost Reference

| Tool | Cost | Notes |
|------|------|-------|
| `run` | VM (~2-5s) | Command execution |
| `import_image` | VM (~10-30s) | Image pull from registry |
| `rsync`, `upload`, `download` | Free | File transfer operations |
| `list_images`, `get_image`, `set_tag` | Free | Image metadata |
| `list_files`, `read_file` | Free | Inspect container filesystem |
| `get_operation`, `list_operations`, `wait_operations`, `cancel_operation` | Free | Async management |
| `get_guide` | Free | Access documentation |

**Cost Optimization:** Use `list_files`/`read_file` instead of `run("ls")`/`run("cat")`.

---

## Image Inspection (Free)

Inspect container filesystem without VM cost:

```
list_files(image="<uuid>", path="/etc")       # List directory contents
read_file(image="<uuid>", path="/etc/passwd") # Read file contents
```

Prefer these over `run("ls ...")`/`run("cat ...")` for simple inspection.

---

## Guides

Access documentation via resource URI or tool:

| Guide | Resource URI | Tool Alternative |
|-------|--------------|------------------|
| Workflow patterns | `contree://guide/workflow` | `get_guide(section="workflow")` |
| Async execution | `contree://guide/async` | `get_guide(section="async")` |
| Tagging convention | `contree://guide/tagging` | `get_guide(section="tagging")` |
| Tool reference | `contree://guide/reference` | `get_guide(section="reference")` |
| Error handling | `contree://guide/errors` | `get_guide(section="errors")` |

Use resources if supported by your agent runtime, otherwise use `get_guide()`.
"""

import re
from collections.abc import Awaitable, Callable
from textwrap import dedent
from typing import Any

from mcp.server import FastMCP
from mcp.server.fastmcp.prompts import Prompt
from mcp.server.fastmcp.resources import ResourceTemplate
from pydantic import AnyUrl

from contree_mcp import prompts

from . import resources, tools


class PathResourceTemplate(ResourceTemplate):
    """Resource template that supports path parameters with slashes.

    FastMCP's default ResourceTemplate uses [^/]+ for parameters, which doesn't
    match paths containing slashes. This subclass overrides the matches() method
    to use .+ for the last parameter named 'path', allowing paths like 'etc/passwd'.
    """

    def matches(self, uri: str) -> dict[str, Any] | None:
        """Check if URI matches template and extract parameters.

        Uses .+ for the last {path} parameter to capture paths with slashes.
        """
        # Build regex pattern, using .+ for the last {path} parameter
        pattern = self.uri_template

        # Find all parameter names
        param_names = re.findall(r"\{(\w+)\}", pattern)

        for i, param in enumerate(param_names):
            is_last = i == len(param_names) - 1
            is_path = param == "path"

            if is_last and is_path:
                # Last path parameter: match anything including slashes
                pattern = pattern.replace(f"{{{param}}}", f"(?P<{param}>.+)")
            else:
                # Regular parameter: don't match slashes
                pattern = pattern.replace(f"{{{param}}}", f"(?P<{param}>[^/]+)")

        match = re.match(f"^{pattern}$", uri)
        if match:
            return match.groupdict()
        return None


def register_resource_template(mcp: FastMCP, url: str, resource_template_func: Callable[..., Awaitable[Any]]) -> None:
    """
    Register a resource template with the MCP app.

    Uses PathResourceTemplate for URLs containing {path} to support
    paths with slashes (e.g., etc/passwd) without URL encoding.
    """
    description = dedent(resource_template_func.__doc__ or "") or ""

    # Use PathResourceTemplate for URLs with {path} parameter
    if "{path}" in url:
        template = PathResourceTemplate.from_function(
            resource_template_func,
            uri_template=url,
            description=description,
        )
        # Directly add to resource manager's templates dict
        mcp._resource_manager._templates[url] = template
    else:
        # Use standard FastMCP registration
        decorator = mcp.resource(url, description=description)
        decorator(resource_template_func)


def register_tool(mcp: FastMCP, tool_func: Callable[..., Awaitable[Any]], **kwargs: Any) -> None:
    mcp.add_tool(tool_func, description=dedent(tool_func.__doc__ or "") or "", **kwargs)


def create_mcp_app(**kwargs: Any) -> FastMCP:
    mcp = FastMCP(
        name="contree-mcp",
        instructions=dedent(__doc__).strip(),
        streamable_http_path="/mcp",
        json_response=True,
        **kwargs,
    )

    register_tool(mcp, tools.list_images)
    register_tool(mcp, tools.registry_token_obtain)
    register_tool(mcp, tools.registry_auth)
    register_tool(mcp, tools.import_image)
    register_tool(mcp, tools.get_image)
    register_tool(mcp, tools.set_tag)
    register_tool(mcp, tools.run)
    register_tool(mcp, tools.rsync)
    register_tool(mcp, tools.upload)
    register_tool(mcp, tools.download)
    register_tool(mcp, tools.get_operation)
    register_tool(mcp, tools.list_operations)
    register_tool(mcp, tools.wait_operations)
    register_tool(mcp, tools.cancel_operation)

    # some agents can not use resources, so we expose these as tools too
    register_tool(mcp, tools.list_files)
    register_tool(mcp, tools.read_file)
    register_tool(mcp, tools.get_guide)

    mcp.add_prompt(Prompt.from_function(prompts.prepare_environment, name="prepare-environment"))
    mcp.add_prompt(Prompt.from_function(prompts.run_python, name="run-python"))
    mcp.add_prompt(Prompt.from_function(prompts.run_shell, name="run-shell"))
    mcp.add_prompt(Prompt.from_function(prompts.sync_and_run, name="sync-and-run"))
    mcp.add_prompt(Prompt.from_function(prompts.install_packages, name="install-packages"))
    mcp.add_prompt(Prompt.from_function(prompts.parallel_tasks, name="parallel-tasks"))
    mcp.add_prompt(Prompt.from_function(prompts.build_project, name="build-project"))
    mcp.add_prompt(Prompt.from_function(prompts.debug_failure, name="debug-failure"))
    mcp.add_prompt(Prompt.from_function(prompts.inspect_image, name="inspect-image"))
    mcp.add_prompt(Prompt.from_function(prompts.multi_stage_build, name="multi-stage-build"))

    register_resource_template(mcp, "contree://image/{image}/read/{path}", resources.read_file)
    register_resource_template(mcp, "contree://image/{image}/ls/{path}", resources.image_ls)
    register_resource_template(mcp, "contree://image/{image}/lineage", resources.image_lineage)
    register_resource_template(mcp, "contree://operations/instance/{operation_id}", resources.instance_operation)
    register_resource_template(mcp, "contree://operations/import/{operation_id}", resources.import_operation)

    # Register guide sections as static resources for discovery
    for section, content in resources.SECTIONS.items():
        mcp.add_resource(
            resources.StaticResource(
                content,
                uri=AnyUrl(f"contree://guide/{section}"),
                name=section,
                title=f"Contree Guide: {section.replace('-', ' ').title()}",
                description=f"Guide section on {section.replace('-', ' ')}",
                mime_type="text/markdown",
            )
        )

    return mcp

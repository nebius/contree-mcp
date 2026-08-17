"""# Contree MCP

Contree MCP exposes sandboxed code execution as a set of stateless tool
calls. Every `run` spawns an isolated microVM; every non-disposable
`run` produces a new immutable image UUID. There are no sessions —
image lineage is the durable state, tracked through `result_image`
UUIDs and `set_tag`.

**FIRST OF ALL READ THE GUIDES.** When anything below is unclear, or
before retrying after a failure, fetch the relevant section:

    get_guide(section="workflow" | "reference" | "quickstart" |
                       "state" | "async" | "tagging" | "errors")

or read the matching resource URI: `contree://guide/<section>`.

## Quick start

1. Search before you build. Always check the existing pool first:
       list_images(tag_prefix="common/")
   Do NOT assume `tag:python:3.11` exists — pick from the actual list.
2. Inspect (free, no VM):
       list_files(image="<uuid-or-tag>", path="/etc")
       read_file(image="<uuid-or-tag>", path="/etc/os-release")
3. Stage local files when needed:
       rsync(source="/path/to/project", destination="/app")  -> directory_state_id
       upload(path="/path/to/file")                          -> file uuid
4. Execute in small steps, one mutating step per `run`. Pass
   `disposable=false` to keep the result image:
       run(command="apt-get install -y curl",
           image="<uuid>", disposable=false)
5. Tag useful results immediately:
       set_tag(image_uuid="<result>",
               tag="common/python-ml/python:3.11-slim")

## Non-negotiable rules

- Always search before you build. `list_images(tag_prefix=...)` is free.
- One mutating step per `run`. Each `run(disposable=false)` is one
  history entry; chained `&&` lines collapse into one and you lose
  granular rollback.
- `disposable=true` is the default (it discards changes). Use it for
  read-only checks and exit-code probes; switch to `disposable=false`
  the moment you want to keep the result. (CLI users: this is the
  opposite of `contree run`'s default.)
- Prefer `list_files` / `read_file` / `grep` over `run("ls ...")` /
  `run("cat ...")` / `run("grep ...")` — they're free and avoid spawning a microVM.
- Local files are NOT visible in the sandbox unless attached via
  `rsync` (directory) or `upload` (single file).
- Tag images you intend to reuse. Untagged images are only reachable
  by UUID and easily lost.
- For env vars that must outlive the run (PATH after rustup / nvm /
  pyenv), set `preserve_env=true` on the `run` that installs them.

## Command map

| Tool | Purpose |
|------|---------|
| `run` | Execute a command in an isolated microVM |
| `import_image` | Pull an OCI image from a registry |
| `list_images` | List images; filter by `tag_prefix` |
| `get_image` | Read image metadata |
| `set_tag` | Add or remove a tag |
| `rsync` | Stage a local directory tree |
| `upload` | Stage a single local file |
| `download` | Pull a file out of an image |
| `list_files` / `read_file` / `grep` | Inspect an image without a VM |
| `get_operation` / `list_operations` / `wait_operations` / `cancel_operation` | Async operation management |
| `whoami` | Token introspection (permissions, limits) |
| `registry_token_obtain` / `registry_auth` | One-time private-registry setup |
| `get_guide` | Read a section of this guide |

## State and lineage

There are no sessions. Image UUIDs are the durable state:

- Each `run(disposable=false)` returns a new `result_image` UUID. Feed
  it to the next `run` as `image` to chain.
- "Rollback" = reuse a prior UUID. Old UUIDs are immutable.
- "Branch" = feed an earlier UUID into a new `run` with different inputs.
- Untagged UUIDs are eligible for project-scoped garbage collection.
  Tag what you want to keep.

Full details: `contree://guide/state`.

## Detached operations

Launch long work with `wait=false`:

    run(command="...", image="...", wait=false)
    # -> {"operation_id": "op-1"}

    wait_operations(operation_ids=["op-1", "op-2"], mode="all" | "any")

`mode="any"` returns on the first completion — useful for racing
multiple approaches. Operation states are `PENDING`, `ASSIGNED`,
`EXECUTING`, `SUCCESS`, `FAILED`, `CANCELLED` (uppercase, matching
the API enum). Full details: `contree://guide/async`.

## Server upgrades

`whoami` surfaces an `mcp_upgrade` field whenever this process is
behind the latest published `contree-mcp` release on PyPI:

    {
      "mcp_version": "0.1.1",
      "mcp_upgrade": {
        "current": "0.1.1",
        "latest": "0.1.5",
        "command": "uv tool install -U contree-mcp  # or: pip install -U contree-mcp"
      }
    }

When you see a non-null `mcp_upgrade`, tell the user the server is
running an outdated build and quote `mcp_upgrade.command` verbatim.
The check runs once at startup (a cached PyPI probe; opt out with
`CONTREE_NO_UPDATE_CHECK=1`), so the field is stable for the lifetime
of the process — there's no need to call `whoami` repeatedly.

## Built-in guide

When something fails or you're unsure, consult the relevant section
instead of guessing:

| URI | Tool | When to read |
|-----|------|--------------|
| `contree://guide/workflow` | `get_guide("workflow")` | Bootstrap protocol and anti-patterns |
| `contree://guide/quickstart` | `get_guide("quickstart")` | Common patterns by example |
| `contree://guide/reference` | `get_guide("reference")` | Per-tool parameters and image refs |
| `contree://guide/state` | `get_guide("state")` | UUID lineage, "rollback" without sessions |
| `contree://guide/async` | `get_guide("async")` | Parallel runs, fan-out / join |
| `contree://guide/tagging` | `get_guide("tagging")` | Tag naming convention |
| `contree://guide/errors` | `get_guide("errors")` | Failure modes and debugging |
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
    register_tool(mcp, tools.whoami)

    # some agents can not use resources, so we expose these as tools too
    register_tool(mcp, tools.list_files)
    register_tool(mcp, tools.read_file)
    register_tool(mcp, tools.grep)
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

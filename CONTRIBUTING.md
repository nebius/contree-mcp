# Contributing to ConTree MCP

Thanks for considering a contribution! This guide covers the practical bits — opening issues, setting up a dev environment, and getting a PR merged.

## Reporting issues

**Bugs.** Open a [bug report](https://github.com/nebius/contree-mcp/issues/new?template=bug_report.yml). Include `contree-mcp --version`, your Python version, OS, MCP client, a minimal reproducer, and any logs (`--log-level=debug` is helpful).

**Features.** For anything beyond a small fix, please [open a feature request](https://github.com/nebius/contree-mcp/issues/new?template=feature_request.yml) **before** writing code. We may have a different shape in mind, or be working on something related.

**Documentation gaps.** [Open a docs issue](https://github.com/nebius/contree-mcp/issues/new?template=documentation.yml) — small fixes can be PR'd directly.

**Security.** Use [GitHub Security Advisories](https://github.com/nebius/contree-mcp/security/advisories/new) — do not file a public issue.

## Development setup

Requirements: Python 3.10+ and [`uv`](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/nebius/contree-mcp.git
cd contree-mcp
make install          # uv sync --group dev
```

## Workflow

```bash
make check            # lint + typecheck + tests (run before pushing)
make test             # tests only
make format           # auto-fix formatting + lint
make help             # full target list
```

When making changes:

1. Fork and create a branch — descriptive name, no convention enforced (`fix/...`, `feat/...`, `docs/...`, or anything readable).
2. Edit code in `contree_mcp/` and tests in `tests/`.
3. Run `make check` — must pass before opening a PR. CI runs the same matrix on Ubuntu/macOS/Windows × Python 3.10–3.14.
4. Update `README.md` if user-facing behavior changes; update `llm.txt` if internals change in ways agents need to know.
5. Open a PR against `master`. Link the related issue if any.

## Pull request expectations

- Keep PRs focused — one logical change per PR.
- Include tests for new behavior; use `contree_client.testing.ContreeAsyncClient` to mock the SDK boundary. Reserve
  raw HTTP fakes for transport behavior that the SDK test double cannot represent.
- Update docs in the same PR as the code change.
- The CI suite (`tests.yml`) must pass.
- The PR template (auto-applied) lists the merge checklist.

Commit messages: short imperative subject (≤72 chars), optional body explaining the *why*. Match the existing style in `git log`.

## Architecture pointers

- `contree_mcp/app.py` — registers tools, prompts, resources with FastMCP
- `contree_mcp/tools/` — one file per MCP tool
- `contree_mcp/tools/mcp_types.py` — stable MCP-facing Pydantic DTOs
- `contree_mcp/client.py` — MCP adapter around the official `contree-client` SDK
- `contree_mcp/resources/` — MCP resource handlers (image inspection, guides)
- `tests/conftest.py` — shared SDK test-client, MCP adapter, and cache fixtures
- `llm.txt` — agent-readable internals reference

## Code style

- `ruff` for lint and format (config in `pyproject.toml`)
- `mypy --strict` for type checking
- Line length: 119

## Release process

Releases are managed by the Nebius team. Contributors don't need to bump versions in PRs.

## License

By contributing, you agree your contributions are licensed under [Apache 2.0](LICENSE).

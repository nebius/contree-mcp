"""
# Contree MCP — Tool Reference

| Tool | Action | Key params | Returns | Cost |
|------|--------|-----------|---------|------|
| `run` | Execute command in container | `command`, `image`, `disposable`, `wait` | stdout, exit_code, result_image | VM |
| `import_image` | Import OCI image from registry | `registry_url`, `tag`, `wait` | result_image | VM |
| `list_images` | List available images | `tag_prefix`, `tagged` | images[] | Free |
| `get_image` | Image metadata by UUID or tag | `image` | uuid, tag, created_at, operation_uuid | Free |
| `set_tag` | Add / remove tag | `image_uuid`, `tag` | Image | Free |
| `rsync` | Stage a local directory | `source`, `destination`, `exclude` | directory_state_id | Free |
| `upload` | Stage a single local file | `content` / `content_base64` / `path` | uuid | Free |
| `download` | Pull a file out of an image | `image`, `path`, `destination` | local file | Free |
| `list_files` | List files in an image (no VM) | `image`, `path` | entries[] | Free |
| `read_file` | Read a file from an image | `image`, `path` | bytes / text | Free |
| `grep` | Search file contents via ripgrep (no VM) | `image`, `pattern`, `path`, `glob` | matches[] | Free |
| `get_operation` | Poll a single operation | `operation_id` | operation | Free |
| `list_operations` | List operations | `status`, `kind`, `since`, `until` | operations[] | Free |
| `wait_operations` | Wait for several operations | `operation_ids`, `mode` | results | Free |
| `cancel_operation` | Cancel one operation | `operation_id` | status | Free |
| `whoami` | Token introspection | — | token_uuid, permissions, limits | Free |
| `registry_token_obtain` | Get PAT URL for a registry | `registry_url` | url | Free |
| `registry_auth` | Validate + store registry creds | `registry_url`, `username`, `token` | ok | Free |
| `get_guide` | Read a section of this guide | `section` | markdown | Free |

## Image references

Both UUID and tag forms are accepted by every tool that takes an
`image` parameter:

- UUID: `abc-123-def-456` (direct, immutable).
- Tag: `tag:python:3.11` (resolved server-side each call).

Prefer UUIDs when chaining a sequence of `run` calls — pass the
`result_image` from the previous step. Use tags for shared base
images and for human-readable references.

## run

Execute a command in an isolated microVM.

Required:
  - `command`: shell expression when `shell=true` (default), or an
    absolute / relative path to an executable when `shell=false`.
  - `image`: source image UUID or `tag:<name>`.

Key options:
  - `disposable`: `true` (default) discards changes; `false` saves
    a new `result_image`. **CLI default is the opposite.**
  - `wait`: `true` (default) blocks for the result; `false` returns
    `operation_id` and runs in the background.
  - `cwd`: working directory; `""` (default) uses the image's
    default, otherwise an absolute path. The CLI's `contree cd`
    has no MCP analogue — pass `cwd` on every `run` that needs it.
  - `env`: `{"K": "v"}` — env vars for this run only. Set a value
    to `null` to remove a previously-preserved variable.
  - `preserve_env`: bake `env` into the resulting image. Use
    after installing tools that need PATH adjustments
    (rustup / nvm / pyenv) or for any vars that should outlive
    the run.
  - `uid` / `gid`: run as a specific user (default `0/0` = root).
  - `timeout`: seconds (default `30`, server max `600`).
  - `max_layer_bytes`: cap on writable-layer size (default 12 GiB).
  - `truncate_output_at`: stdout/stderr cap (default `8000`).
  - `directory_state_id`: stage files from a prior `rsync`.
  - `files`: `{"/abs/path": "<file-uuid>"}` from `upload`.
  - `stdin`: forwarded to the process verbatim.

## rsync

Stage a local directory tree for the next `run`. Free (no VM).
  - `source`: absolute path or glob (`/path/dir`, `/path/**/*.py`).
  - `destination`: absolute path inside the sandbox.
  - `exclude`: list of patterns layered on top of the built-in
    excludes (`.git`, `__pycache__`, `node_modules`, `dist`,
    `build`, `.venv`, `.mypy_cache`, `.pytest_cache`, `*.pyc`).

Returns `directory_state_id` — pass it to the next `run`.

## upload

Stage a single file. Three input modes, exactly one required:
  - `content`: raw text.
  - `content_base64`: base64-encoded bytes.
  - `path`: a local filesystem path the server reads.

Returns `{"uuid": "..."}`. Inject it into a `run` via the `files`
map: `{"/etc/some-config": "<uuid>"}`. One UUID can land at
multiple destination paths.

## import_image

Pull an OCI image from a registry. Async (returns
`operation_id` when `wait=false`).
  - `registry_url`: `docker://docker.io/python:3.11-slim` /
    `docker://ghcr.io/org/image:tag`.
  - `tag`: optional human-readable tag; if omitted the image is
    addressable only by UUID.
  - `wait`: `true` blocks until imported.

For private registries, run `registry_token_obtain` followed by
`registry_auth` once per registry.

## list_files / read_file / grep

Inspect images without spawning a VM:
  - `list_files(image, path)` → entries with `path`, `size`,
    `mode`, `is_dir`, `is_symlink`, ...
  - `read_file(image, path)` → file bytes (text-decoded when
    possible).
  - `grep(image, pattern, path, glob, case)` → matching lines via
    ripgrep, with `path`, `line_number`, `line_text` per match.
    `pattern` is a regex (Rust syntax), not a plain substring.

Prefer these over `run("ls ...")` / `run("cat ...")` / `run("grep ...")`.

## whoami

Introspect the current API token. Returns:
  - `token_uuid`, `token_expiration` (epoch seconds or `null`).
  - `permissions`: `{"import": true, "spawn": true, ...}`.
  - `limits`: `{"instance_max_timeout": 3600, ...}`.

Call it when a tool fails with a permission error, or before
fanning out a large batch.

## Resources

URI template: `contree://guide/{section}`. Sections: `workflow`,
`reference`, `quickstart`, `state`, `async`, `tagging`, `errors`.
"""

"""
# Contree MCP — Core Workflow

Stateless: each tool call is independent. Image lineage is the only
durable state, tracked through `result_image` UUIDs (with
`disposable=false`) and `set_tag`.

## Agent protocol

Follow this sequence for every task:

1. Pick an image. Always search the existing pool first:
     list_images(tag_prefix="common/")
   Do NOT assume `tag:python:3.11` exists — pick from the actual list.

2. Inspect first (no VM, free):
     list_files(image="<uuid-or-tag>", path="/etc")
     read_file(image="<uuid-or-tag>", path="/etc/os-release")
     grep(image="<uuid-or-tag>", pattern="PermitRootLogin", path="/etc")

3. Stage local files when needed:
     rsync(source="/path/to/project", destination="/app") -> directory_state_id
     upload(path="/path/to/file") -> file uuid

4. Execute in small steps — one mutating step per `run`. Pass
   `disposable=false` to keep the result image:
     run(command="apt-get update", image="<uuid>", disposable=false)
     run(command="apt-get install -y curl", image="<result_image>",
         disposable=false)
     run(command="make -C /app test", image="<result_image>",
         directory_state_id="<id>")

5. Tag useful results immediately:
     set_tag(image_uuid="<result_image>",
             tag="common/python-ml/python:3.11-slim")

6. Branch by feeding a prior `result_image` UUID to a new `run`.
   Old UUIDs are immutable — they always represent the same state.

## Worked example — Python ML environment

Same shape as `contree-cli`'s "build and tag a Python environment"
example, expressed as MCP tool calls.

Step 1. Look for a prepared image:
    list_images(tag_prefix="common/python-ml")
If found, skip to step 4.

Step 2. Import a base image:
    import_image(registry_url="docker://docker.io/python:3.11-slim")
    -> result_image: "uuid-base"

Step 3. Install + tag in non-disposable runs:
    run(command="pip install numpy pandas scikit-learn",
        image="uuid-base", disposable=false)
    -> result_image: "uuid-with-deps"

    set_tag(image_uuid="uuid-with-deps",
            tag="common/python-ml/python:3.11-slim")

Step 4. Use it:
    rsync(source="/path/to/project", destination="/app")
    run(command="python /app/train.py",
        image="tag:common/python-ml/python:3.11-slim",
        directory_state_id="<id>")

## Non-negotiable rules

- Search before you build. `list_images(tag_prefix=...)` is free.
- One mutating step per `run`. Each `run(disposable=false)` is a
  history entry; chained `&&` lines collapse into one and you lose
  granular rollback.
    Wrong: run(command="apt update && apt install -y curl && make test")
    Right: three separate `run` calls, each with `disposable=false`.
- `disposable=true` (the default) discards changes. Use it for
  read-only checks, exit-code probes, and exploration. Switch to
  `disposable=false` the moment you want to keep the result.
  (Heads-up for CLI users: this is the opposite of `contree run`'s
  default.)
- Prefer `list_files` / `read_file` / `grep` over `run("ls ...")` /
  `run("cat ...")` / `run("grep ...")` — they're free and avoid spawning a microVM.
- Inject files explicitly. Local files are NOT visible inside the
  sandbox unless attached via `rsync` (directory) or `upload`
  (single file).
- Prefer absolute paths for `cwd` and file destinations.
- Tag images you intend to reuse. Untagged images are only
  reachable by UUID and easily lost.
- `env` defaults to no inheritance. To preserve env vars into the
  next image (e.g. PATH after `curl rustup`), set
  `preserve_env=true` on the `run` that installed them.

## Anti-patterns

Importing without checking:
    Wrong: import_image(registry_url="docker://python:3.11-slim")
           # every time, wastes 10-30s
    Right: list_images(tag_prefix="python") first; import only if
           nothing matches.

Not tagging after a non-disposable run:
    Wrong: run(command="pip install ...", disposable=false)
           # uuid is now unreachable without remembering it
    Right: set_tag(image_uuid=result_image, tag="common/...")

Long chained shell expression:
    Wrong: run(command="apt update && apt install -y curl && make test",
               disposable=false)
    Right: three runs, three history entries, three rollback points.

## Cross-references

- State model + lineage: contree://guide/state
- Async / parallel runs: contree://guide/async
- Tag convention: contree://guide/tagging
- Error recovery: contree://guide/errors
"""

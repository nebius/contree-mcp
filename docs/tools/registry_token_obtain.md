# registry_token_obtain

Open browser to create a Personal Access Token for a container registry.

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `registry_url` | string | required | Registry URL (e.g., `docker://ghcr.io/org/image`) |

## Known Registries

| Registry | PAT Page |
|----------|----------|
| docker.io | Docker Hub PAT settings |
| ghcr.io | GitHub fine-grained tokens |
| registry.gitlab.com | GitLab PAT settings |
| gcr.io | Google Cloud credentials |

## Examples

**Docker Hub:**
```json
{"registry_url": "docker://docker.io/library/alpine"}
```

**GitHub Container Registry:**
```json
{"registry_url": "docker://ghcr.io/org/image"}
```

**Bare image name (defaults to docker.io):**
```json
{"registry_url": "alpine"}
```

## Response

**Success:**
```json
{
  "status": "success",
  "registry": "docker.io",
  "url": "https://app.docker.com/settings/personal-access-tokens",
  "message": "Browser opened to ... Create a read-only PAT, then provide your username and token.",
  "agent_instruction": "STOP HERE. Wait for user to create PAT and provide the token."
}
```

**Unknown registry:**
```json
{
  "status": "error",
  "registry": "unknown.example.com",
  "message": "Unknown registry 'unknown.example.com'. Please consult the registry documentation for token creation."
}
```

## Workflow

1. Call `registry_token_obtain` → opens browser
2. User creates read-only PAT in registry web UI
3. User provides username and token
4. Call `registry_auth` to validate and store credentials
5. Call `import_image` to import images

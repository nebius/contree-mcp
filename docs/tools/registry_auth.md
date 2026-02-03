# registry_auth

Authenticate with a container registry via Personal Access Token.

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `registry_url` | string | required | Registry URL (e.g., `docker://ghcr.io/org/image`) |
| `username` | string | required | Registry username |
| `token` | string | required | Personal Access Token |

## URL Parsing

| Input | Registry |
|-------|----------|
| `docker://ghcr.io/org/image` | ghcr.io |
| `oci://registry.gitlab.com/org/image` | registry.gitlab.com |
| `alpine` or `library/alpine` | docker.io (implicit) |

## Examples

**Docker Hub:**
```json
{"registry_url": "docker://docker.io/library/alpine", "username": "myuser", "token": "dckr_pat_xxx"}
```

**GitHub Container Registry:**
```json
{"registry_url": "docker://ghcr.io/org/image", "username": "myuser", "token": "ghp_xxx"}
```

## Response

**Success:**
```json
{
  "status": "success",
  "registry": "docker.io",
  "message": "Authenticated with 'docker.io' as 'myuser' successfully."
}
```

**Invalid credentials:**
```json
{
  "status": "error",
  "registry": "docker.io",
  "message": "Invalid credentials for 'docker.io'. Please verify your username and PAT."
}
```

## Token Storage

- Credentials are validated via OCI /v2/ API before storage
- Stored in local cache and persisted across sessions
- Tokens are revalidated before each `import_image` call
- Expired tokens are automatically removed from cache

## Workflow

1. Call `registry_token_obtain` → opens browser
2. User creates read-only PAT in registry web UI
3. User provides username and token
4. Call `registry_auth` → validates and stores credentials
5. Call `import_image` to import images

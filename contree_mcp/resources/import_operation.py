from contree_mcp.backend_types import ImportImageMetadata, OperationKind
from contree_mcp.context import CLIENT


async def import_operation(operation_id: str) -> str:
    """
    Read image import operation details. Free (no VM).

    Return text in format:
    ```
    STATE: SUCCESS
    RESULT_IMAGE: <uuid>
    RESULT_TAG: latest
    REGISTRY_URL: registry.example.com/repo/image:tag
    ERROR:
    multiline error message if any
    ```

    Strings might absent in case it's not applicable.

    URI: contree://operations/import/{operation_id}

    Example: contree://operations/import/op-abc-123-def
    Returns:
    ```
    STATE: SUCCESS
    RESULT_IMAGE: 550e8400-e29b-41d4-a716-446655440000
    RESULT_TAG: latest
    REGISTRY_URL: registry.example.com/repo/image:tag
    """
    client = CLIENT.get()
    op = await client.get_operation(operation_id)
    if op.kind != OperationKind.IMAGE_IMPORT:
        raise ValueError(f"Operation {operation_id} is not an import operation (kind={op.kind})")

    result = f"STATE: {op.status.value}"

    if op.result and op.result.image:
        result += f"\nRESULT_IMAGE: {op.result.image}"
    if op.result and op.result.tag:
        result += f"\nRESULT_TAG: {op.result.tag}"

    # Extract registry URL from metadata
    if isinstance(op.metadata, ImportImageMetadata):
        registry_url = str(op.metadata.registry.url) if op.metadata.registry else None
        if registry_url:
            result += f"\nREGISTRY_URL: {registry_url}"

    if op.error:
        result += f"\nERROR:\n{op.error}"

    return result

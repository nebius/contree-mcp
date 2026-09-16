from types import EllipsisType

from contree_client.models import ImageImportMetadata

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
    op = await client.get_operation_status(operation_id)
    if op.kind != "image_import":
        raise ValueError(f"Operation {operation_id} is not an import operation (kind={op.kind})")

    result = f"STATE: {op.status}"

    op_result = op.result
    if not isinstance(op_result, EllipsisType) and op_result is not None:
        if op_result.image:
            result += f"\nRESULT_IMAGE: {op_result.image}"
        if op_result.tag:
            result += f"\nRESULT_TAG: {op_result.tag}"

    # Extract registry URL from metadata
    if isinstance(op.metadata, ImageImportMetadata):
        registry = op.metadata.registry
        registry_url = registry.url if not isinstance(registry, EllipsisType) else None
        if registry_url:
            result += f"\nREGISTRY_URL: {registry_url}"

    if op.error:
        result += f"\nERROR:\n{op.error}"

    return result

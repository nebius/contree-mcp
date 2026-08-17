"""Image lineage tracking for the ``contree://image/{image}/lineage`` resource.

The Contree backend has no concept of parent/child images — contree-mcp
records it locally so agents can answer "where did this image come
from" without keeping their own state. There is no background watcher;
:func:`record_lineage` is called opportunistically by any tool that
observes a terminal :class:`OperationResponse` (``run``, ``import_image``,
``wait_operations``, ``get_operation``). Writes are idempotent (keyed by
the resulting image UUID), so recording the same operation more than
once is harmless.
"""

from __future__ import annotations

from types import EllipsisType

from contree_client.models import ImageImportMetadata, OperationInstanceMetadata, OperationResponse

from .cache import Cache


async def record_lineage(cache: Cache, op: OperationResponse) -> None:
    op_result = op.result
    if op.status != "SUCCESS" or op_result is None or isinstance(op_result, EllipsisType):
        return
    result_image = op_result.image
    if not isinstance(result_image, str) or not result_image:
        return
    operation_id = op.uuid if isinstance(op.uuid, str) else ""

    if isinstance(op.metadata, OperationInstanceMetadata):
        input_image = op.metadata.image
        if not input_image or input_image == result_image:
            return
        parent_entry = await cache.get("image", input_image)
        await cache.put(
            kind="image",
            key=result_image,
            data={
                "parent_image": input_image,
                "operation_id": operation_id,
                "command": op.metadata.command,
            },
            parent_id=parent_entry.id if parent_entry else None,
        )
    elif isinstance(op.metadata, ImageImportMetadata):
        registry = op.metadata.registry
        registry_url = registry.url if not isinstance(registry, EllipsisType) else None
        result_tag = op_result.tag
        await cache.put(
            kind="image",
            key=result_image,
            data={
                "operation_id": operation_id,
                "registry_url": registry_url if isinstance(registry_url, str) else None,
                "tag": result_tag if isinstance(result_tag, str) else None,
                "is_import": True,
            },
            parent_id=None,
        )

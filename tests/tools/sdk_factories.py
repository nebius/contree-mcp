"""Factories for SDK models returned to MCP tool tests."""

from contree_client.models import (
    ImageImportMetadata,
    ImageImportMetadataRegistry,
    InstanceResult,
    InstanceResultResources,
    InstanceResultState,
    OperationInstanceMetadata,
    OperationResponse,
    OperationResult,
    OperationStatus,
    StreamRepr,
)


def instance_operation(
    *,
    uuid: str,
    status: OperationStatus = OperationStatus.SUCCESS,
    command: str = "echo test",
    image: str = "img-1",
    stdout: str = "",
    stderr: str = "",
    exit_code: int = 0,
    timed_out: bool = False,
    elapsed_time: float = 0.0,
    result_image: str | None = None,
    error: str | None = None,
) -> OperationResponse:
    """Create an SDK instance-operation response."""
    return OperationResponse(
        uuid=uuid,
        kind="instance",
        status=status,
        error=error,
        created_at="2024-01-01T00:00:00Z",
        metadata=OperationInstanceMetadata(
            command=command,
            image=image,
            result=InstanceResult(
                state=InstanceResultState(
                    exit_code=exit_code,
                    pid=1,
                    timed_out=timed_out,
                ),
                stdout=StreamRepr(value=stdout, encoding="ascii"),
                stderr=StreamRepr(value=stderr, encoding="ascii"),
                resources=InstanceResultResources(elapsed_time=elapsed_time),
            ),
        ),
        result=OperationResult(image=result_image, tag=None),
    )


def import_operation(
    *,
    uuid: str,
    status: OperationStatus = OperationStatus.SUCCESS,
    registry_url: str = "docker.io/library/python:3.11-slim",
    tag: str | None = None,
    result_image: str | None = None,
    error: str | None = None,
    include_result: bool = True,
) -> OperationResponse:
    """Create an SDK image-import operation response."""
    result = OperationResult(image=result_image, tag=tag) if include_result else ...
    return OperationResponse(
        uuid=uuid,
        kind="image_import",
        status=status,
        error=error,
        created_at="2024-01-01T00:00:00Z",
        metadata=ImageImportMetadata(
            registry=ImageImportMetadataRegistry(url=registry_url),
            tag=tag,
            timeout=300,
        ),
        result=result,
    )

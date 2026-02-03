"""Tests for contree_mcp.types module."""

import base64

from contree_mcp.backend_types import (
    ConsumedResources,
    ImageRegistry,
    ImportImageMetadata,
    InstanceMetadata,
    InstanceResult,
    OperationKind,
    OperationResponse,
    OperationResult,
    OperationStatus,
    ProcessExitState,
    Stream,
)


class TestOperationResponse:
    """Tests for OperationResponse model."""

    def test_instance_operation(self) -> None:
        """Test creating an instance operation response."""
        response = OperationResponse(
            uuid="op-1",
            kind=OperationKind.INSTANCE,
            status=OperationStatus.SUCCESS,
            metadata=InstanceMetadata(
                command="echo hello",
                image="img-1",
                result=InstanceResult(
                    state=ProcessExitState(exit_code=0, pid=1, timed_out=False),
                    stdout=Stream(value="hello world", encoding="ascii"),
                    stderr=Stream(value="", encoding="ascii"),
                    resources=ConsumedResources(elapsed_time=1.0),
                ),
            ),
            result=OperationResult(image="img-result", tag=None),
        )

        assert response.uuid == "op-1"
        assert response.kind == OperationKind.INSTANCE
        assert response.status == OperationStatus.SUCCESS
        assert isinstance(response.metadata, InstanceMetadata)
        assert response.metadata.result.stdout.text() == "hello world"
        assert response.result is not None
        assert response.result.image == "img-result"

    def test_image_import_operation(self) -> None:
        """Test creating an image import operation response."""
        response = OperationResponse(
            uuid="op-2",
            kind=OperationKind.IMAGE_IMPORT,
            status=OperationStatus.SUCCESS,
            metadata=ImportImageMetadata(
                registry=ImageRegistry(url="docker://test"),
                tag="python:3.11",
            ),
            result=OperationResult(image="img-imported", tag="python:3.11"),
        )

        assert response.uuid == "op-2"
        assert response.kind == OperationKind.IMAGE_IMPORT
        assert response.status == OperationStatus.SUCCESS
        assert isinstance(response.metadata, ImportImageMetadata)
        assert response.result is not None
        assert response.result.image == "img-imported"
        assert response.result.tag == "python:3.11"

    def test_failed_operation(self) -> None:
        """Test creating a failed operation response."""
        response = OperationResponse(
            uuid="op-3",
            kind=OperationKind.INSTANCE,
            status=OperationStatus.FAILED,
            error="Command timed out",
        )

        assert response.status == OperationStatus.FAILED
        assert response.error == "Command timed out"


class TestStream:
    """Tests for Stream model."""

    def test_ascii_text(self) -> None:
        """Test getting text from ASCII stream."""
        stream = Stream(value="hello", encoding="ascii")
        assert stream.text() == "hello"

    def test_base64_text(self) -> None:
        """Test getting text from base64 stream."""
        encoded = base64.b64encode(b"hello binary").decode()
        stream = Stream(value=encoded, encoding="base64")
        assert stream.text() == "hello binary"

    def test_truncated_flag(self) -> None:
        """Test truncated flag."""
        stream = Stream(value="partial", encoding="ascii", truncated=True)
        assert stream.truncated is True
        assert stream.text() == "partial"

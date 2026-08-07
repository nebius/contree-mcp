"""Tests for MCP types and their compatibility with contree-client.

MCP models are the public contract, so they are the source of truth in these
tests.  Starting with an MCP model and round-tripping it through the matching
SDK model verifies that every field we expose is supported by contree-client,
without coupling this project to additional SDK fields that MCP does not use.
"""

from typing import Any

import pytest
from contree_client import models as sdk_models
from pydantic import BaseModel

from contree_mcp.tools import mcp_types

CREATED_AT = "2026-01-01T00:00:00Z"


def mcp_operation_summary() -> mcp_types.OperationSummary:
    return mcp_types.OperationSummary(
        uuid="op-summary",
        kind=mcp_types.OperationKind.INSTANCE,
        status=mcp_types.OperationStatus.SUCCESS,
        error=None,
        created_at=CREATED_AT,
        duration=1.5,
        image_size=1024,
        consumed_cpu=0.25,
        consumed_memory=2048,
        image_uuid="img-source",
        result_image_uuid="img-result",
    )


def mcp_instance_operation() -> mcp_types.OperationResponse:
    return mcp_types.OperationResponse(
        uuid="op-instance",
        kind=mcp_types.OperationKind.INSTANCE,
        status=mcp_types.OperationStatus.SUCCESS,
        error=None,
        created_at=CREATED_AT,
        duration=1.5,
        image_size=1024,
        consumed_cpu=0.3,
        consumed_memory=2048,
        image_uuid="img-source",
        result_image_uuid="img-result",
        metadata=mcp_types.InstanceMetadata(
            command="echo ok",
            image="img-source",
            disposable=False,
            hostname="linuxkit",
            args=[],
            shell=True,
            env={"EXAMPLE": "value"},
            preserve_env=False,
            cwd="/work",
            uid=1000,
            gid=1000,
            resources_limits=mcp_types.InstanceResourcesLimits(max_layer_bytes=4096),
            stdin=mcp_types.Stream(value="", encoding="ascii"),
            timeout=60,
            truncate_output_at=1024,
            files={
                "/work/input": mcp_types.InstanceFileSpec(
                    uuid="file-1",
                    uid=1000,
                    gid=1000,
                    mode="0644",
                )
            },
            result=mcp_types.InstanceResult(
                resources=mcp_types.ConsumedResources(
                    block_input=1,
                    block_output=2,
                    cost=0.01,
                    elapsed_time=1.5,
                    involuntary_switches=3,
                    max_rss=2048,
                    monotonic_time=1.6,
                    page_faults=4,
                    page_faults_io=5,
                    shared_memory=6,
                    signals=0,
                    swaps=0,
                    system_cpu_time=0.1,
                    unshared_memory=7,
                    user_cpu_time=0.2,
                    voluntary_switches=8,
                ),
                state=mcp_types.ProcessExitState(
                    continued=False,
                    core_dump=False,
                    exit_code=0,
                    pid=1,
                    signal=0,
                    stopped=False,
                    timed_out=False,
                ),
                stdout=mcp_types.Stream(value="ok\n", encoding="ascii", truncated=False),
                stderr=mcp_types.Stream(value="", encoding="ascii", truncated=False),
            ),
        ),
        result=mcp_types.OperationResult(image="img-result", tag=None),
    )


def mcp_import_operation() -> mcp_types.OperationResponse:
    return mcp_types.OperationResponse(
        uuid="op-import",
        kind=mcp_types.OperationKind.IMAGE_IMPORT,
        status=mcp_types.OperationStatus.SUCCESS,
        error=None,
        created_at=CREATED_AT,
        duration=2.0,
        image_size=4096,
        consumed_cpu=None,
        consumed_memory=None,
        image_uuid=None,
        result_image_uuid="img-imported",
        metadata=mcp_types.ImportImageMetadata(
            registry=mcp_types.ImageRegistry(
                url="docker://registry.example/image:latest",
                credentials=mcp_types.ImageCredentials(
                    username="user",
                    password="secret",
                ),
            ),
            tag="local:image",
            timeout=300,
        ),
        result=mcp_types.OperationResult(image="img-imported", tag="local:image"),
    )


MCP_IMAGE = mcp_types.Image(
    uuid="img-1",
    tag="example:latest",
    created_at=CREATED_AT,
    operation_uuid="op-source",
)
MCP_FILE_ITEM = mcp_types.FileItem(
    size=12,
    path="etc/hosts",
    owner=0,
    group=0,
    mode=0o644,
    mtime=1_767_225_600,
    is_dir=False,
    is_regular=True,
    is_symlink=False,
    is_socket=False,
    is_fifo=False,
    symlink_to="",
)


def sdk_payload(mcp_model: BaseModel) -> dict[str, Any]:
    """Serialize an MCP model and add only SDK-required transport fields."""
    payload = mcp_model.model_dump(mode="json")
    if isinstance(mcp_model, mcp_types.DirectoryList):
        for item in payload["files"]:
            item["uid"] = item["owner"] if isinstance(item["owner"], int) else 0
            item["gid"] = item["group"] if isinstance(item["group"], int) else 0
            item["nlink"] = 1
    return payload


@pytest.mark.parametrize(
    ("mcp_model", "sdk_type"),
    [
        pytest.param(MCP_IMAGE, sdk_models.Image, id="image"),
        pytest.param(
            mcp_types.ImageListResponse(images=[MCP_IMAGE]),
            sdk_models.ImageListResponse,
            id="image-list",
        ),
        pytest.param(
            mcp_types.DirectoryList(path="/etc", files=[MCP_FILE_ITEM]),
            sdk_models.DirectoryList,
            id="directory-list",
        ),
        pytest.param(
            mcp_types.FileResponse(uuid="file-1", sha256="a" * 64, size=3),
            sdk_models.FileResponse,
            id="uploaded-file",
        ),
        pytest.param(
            mcp_types.FileResponse(
                uuid="file-2",
                sha256="b" * 64,
                size=4,
                created_at="2026-01-01T00:00:00+00:00",
                updated_at="2026-01-02T00:00:00+00:00",
            ),
            sdk_models.File,
            id="looked-up-file",
        ),
        pytest.param(
            mcp_types.InstanceSpawnResponse(uuid="op-spawn"),
            sdk_models.InstanceSpawnResponse,
            id="spawn",
        ),
        pytest.param(
            mcp_operation_summary(),
            sdk_models.OperationSummary,
            id="operation-summary",
        ),
        pytest.param(
            mcp_instance_operation(),
            sdk_models.OperationResponse,
            id="instance-operation",
        ),
        pytest.param(
            mcp_import_operation(),
            sdk_models.OperationResponse,
            id="import-operation",
        ),
        pytest.param(
            mcp_types.WhoAmIResponse(
                token_uuid="token-1",
                token_expiration=None,
                permissions={"spawn": True},
                operations_stat={"completed": 1},
                limits={"instance_max_timeout": 3600},
            ),
            sdk_models.WhoAmIResponse,
            id="whoami",
        ),
    ],
)
def test_mcp_model_round_trips_through_sdk(
    mcp_model: BaseModel,
    sdk_type: type[sdk_models.ContreeModel],
) -> None:
    sdk_model = sdk_type.from_dict(sdk_payload(mcp_model))
    round_trip = type(mcp_model).model_validate(sdk_model.to_dict())
    assert round_trip == mcp_model


@pytest.mark.parametrize("mcp_status", list(mcp_types.OperationStatus))
def test_operation_status_round_trips_through_sdk(
    mcp_status: mcp_types.OperationStatus,
) -> None:
    sdk_status = sdk_models.OperationStatus(mcp_status.value)
    assert mcp_types.OperationStatus(sdk_status.value) is mcp_status

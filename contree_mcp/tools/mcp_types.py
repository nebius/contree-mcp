"""Pydantic models used to publish and validate Contree MCP schemas."""

from base64 import b64decode, b64encode
from enum import Enum
from typing import Any, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ByteSize, Field, PositiveInt, model_validator
from typing_extensions import Self

PublicUUID = str(UUID(int=0))

E = TypeVar("E", bound=Enum)


class ImageCredentials(BaseModel):
    username: str = ""
    password: str = ""


class ImageRegistry(BaseModel):
    url: str
    credentials: ImageCredentials = ImageCredentials()


class ImportImageMetadata(BaseModel):
    registry: ImageRegistry
    tag: str | None = None
    timeout: PositiveInt = 300


class ImageSize(BaseModel):
    physical: int = -1
    logical: int = -1


class Image(BaseModel):
    """Response model for image endpoints.

    API handlers:
    - GET /inspect/{image_uuid}/ -> Image
    - GET /inspect/?tag={tag} -> Image (redirect)
    - PATCH /images/{image_uuid}/tag -> Image
    - DELETE /images/{image_uuid}/tag -> Image
    """

    uuid: str = Field(description="Image UUID")
    tag: str | None = Field(default=None, description="Image tag or null")
    created_at: str = Field(default="", description="ISO 8601 creation timestamp")
    operation_uuid: str | None = Field(
        default=None,
        description=(
            "UUID of the operation that created this image. Null for images from another"
            " namespace (public/shared) or images not created by an operation."
        ),
    )


class ImageListResponse(BaseModel):
    """Response from GET /images.

    API handlers:
    - GET /images -> ImageListResponse
    """

    images: list[Image] = Field(default_factory=list)


class FileItem(BaseModel):
    """File info in directory listing."""

    path: str = Field(description="File name relative to directory")
    size: int = Field(description="File size in bytes")
    owner: int | str = Field(description="User ID or name of owner")
    group: int | str = Field(description="Group ID or name")
    mode: int = Field(description="File permissions as integer")
    mtime: int = Field(description="Last modification Unix timestamp")
    is_dir: bool = Field(description="Directory indicator")
    is_regular: bool = Field(description="Regular file indicator")
    is_symlink: bool = Field(description="Symbolic link indicator")
    is_socket: bool = Field(description="Socket indicator")
    is_fifo: bool = Field(description="FIFO/named pipe indicator")
    symlink_to: str = Field(default="", description="Target path for symlinks")


class DirectoryList(BaseModel):
    """Response from GET /inspect/{uuid}/list.

    API handlers:
    - GET /inspect/{image_uuid}/list -> DirectoryList
    """

    path: str = Field(description="Directory path listed")
    files: list[FileItem] = Field(default_factory=list)


class FileResponse(BaseModel):
    """Response from file endpoints.

    API handlers:
    - POST /files -> FileResponse (uuid, sha256, size)
    - GET /files/{sha256} -> FileResponse (uuid, sha256, size, created_at, updated_at)

    Only ``uuid`` is load-bearing for client logic; every other field is
    optional so additive or renamed fields on the backend do not break parsing.
    The ``unwrap_envelopes`` validator also accepts list-shaped responses
    (``{"files": [item, ...]}``) and single-key envelopes (``{"file": item}``)
    so the client survives backend response-shape drift.
    """

    uuid: str = Field(description="File UUID")
    sha256: str = Field(default="", description="SHA256 hash of file content")
    size: int = Field(default=-1, description="File size in bytes; -1 if unknown")
    created_at: str | None = Field(default=None, description="First-upload timestamp (ISO 8601)")
    updated_at: str | None = Field(default=None, description="Last-upload timestamp (ISO 8601)")

    @model_validator(mode="before")
    @classmethod
    def unwrap_envelopes(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if isinstance(data.get("files"), list):
                files = data["files"]
                return files[0] if files else {"uuid": ""}
            if isinstance(data.get("file"), dict):
                return data["file"]
        return data


class InstanceSpawnResponse(BaseModel):
    """Response from POST /instances.

    API handlers:
    - POST /instances -> InstanceSpawnResponse
    - POST /images/import -> InstanceSpawnResponse (same format)
    """

    uuid: str = Field(description="Operation UUID")


class Stream(BaseModel):
    value: str
    encoding: Literal["ascii", "base64"] = "ascii"
    truncated: bool = False

    def text(self) -> str:
        if self.encoding == "ascii":
            return self.value
        elif self.encoding == "base64":
            return b64decode(self.value).decode("utf-8", errors="replace")
        raise ValueError(f"Unsupported encoding: {self.encoding}")

    @classmethod
    def from_bytes(cls, data: bytes, max_size: int = -1) -> Self:
        encoding: Literal["ascii", "base64"]
        truncated = False
        if 0 < max_size < len(data):
            data = data[:max_size]
            truncated = True
        try:
            encoding = "ascii"
            value = data.decode("ascii")
        except UnicodeDecodeError:
            encoding = "base64"
            value = b64encode(data).decode("ascii")
        return cls(value=value, encoding=encoding, truncated=truncated)

    def to_bytes(self) -> bytes:
        match self.encoding:
            case "ascii":
                return self.value.encode("ascii")
            case "base64":
                return b64decode(self.value)
            case _:
                raise ValueError(f"Unsupported encoding: {self.encoding}")

    def __bool__(self) -> bool:
        return bool(self.value)


class ConsumedResources(BaseModel):
    block_input: int = -1
    block_output: int = -1
    cost: float = -1.0
    elapsed_time: float = -1
    involuntary_switches: int = -1
    max_rss: int = -1
    monotonic_time: float = -1
    page_faults: int = -1
    page_faults_io: int = -1
    shared_memory: int = -1
    signals: int = -1
    swaps: int = -1
    system_cpu_time: float = -1.0
    unshared_memory: int = -1
    user_cpu_time: float = -1.0
    voluntary_switches: int = -1
    layer_bytes: int = -1


class ProcessExitState(BaseModel):
    continued: bool = False
    core_dump: bool = False
    exit_code: int = 0
    pid: int = 0
    signal: int = -1
    stopped: bool = False
    timed_out: bool = False


class InstanceResult(BaseModel):
    resources: ConsumedResources = ConsumedResources()
    state: ProcessExitState = ProcessExitState()
    stdout: Stream
    stderr: Stream


class InstanceFileSpec(BaseModel):
    uuid: str
    mode: str = "0644"
    uid: int = 0
    gid: int = 0


class InstanceResourcesLimits(BaseModel):
    """Per-instance resource caps. Mirrors the backend ``InstanceResourcesLimits``.

    Default for ``max_layer_bytes`` matches the backend (12 GiB) — see
    ``contree.types.InstanceResourcesLimits`` and ``DataUnits.GB(12)``.
    """

    max_layer_bytes: PositiveInt = Field(
        default=12 * 1024**3,
        description="Maximum writable layer size in bytes (default 12 GiB).",
    )


class InstanceMetadata(BaseModel):
    """Metadata for instance execution operations."""

    command: str = Field(description="Command to run")
    image: str = Field(description="Image UUID or string starts with 'tag:'")
    hostname: str = "linuxkit"
    args: list[str] = Field(default_factory=list, description="Command arguments, must be used with shell is false")
    shell: bool = Field(default=False, description="In this mode command is a shell expression and args must be empty")
    # ``None`` value removes the variable from the preserved environment;
    # see ``preserve_env`` semantics in the API spec.
    env: dict[str, str | None] = Field(default_factory=dict)
    preserve_env: bool = Field(
        default=False,
        description="Preserve environment variables in resulting image after execution",
    )
    cwd: str = Field(
        default="",
        description=("Working directory; absolute path or empty string. Empty means use the image's default."),
    )
    uid: int = Field(default=0, ge=0, description="User ID to run the process as")
    gid: int = Field(default=0, ge=0, description="Group ID to run the process as")
    disposable: bool = False
    resources_limits: InstanceResourcesLimits = Field(default_factory=InstanceResourcesLimits)
    stdin: Stream = Stream(value="")
    timeout: PositiveInt = 60
    truncate_output_at: ByteSize = ByteSize(1024 * 1024)
    files: dict[str, InstanceFileSpec] = Field(default_factory=dict, description="Files to add to the image")
    result: InstanceResult | None = None


class OperationStatus(str, Enum):
    PENDING = "PENDING"
    EXECUTING = "EXECUTING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    ASSIGNED = "ASSIGNED"

    def __str__(self) -> str:
        return self.value

    def is_terminal(self) -> bool:
        cls = self.__class__
        return self in {cls.SUCCESS, cls.FAILED, cls.CANCELLED}


class OperationKind(str, Enum):
    INSTANCE = "instance"
    IMAGE_IMPORT = "image_import"

    def __str__(self) -> str:
        return self.value


class OperationEventType(str, Enum):
    """Event categories in the SSE stream from GET /operations/{id}/events.

    ``SSE_ERROR`` is synthetic — produced by our SSE parser for
    ``event: sse_error`` frames (plain-text server-side stream errors),
    it never appears in the backend's OperationEventType enum.
    """

    INIT = "init"
    SPAWN = "spawn"
    STDIN = "stdin"
    STDOUT = "stdout"
    STDERR = "stderr"
    EXIT = "exit"
    TRUNCATED = "truncated"
    SIZE_CAP = "size_cap"
    NETWORK = "network"
    SHUTDOWN = "shutdown"
    COMPLETION = "completion"
    SSE_ERROR = "sse_error"

    def __str__(self) -> str:
        return self.value


class OperationResult(BaseModel):
    image: str | None = Field(default=None, description="Result image UUID or null")
    tag: str | None = Field(default=None, description="Assigned tag or null")


class OperationSummary(BaseModel):
    """Summary model for operations in list.

    API handlers:
    - GET /operations -> OperationListResponse.operations (list of OperationSummary)
    """

    uuid: str = Field(description="Operation UUID")
    kind: OperationKind = Field(description="Operation kind")
    status: OperationStatus = Field(description="Operation status")
    error: str | None = Field(default=None, description="Error message if failed")
    created_at: str = Field(default="", description="ISO 8601 creation timestamp")
    duration: float | None = Field(default=None, description="Operation duration in seconds")
    image_size: int | None = Field(default=None, description="Bytes written for the resulting image/layer(s)")
    consumed_cpu: float | None = Field(default=None, description="CPU seconds reported by the in-VM init")
    consumed_memory: int | None = Field(default=None, description="Peak memory (max_rss) reported by the in-VM init")
    image_uuid: str | None = Field(default=None, description="Source image UUID; null for IMAGE_IMPORT ops")
    result_image_uuid: str | None = Field(default=None, description="UUID of the image produced; set only on SUCCESS")


class OperationListResponse(BaseModel):
    """Response from GET /operations.

    API handlers:
    - GET /operations -> OperationListResponse
    """

    operations: list[OperationSummary] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def wrap_list(cls, data: Any) -> Any:
        """Handle backend returning list instead of dict with operations key."""
        if isinstance(data, list):
            return {"operations": data}
        return data


class OperationResponse(BaseModel):
    """Response model for operation detail endpoint.

    API handlers:
    - GET /operations/{operation_id} -> OperationResponse
    """

    uuid: str = Field(default="", description="Operation UUID")
    status: OperationStatus = Field(description="Operation status")
    kind: OperationKind = Field(description="Operation kind")
    error: str | None = Field(default=None, description="Error message if any")
    created_at: str = Field(default="", description="ISO 8601 creation timestamp")
    metadata: InstanceMetadata | ImportImageMetadata | None = Field(default=None, description="Operation metadata")
    result: OperationResult | None = Field(default=None, description="Operation result")
    duration: float | None = Field(default=None, description="Operation duration in seconds")
    image_size: int | None = Field(default=None, description="Bytes written for the resulting image/layer(s)")
    consumed_cpu: float | None = Field(default=None, description="CPU seconds reported by the in-VM init")
    consumed_memory: int | None = Field(default=None, description="Peak memory (max_rss) reported by the in-VM init")
    image_uuid: str | None = Field(default=None, description="Source image UUID; null for IMAGE_IMPORT ops")
    result_image_uuid: str | None = Field(default=None, description="UUID of the image produced; set only on SUCCESS")

    @model_validator(mode="before")
    @classmethod
    def parse_metadata(cls, data: Any) -> Any:
        if isinstance(data, dict) and "kind" in data:
            data = dict(data)  # Create mutable copy
            data["kind"] = data["kind"].lower()
        return data


class CancelOperationResponse(BaseModel):
    """Response from cancel operation endpoint.

    API handlers:
    - DELETE /operations/{operation_id} -> CancelOperationResponse
    """

    uuid: str = Field(default="", description="Operation UUID")
    status: OperationStatus = Field(default=OperationStatus.CANCELLED)


class WhoAmIResponse(BaseModel):
    """Response from token introspection endpoint.

    API handlers:
    - GET /whoami -> WhoAmIResponse

    ``permissions`` maps permission names to booleans (e.g. ``import``,
    ``spawn``, ``list``). ``limits`` maps resource limit names to ints
    (e.g. ``instance_max_timeout``). ``operations_stat`` is reserved
    for future use and may be empty.
    """

    token_uuid: str = Field(description="UUID of the authentication token")
    token_expiration: int | None = Field(
        default=None,
        description="Token expiration time as Unix timestamp, or null if not set",
    )
    permissions: dict[str, bool] = Field(default_factory=dict)
    limits: dict[str, int] = Field(default_factory=dict)
    operations_stat: dict[str, int] = Field(default_factory=dict)

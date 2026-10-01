"""Typed contracts shared by the gateway, policy, budget and provider adapters."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Literal, Optional


class Capability(str, Enum):
    TEXT = "text"
    STREAMING = "streaming"
    VISION = "vision"
    TOOLS = "tools"
    JSON_SCHEMA = "json_schema"
    REASONING = "reasoning"
    EMBEDDINGS = "embeddings"
    AUDIO = "audio"


class DataClass(str, Enum):
    """What the request may contain. Policy decides where it may travel."""
    PUBLIC = "public"            # no personal content (e.g. market news summary)
    MASKED = "masked"            # PII replaced with tokens
    PERSONAL = "personal"        # user's own private content
    SENSITIVE = "sensitive"      # health / financial documents


class Mode(str, Enum):
    AUTO = "auto"
    CHOOSE = "choose"
    LOCAL_ONLY = "local_only"


class Profile(str, Enum):
    ECONOMY = "economy"
    BALANCED = "balanced"
    QUALITY = "quality"


class Locality(str, Enum):
    LOCAL = "local"
    CLOUD = "cloud"


class FinishReason(str, Enum):
    STOP = "stop"
    LENGTH = "length"
    TOOL = "tool"
    CONTENT_FILTER = "content_filter"
    ERROR = "error"
    CANCELLED = "cancelled"


class ErrorCode(str, Enum):
    MISSING_KEY = "missing_key"
    INVALID_KEY = "invalid_key"
    UNSUPPORTED_MODEL = "unsupported_model"
    CAPABILITY_MISSING = "capability_missing"
    QUOTA_EXHAUSTED = "quota_exhausted"
    POLICY_DENIED = "policy_denied"
    CONSENT_REQUIRED = "consent_required"
    LOCAL_MODEL_MISSING = "local_model_missing"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    MALFORMED_OUTPUT = "malformed_output"
    SAFETY_REFUSAL = "safety_refusal"
    INPUT_TOO_LARGE = "input_too_large"


class AIError(Exception):
    """Normalized gateway error. Never carries raw upstream bodies or secrets."""

    def __init__(self, code: ErrorCode, message: str, *, retryable: bool = False,
                 provider: str | None = None, model: str | None = None, http_status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.provider = provider
        self.model = model
        self.http_status = http_status

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code.value, "message": self.message, "retryable": self.retryable,
                "provider": self.provider, "model": self.model}


@dataclass(frozen=True)
class ActorContext:
    """Authenticated principal for a request. Never built from browser input."""
    user_id: str
    tenant_id: Optional[str] = None
    role: str = "user"
    is_background: bool = False

    @property
    def scope_key(self) -> str:
        return f"{self.tenant_id or '-'}:{self.user_id}"


@dataclass
class Message:
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema


@dataclass
class ToolProposal:
    """A model-proposed action. The backend decides whether to execute it."""
    id: str
    name: str
    arguments: dict[str, Any]
    raw_arguments: str = ""
    complete: bool = True


@dataclass
class Selection:
    """How the caller wants the model chosen."""
    mode: Optional[Mode] = None
    profile: Optional[Profile] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    allow_fallback: Optional[bool] = None
    scope: Literal["request", "conversation", "task", "user", "platform"] = "request"


@dataclass
class AIRequest:
    actor: ActorContext
    task: str                                   # e.g. "assistant", "finance", "extract"
    messages: list[Message]
    data_class: DataClass = DataClass.PERSONAL
    required: set[Capability] = field(default_factory=lambda: {Capability.TEXT})
    selection: Selection = field(default_factory=Selection)
    temperature: float = 0.2
    max_output_tokens: Optional[int] = None
    json_schema: Optional[dict[str, Any]] = None
    tools: list[ToolSpec] = field(default_factory=list)
    max_tool_calls: int = 4
    deadline_s: Optional[float] = None
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    idempotency_key: Optional[str] = None
    conversation_id: Optional[str] = None
    cacheable: bool = True

    @property
    def prompt_chars(self) -> int:
        return sum(len(m.content) for m in self.messages)


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    reasoning_tokens: int = 0
    tool_calls: int = 0
    estimated: bool = True   # provider did not report exact counts

    def as_dict(self) -> dict[str, int | bool]:
        return {"input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
                "cached_input_tokens": self.cached_input_tokens,
                "reasoning_tokens": self.reasoning_tokens, "tool_calls": self.tool_calls,
                "estimated": self.estimated}


@dataclass
class AIResponse:
    request_id: str
    provider: str
    model: str
    locality: Locality
    text: str = ""
    structured: Optional[Any] = None
    tool_proposals: list[ToolProposal] = field(default_factory=list)
    finish: FinishReason = FinishReason.STOP
    usage: Usage = field(default_factory=Usage)
    cost_micro_usd: int = 0
    cost_final: bool = False
    price_version: Optional[str] = None
    latency_ms: int = 0
    fallback_from: Optional[str] = None
    fallback_reason: Optional[str] = None
    mode: Optional[str] = None
    cached: bool = False

    def metadata(self) -> dict[str, Any]:
        """Client-safe metadata for the response badge and audit log."""
        return {
            "request_id": self.request_id,
            "provider": self.provider,
            "model": self.model,
            "locality": self.locality.value,
            "mode": self.mode,
            "fallback_from": self.fallback_from,
            "fallback_reason": self.fallback_reason,
            "finish": self.finish.value,
            "usage": self.usage.as_dict(),
            "cost_micro_usd": self.cost_micro_usd,
            "cost_final": self.cost_final,
            "latency_ms": self.latency_ms,
            "cached": self.cached,
        }


@dataclass
class StreamEvent:
    type: Literal["started", "text_delta", "tool_proposal", "usage", "completed", "cancelled", "error"]
    data: Any = None


StreamIterator = AsyncIterator[StreamEvent]

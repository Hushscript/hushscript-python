from __future__ import annotations

import json
import math
import re
from typing import TYPE_CHECKING, Any, ClassVar, Final

from ._json import as_dict, as_list
from ._redact import Credentials, redact
from .generated.catalog import ERROR_CATALOG
from .generated.hints import HINTS
from .generated.scopes import OPERATION_SCOPES

if TYPE_CHECKING:
    from collections.abc import Mapping

    import httpx

_PLACEHOLDER: Final = re.compile(r"\{(\w+)\}")
_TEMPLATE_PARAMETER: Final = re.compile(r"\\\{[^}/]+\\\}")


def _camel(key: str) -> str:
    head, *rest = key.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in rest)


def _format_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def _format_context_value(value: object) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return _format_number(value)
    items = as_list(value)
    if items is not None:
        names = [str(item) for item in items]
        if len(names) > 1:
            return f"{', '.join(names[:-1])} and {names[-1]}"
        return "".join(names)
    return str(value)


def _hint_context(
    details: Mapping[str, object], retry_after: float | None, scope: str | None
) -> dict[str, str]:
    context = {_camel(key): _format_context_value(value) for key, value in details.items()}
    needed = details.get("needed_seconds")
    if isinstance(needed, (int, float)) and not isinstance(needed, bool):
        context["needed"] = str(math.ceil(needed / 60))
    available = details.get("balance_seconds")
    if isinstance(available, (int, float)) and not isinstance(available, bool):
        context["balance"] = str(int(available / 60))
    if retry_after is not None:
        context["retryAfter"] = _format_number(retry_after)
    if scope is not None:
        context["scope"] = scope
    return context


def render_hint(
    code: str,
    details: Mapping[str, object] | None = None,
    retry_after: float | None = None,
    scope: str | None = None,
) -> str | None:
    template = HINTS.get(code)
    if template is None:
        return None
    context = _hint_context(details or {}, retry_after, scope)
    return _PLACEHOLDER.sub(lambda match: context.get(match.group(1), match.group(0)), template)


class HushscriptError(Exception):
    default_code: ClassVar[str] = "hushscript_error"
    auto_hint: ClassVar[bool] = True

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        numeric_code: int | None = None,
        status: int | None = None,
        hint: str | None = None,
        details: Mapping[str, object] | None = None,
        retry_after: float | None = None,
        scope: str | None = None,
    ) -> None:
        self.code: str = code or self.default_code
        self.numeric_code: int | None = numeric_code
        self.status: int | None = status
        self.details: dict[str, object] = dict(details or {})
        self.retry_after: float | None = retry_after
        if hint is None and self.auto_hint:
            hint = render_hint(self.code, self.details, retry_after, scope)
        self.hint: str | None = redact(hint) if hint is not None else None
        self.message: str = redact(message)
        super().__init__(self.message)

    def __str__(self) -> str:
        return f"{self.message} {self.hint}" if self.hint else self.message

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(code={self.code!r}, status={self.status!r}, "
            f"message={self.message!r})"
        )


class ConfigurationError(HushscriptError):
    default_code = "config_invalid"
    auto_hint = False


class PreflightError(HushscriptError):
    """The request was refused before any credit hold was placed."""


class UnsupportedMediaError(PreflightError):
    default_code = "unsupported_media"


class FileLimitError(PreflightError):
    default_code = "size_out_of_range"


class DailyLimitError(PreflightError):
    default_code = "daily_limit"


class ResumeMismatchError(PreflightError):
    default_code = "resume_file_mismatch"


class ApiError(HushscriptError):
    default_code = "api_error"


class AuthenticationError(ApiError):
    default_code = "unauthorized"


class PermissionError(ApiError):  # spec 9.2 names this class PermissionError
    default_code = "pat_forbidden"


class InsufficientBalanceError(ApiError):
    default_code = "insufficient_balance"


class NotFoundError(ApiError):
    default_code = "not_found"


class ConflictError(ApiError):
    default_code = "wrong_state"


class ValidationError(ApiError):
    default_code = "bad_request"


class RateLimitError(ApiError):
    default_code = "rate_limited"


class PaymentMethodRequiredError(HushscriptError):
    default_code = "no_default_card"


class UploadError(HushscriptError):
    default_code = "upload_incomplete"


class JobFailedError(HushscriptError):
    default_code = "job_failed"

    def __init__(
        self,
        message: str,
        *,
        job_id: str | None = None,
        error: str | None = None,
        failure_kind: str | None = None,
        **kwargs: Any,  # noqa: ANN401  # forwarded to HushscriptError, which types them
    ) -> None:
        super().__init__(message, **kwargs)
        self.job_id = job_id
        self.error = redact(error) if error is not None else None
        self.failure_kind = failure_kind


class WaitTimeoutError(HushscriptError):
    default_code = "wait_timeout"

    def __init__(
        self,
        message: str,
        *,
        resume_token: str | None = None,
        **kwargs: Any,  # noqa: ANN401  # forwarded to HushscriptError, which types them
    ) -> None:
        super().__init__(message, **kwargs)
        self.resume_token = resume_token


class AbortError(HushscriptError):
    default_code = "aborted"

    def __init__(
        self,
        message: str,
        *,
        resume_token: str | None = None,
        **kwargs: Any,  # noqa: ANN401  # forwarded to HushscriptError, which types them
    ) -> None:
        super().__init__(message, **kwargs)
        self.resume_token = resume_token


class NetworkError(HushscriptError):
    default_code = "network_error"


class OutcomeUnknownError(HushscriptError):
    default_code = "outcome_unknown"


_CLASS_BY_SLUG: Final[dict[str, type[HushscriptError]]] = {
    "upload_incomplete": UploadError,
    "size_exceeded": UploadError,
    "agent_claim_invalid": AuthenticationError,
    "unauthorized": AuthenticationError,
    "pat_scope_missing": PermissionError,
    "pat_forbidden": PermissionError,
    "account_suspended": PermissionError,
    "agent_pack_locked": PermissionError,
    "pat_purchase_requires_app": PermissionError,
    "pat_purchase_requires_authentication": PermissionError,
    "country_restricted": PermissionError,
    "signup_not_allowed": PermissionError,
    "insufficient_balance": InsufficientBalanceError,
    "org_insufficient_balance": InsufficientBalanceError,
    "org_pool_expired": InsufficientBalanceError,
    "org_plan_frozen": InsufficientBalanceError,
    "wrong_state": ConflictError,
    "agent_signup_pending": ConflictError,
    "pat_limit": ConflictError,
    "rate_limited": RateLimitError,
    "too_many_active_jobs": RateLimitError,
    "agent_purchase_capped": RateLimitError,
    "url_target_busy": RateLimitError,
}

_CLASS_BY_STATUS: Final[dict[int, type[HushscriptError]]] = {
    400: ValidationError,
    401: AuthenticationError,
    402: InsufficientBalanceError,
    403: PermissionError,
    404: NotFoundError,
    409: ConflictError,
    422: ValidationError,
    429: RateLimitError,
}

_OPERATION_PATTERNS: Final = [
    (re.compile("^" + _TEMPLATE_PARAMETER.sub("[^/]+", re.escape(key.split(" ", 1)[1])) + "$"), key)
    for key in OPERATION_SCOPES
]


def operation_key(method: str, path: str) -> str | None:
    """Maps a concrete request (`GET`, `/v1/jobs/abc`) to its OPERATION_SCOPES key."""
    prefix = f"{method.upper()} "
    for pattern, key in _OPERATION_PATTERNS:
        if key.startswith(prefix) and pattern.match(path):
            return key
    return None


def parse_retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    text = value.strip()
    return float(int(text)) if text.isascii() and text.isdigit() else None


def _extra_details(body: Mapping[str, object]) -> dict[str, object]:
    details: dict[str, object] = {
        key: value for key, value in body.items() if key not in {"error", "code", "details"}
    }
    nested = body.get("details")
    nested_details = as_dict(nested)
    if nested_details is not None:
        for key, value in nested_details.items():
            details.setdefault(key, value)
    elif nested is not None:
        details["details"] = nested
    return details


def _operation_of(response: httpx.Response) -> str | None:
    try:
        request = response.request
    except RuntimeError:  # the response was built without a request
        return None
    return operation_key(request.method, request.url.path)


def _parse_body(response: httpx.Response) -> dict[str, object]:
    try:
        parsed: object = json.loads(response.content)
    except ValueError:
        return {}
    return as_dict(parsed) or {}


def error_from_response(
    response: httpx.Response,
    *,
    credentials: Credentials | None = None,
    operation: str | None = None,
) -> HushscriptError:
    """Builds the spec 9.2 error for a non-2xx API response."""
    credentials = credentials or Credentials()
    status = response.status_code
    body = _parse_body(response)
    slug = body.get("error")
    code_value = body.get("code")
    numeric_code = (
        code_value if isinstance(code_value, int) and not isinstance(code_value, bool) else None
    )
    code = slug if isinstance(slug, str) and slug else f"http_{status}"
    entry = ERROR_CATALOG.get(code)
    message = entry.meaning if entry is not None else f"The API answered {status} ({code})."
    if operation is None:
        operation = _operation_of(response)
    retry_after = parse_retry_after(response.headers.get("retry-after"))
    details = as_dict(credentials.scrub_value(_extra_details(body))) or {}
    error_class = _CLASS_BY_SLUG.get(code) or _CLASS_BY_STATUS.get(status) or ApiError
    return error_class(
        credentials.scrub(message),
        code=code,
        numeric_code=numeric_code,
        status=status,
        details=details,
        retry_after=retry_after,
        scope=OPERATION_SCOPES.get(operation) if operation else None,
    )


def raise_for_response(
    response: httpx.Response,
    *,
    credentials: Credentials | None = None,
    operation: str | None = None,
) -> None:
    if response.is_success:
        return
    raise error_from_response(response, credentials=credentials, operation=operation)

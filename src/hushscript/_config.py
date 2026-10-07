from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final
from urllib.parse import urlsplit

from ._errors import ConfigurationError
from ._log import LOG_LEVELS
from ._redact import Credentials

if TYPE_CHECKING:
    from collections.abc import Mapping

DEFAULT_BASE_URL: Final = "https://api.hushscript.com"
DEFAULT_TIMEOUT: Final = 60.0
PART_TIMEOUT: Final = 300.0
DEFAULT_MAX_RETRIES: Final = 3
TOKEN_ENV: Final = "HUSHSCRIPT_TOKEN"  # noqa: S105  # the name of an environment variable
BASE_URL_ENV: Final = "HUSHSCRIPT_BASE_URL"
LOG_ENV: Final = "HUSHSCRIPT_LOG"
TOKEN_PREFIX: Final = "hsr"  # noqa: S105  # the token family prefix, not a secret
PRINTABLE_FIRST: Final = 0x21
PRINTABLE_LAST: Final = 0x7E
LOOPBACK_HOSTS: Final = frozenset({"localhost", "127.0.0.1", "::1"})

SETUP_HINT: Final = (
    "Set HUSHSCRIPT_TOKEN or pass a token. Create one in the Hushscript app: "
    "Account → Connected apps (app.hushscript.com/account/mcp)."
)


@dataclass(frozen=True, slots=True)
class Config:
    credentials: Credentials
    base_url: str
    timeout: float
    max_retries: int
    log_level: str


def _validate_base_url(raw: str) -> str:
    parts = urlsplit(raw)
    if parts.path not in {"", "/"} or "?" in raw or "#" in raw:
        # Requests are classified by their path relative to the base URL (spec 7.4), so it has none.
        raise ConfigurationError("base_url must not have a path, query or fragment.")
    host = parts.hostname or ""
    secure = parts.scheme == "https"
    loopback = parts.scheme == "http" and host in LOOPBACK_HOSTS
    if not (secure or loopback) or not host or parts.username or parts.password:
        raise ConfigurationError(
            "base_url must be https://, or http:// to localhost, 127.0.0.1 or [::1]."
        )
    return raw.rstrip("/")


def _is_positive_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def _is_non_negative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def acceptable_token(token: str) -> bool:
    """The check every token passes, at construction and after a claim or a rotation: printable
    ASCII only, and the `hsr` prefix."""
    return token.startswith(TOKEN_PREFIX) and all(
        PRINTABLE_FIRST <= ord(char) <= PRINTABLE_LAST for char in token
    )


def resolve_tokenless_config(  # mirrors the keyword surface of the static agent calls
    *,
    base_url: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    log_level: str | None = None,
    env: Mapping[str, str] | None = None,
) -> Config:
    """The config of a call that needs no token: HUSHSCRIPT_TOKEN is neither read nor sent."""
    environment = os.environ if env is None else env
    resolved_url = _validate_base_url(base_url or environment.get(BASE_URL_ENV) or DEFAULT_BASE_URL)
    if not _is_positive_number(timeout):
        raise ConfigurationError("timeout must be a positive number of seconds.")
    level = log_level if log_level is not None else environment.get(LOG_ENV) or "off"
    if level not in LOG_LEVELS:
        raise ConfigurationError(f"log_level must be one of {', '.join(LOG_LEVELS)}.")
    return Config(
        credentials=Credentials(),
        base_url=resolved_url,
        timeout=float(timeout),
        max_retries=0,
        log_level=level,
    )


def resolve_config(  # mirrors the public constructor
    token: str | None = None,
    *,
    base_url: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
    log_level: str | None = None,
    env: Mapping[str, str] | None = None,
) -> Config:
    environment = os.environ if env is None else env
    resolved_token = (token or environment.get(TOKEN_ENV, "")).strip()
    if not resolved_token:
        raise ConfigurationError("No Hushscript token was provided.", hint=SETUP_HINT)
    if any(not PRINTABLE_FIRST <= ord(char) <= PRINTABLE_LAST for char in resolved_token):
        # The message never echoes the token (spec 7.4).
        raise ConfigurationError("The token contains control or non-printable characters.")
    if not resolved_token.startswith(TOKEN_PREFIX):
        raise ConfigurationError("This doesn't look like a Hushscript token.")
    resolved_url = _validate_base_url(base_url or environment.get(BASE_URL_ENV) or DEFAULT_BASE_URL)
    if not _is_positive_number(timeout):
        raise ConfigurationError("timeout must be a positive number of seconds.")
    if not _is_non_negative_int(max_retries):
        raise ConfigurationError("max_retries must be a non-negative integer.")
    level = log_level if log_level is not None else environment.get(LOG_ENV) or "off"
    if level not in LOG_LEVELS:
        raise ConfigurationError(f"log_level must be one of {', '.join(LOG_LEVELS)}.")
    return Config(
        credentials=Credentials(resolved_token),
        base_url=resolved_url,
        timeout=float(timeout),
        max_retries=max_retries,
        log_level=level,
    )

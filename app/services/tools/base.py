"""Tool registry shared by every LLM tool (finance + Google)."""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional

from app.config import settings
from app.providers.google import (
    GoogleAPIError,
    GoogleError,
    GoogleNotConfigured,
    GoogleNotConnected,
    GoogleNotFound,
    GoogleRateLimited,
    GoogleReauthRequired,
    SERVICE_LABELS,
)

logger = logging.getLogger(__name__)

ToolHandler = Callable[[Dict[str, Any]], Awaitable[Any]]


@dataclass(frozen=True)
class ToolSpec:
    """One callable exposed to the LLM."""

    name: str
    description: str
    parameters: Dict[str, Any]
    handler: ToolHandler
    timeout_seconds: float = 30.0

    def to_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """Holds the tools available for a single conversation turn."""

    def __init__(self, specs: Optional[Iterable[ToolSpec]] = None):
        self._specs: Dict[str, ToolSpec] = {}

        for spec in specs or []:
            self.register(spec)

    def register(self, spec: ToolSpec) -> None:
        self._specs[spec.name] = spec

    def extend(self, specs: Iterable[ToolSpec]) -> None:
        for spec in specs:
            self.register(spec)

    def __contains__(self, name: str) -> bool:
        return name in self._specs

    def __len__(self) -> int:
        return len(self._specs)

    @property
    def schemas(self) -> List[Dict[str, Any]]:
        return [spec.to_schema() for spec in self._specs.values()]

    async def execute(
        self,
        name: str,
        arguments: Dict[str, Any],
    ) -> str:
        """Run a tool and always return a JSON string for the LLM."""

        spec = self._specs.get(name)

        if spec is None:
            return _dump(
                {
                    "error": "unknown_tool",
                    "message": f"No tool named '{name}' is available.",
                }
            )

        started = time.monotonic()

        try:
            result = await asyncio.wait_for(
                spec.handler(arguments),
                timeout=spec.timeout_seconds,
            )
            payload = _dump(result)

        except asyncio.TimeoutError:
            logger.warning("Tool %s timed out", name)
            payload = _dump(
                {
                    "error": "timeout",
                    "message": (
                        f"'{name}' took too long to respond. "
                        "Tell the user the data source was slow."
                    ),
                }
            )

        except GoogleError as exc:
            payload = _dump(_google_error_payload(exc))

        except Exception as exc:  # noqa: BLE001 - surfaced to the LLM
            logger.exception("Tool %s failed", name)
            payload = _dump(
                {
                    "error": "tool_failed",
                    "message": f"{type(exc).__name__}: {exc}",
                }
            )

        logger.info(
            "Tool %s finished in %.0f ms (%s chars)",
            name,
            (time.monotonic() - started) * 1000,
            len(payload),
        )

        return payload


def _google_error_payload(exc: GoogleError) -> Dict[str, Any]:

    if isinstance(exc, GoogleNotConnected):
        label = SERVICE_LABELS.get(exc.service_name, exc.service_name)
        return {
            "error": "not_connected",
            "service": exc.service_name,
            "message": (
                f"The user has not connected {label}. "
                "Ask them to run /connect in Telegram and pick "
                f"{label}, then retry."
            ),
        }

    if isinstance(exc, GoogleReauthRequired):
        label = SERVICE_LABELS.get(exc.service_name, exc.service_name)
        return {
            "error": "reauth_required",
            "service": exc.service_name,
            "message": (
                f"{label} access expired or was revoked. "
                "Ask the user to reconnect it with /connect."
            ),
        }

    if isinstance(exc, GoogleNotConfigured):
        return {
            "error": "not_configured",
            "message": (
                "Google integrations are not configured on the server."
            ),
        }

    if isinstance(exc, GoogleRateLimited):
        return {
            "error": "rate_limited",
            "message": (
                "Google is rate limiting requests. "
                "Ask the user to try again shortly."
            ),
        }

    if isinstance(exc, GoogleNotFound):
        return {
            "error": "not_found",
            "message": str(exc),
        }

    if isinstance(exc, GoogleAPIError):
        return {
            "error": "google_api_error",
            "status_code": exc.status_code,
            "message": str(exc),
        }

    return {"error": "google_error", "message": str(exc)}


def _dump(result: Any) -> str:

    if isinstance(result, str):
        payload = result
    else:
        payload = json.dumps(result, default=str, ensure_ascii=False)

    limit = settings.TOOL_RESULT_MAX_CHARS

    if len(payload) > limit:
        payload = payload[:limit] + "...[truncated]"

    return payload or "{}"

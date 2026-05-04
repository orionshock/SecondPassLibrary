from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


class ErrorCode:
    """
    Custom API error codes.

    Keep this minimal: only add codes once the API actually uses them.
    """


@dataclass(frozen=True, slots=True)
class ApiError:
    code: str
    message: str
    detail: str = ""
    hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "detail": self.detail,
                "hint": self.hint,
            }
        }


def api_error_payload(
    *, code: str, message: str, detail: str = "", hint: str = ""
) -> dict[str, Any]:
    return ApiError(code=code, message=message, detail=detail, hint=hint).to_dict()


def api_error_response(
    *,
    code: str,
    message: str,
    detail: str = "",
    hint: str = "",
    status_code: int = 400,
    headers: Optional[dict[str, str]] = None,
):
    """
    Return a consistent error Response payload for custom API errors.

    Note: This is intended for places where views hand-craft error Responses. It
    does not attempt to replace DRF's native validation error format yet.
    """
    from rest_framework.response import Response

    return Response(
        api_error_payload(code=code, message=message, detail=detail, hint=hint),
        status=status_code,
        headers=headers,
    )

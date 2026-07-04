from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


class ErrorCode:
    """
    Custom API error codes.

    Keep this minimal: only add codes once the API actually uses them.
    """

    PERMISSION_DENIED = "PERMISSION_DENIED"
    NOT_FOUND = "NOT_FOUND"
    INVALID_REQUEST = "INVALID_REQUEST"
    MISSING_UPLOAD_FILE = "MISSING_UPLOAD_FILE"
    INVALID_UPLOAD_TYPE = "INVALID_UPLOAD_TYPE"
    GROUP_IDENTITY_IMMUTABLE = "GROUP_IDENTITY_IMMUTABLE"
    ADVANCED_GROUPS_DISABLED = "ADVANCED_GROUPS_DISABLED"
    PUBLIC_GROUP_PROTECTED = "PUBLIC_GROUP_PROTECTED"
    INVALID_ROLE_CHANGE = "INVALID_ROLE_CHANGE"
    SELF_DEACTIVATION_BLOCKED = "SELF_DEACTIVATION_BLOCKED"
    UNSAFE_FIELD = "UNSAFE_FIELD"


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

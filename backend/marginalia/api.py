from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework import status

from accounts.client_sessions.authentication import ClientBearerAuthentication
from core.errors import ErrorCode, api_error_response


class MarginaliaReadMixin:
    authentication_classes = [SessionAuthentication, ClientBearerAuthentication]
    permission_classes = [IsAuthenticated]


class SessionAuthenticationRequiredForSessionDelete(BasePermission):
    """Keep Reading Session deletion outside the client bearer allow-list."""

    message = "Client bearer credentials cannot delete Reading Sessions."

    def has_permission(self, request, view) -> bool:
        if request.method != "DELETE":
            return True
        return isinstance(request.successful_authenticator, SessionAuthentication)


def session_closed_response():
    return api_error_response(
        code=ErrorCode.SESSION_CLOSED,
        message="The Reading Session is closed.",
        status_code=status.HTTP_409_CONFLICT,
    )


def book_access_required_response():
    return api_error_response(
        code=ErrorCode.PERMISSION_DENIED,
        message="Current Library access to the Book is required.",
        status_code=status.HTTP_403_FORBIDDEN,
    )


def invalid_request_response(*, message: str, status_code=status.HTTP_400_BAD_REQUEST):
    return api_error_response(
        code=ErrorCode.INVALID_REQUEST,
        message=message,
        status_code=status_code,
    )

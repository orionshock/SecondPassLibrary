from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from accounts.authentication import ClientBearerAuthentication
from core.errors import ErrorCode, api_error_response


class MarginaliaReadMixin:
    authentication_classes = [SessionAuthentication, ClientBearerAuthentication]
    permission_classes = [IsAuthenticated]


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

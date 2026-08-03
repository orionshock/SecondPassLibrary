from __future__ import annotations

from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import BasePermission, IsAuthenticated, SAFE_METHODS

from accounts.authentication import ClientBearerAuthentication


class SessionWriteOrBearerRead(BasePermission):
    """Bearer credentials are read-only throughout the Library API."""

    message = "Client bearer credentials have read-only Library access."

    def has_permission(self, request, view) -> bool:
        if request.method in SAFE_METHODS:
            return True
        if request.method not in view.allowed_methods:
            return True
        return isinstance(request.successful_authenticator, SessionAuthentication)


class LibraryBearerReadMixin:
    authentication_classes = [SessionAuthentication, ClientBearerAuthentication]
    permission_classes = [IsAuthenticated, SessionWriteOrBearerRead]

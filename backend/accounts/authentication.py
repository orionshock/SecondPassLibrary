from __future__ import annotations

from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from .client_api import authenticate_bearer_token


class ClientBearerAuthentication(BaseAuthentication):
    """
    Client API bearer-token authentication.

    This authentication class is opt-in: it is enabled only on endpoints that
    explicitly include it in their authentication_classes.

    Current intended bearer-token surfaces include:

    - `/api/v1/accounts/me/` (read-only for bearer tokens)
    - read-only Library catalog and visible-group endpoints
    - reading user-data endpoints (sessions/progress/annotations; user-owned data)

    Management/product UI/admin endpoints should not enable bearer auth unless
    deliberately designed and explicitly allow-listed.
    """

    keyword = "Bearer"

    def authenticate(self, request):
        header = get_authorization_header(request)
        if not header:
            return None

        try:
            auth = header.decode("utf-8")
        except Exception:
            raise AuthenticationFailed("Invalid Authorization header.")

        parts = auth.split()
        if len(parts) != 2:
            return None

        if parts[0] != self.keyword:
            return None

        raw_token = parts[1].strip()
        if not raw_token:
            raise AuthenticationFailed("Invalid bearer token.")

        session = authenticate_bearer_token(raw_token)
        if not session:
            raise AuthenticationFailed("Invalid bearer token.")

        return (session.user, session)

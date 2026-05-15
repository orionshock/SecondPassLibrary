from __future__ import annotations

from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from .client_api import authenticate_bearer_token


class ClientBearerAuthentication(BaseAuthentication):
    """
    Client API bearer-token authentication.

    Phase 1 guardrail: this authentication class is only enabled on endpoints
    that explicitly opt in (e.g. /api/v1/accounts/me/).
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


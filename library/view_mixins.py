from typing import Any, cast

from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied

from accounts.authentication import ClientBearerAuthentication
from accounts.models import UserClientSession

class ClientBearerReadOnlyMixin:
    """
    Allow Client API bearer tokens only for explicitly allowed read actions.

    Notes:
    - Session auth continues to work normally.
    - If a request is authenticated via a client bearer token (request.auth is a
      UserClientSession), disallowed actions are rejected with 403.
    """

    authentication_classes = [
        SessionAuthentication,
        ClientBearerAuthentication,
    ]

    # Map of DRF action -> allowed HTTP methods for client bearer auth.
    client_bearer_allowed: dict[str, set[str]] = {}

    def initial(self, request, *args, **kwargs):
        # Pylance can't reliably infer the `super()` type for a mixin; at runtime
        # this is always a DRF view/viewset that implements `initial`.
        cast(Any, super()).initial(request, *args, **kwargs)
        if isinstance(getattr(request, "auth", None), UserClientSession):
            action = getattr(self, "action", None)
            if not action:
                # Fallback for edge cases where DRF hasn't set `self.action` yet.
                ctx = getattr(request, "parser_context", None) or {}
                if isinstance(ctx, dict):
                    action = ctx.get("action") or ""
                else:
                    action = ""
            allowed = self.client_bearer_allowed.get(str(action), set())
            if request.method.upper() not in allowed:
                raise PermissionDenied("Client API tokens are read-only for this endpoint.")



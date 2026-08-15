from typing import Any, cast

from rest_framework import status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.client_sessions.authentication import ClientBearerAuthentication
from accounts.models import UserClientSession, UserProfile

from .serializers import CurrentUserPatchSerializer, CurrentUserSerializer, UserProfileSerializer
from .services import build_current_user_me_payload, update_current_user_via_me_api


class UserProfileViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Explicit ordering avoids DRF's UnorderedObjectListWarning under pagination.
        return (
            UserProfile.objects.select_related("user")
            .filter(user=self.request.user)
            .order_by("user__username", "id")
        )


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [
        SessionAuthentication,
        ClientBearerAuthentication,
    ]

    def get(self, request):
        payload = build_current_user_me_payload(user=request.user)
        serializer = CurrentUserSerializer(payload)
        return Response(serializer.data)

    def patch(self, request):
        # Phase 1 guardrail: Client API bearer tokens may read /me but not update it.
        if isinstance(getattr(request, "auth", None), UserClientSession):
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)

        patch = CurrentUserPatchSerializer(data=request.data or {})
        patch.is_valid(raise_exception=True)
        data = cast(dict[str, Any], patch.validated_data)

        update_current_user_via_me_api(
            user=request.user,
            email=data.get("email"),
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
        )

        payload = build_current_user_me_payload(user=request.user)
        serializer = CurrentUserSerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)


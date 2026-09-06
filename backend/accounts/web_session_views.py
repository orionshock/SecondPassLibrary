from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts import session_control


class CurrentUserLogoutOtherWebSessionsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        session_control.revoke_other_web_sessions(
            request.user,
            getattr(request, "session", None),
            actor=request.user,
            reason="manual_revoke",
        )
        return Response({"message": "Other web sessions logged out."}, status=status.HTTP_200_OK)

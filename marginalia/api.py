from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated

from accounts.authentication import ClientBearerAuthentication


class MarginaliaReadMixin:
    authentication_classes = [SessionAuthentication, ClientBearerAuthentication]
    permission_classes = [IsAuthenticated]

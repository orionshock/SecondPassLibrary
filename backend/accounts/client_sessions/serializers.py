from rest_framework import serializers

from accounts.models import UserClientSession


class CurrentUserClientSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserClientSession
        fields = [
            "id",
            "name",
            "client_type",
            "created_at",
            "updated_at",
            "last_seen_at",
            "revoked_at",
        ]
        read_only_fields = fields

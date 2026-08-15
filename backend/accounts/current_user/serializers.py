from rest_framework import serializers

from accounts.models import UserProfile
from core.errors import ErrorCode, api_error_payload


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ["id", "role", "created_at", "updated_at"]
        read_only_fields = fields


class CurrentUserSerializer(serializers.Serializer):
    class GroupSummarySerializer(serializers.Serializer):
        id = serializers.UUIDField()
        name = serializers.CharField()
        is_public_group = serializers.BooleanField()
        is_curator = serializers.BooleanField(required=False)

    username = serializers.CharField()
    email = serializers.EmailField(allow_blank=True)
    first_name = serializers.CharField(allow_blank=True)
    last_name = serializers.CharField(allow_blank=True)
    profile_id = serializers.UUIDField()
    role = serializers.CharField()
    must_change_password = serializers.BooleanField(required=False)
    is_owner = serializers.BooleanField(required=False)
    can_access_django_admin = serializers.BooleanField(required=False)
    groups = GroupSummarySerializer(many=True)


class CurrentUserPatchSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        initial = getattr(self, "initial_data", {}) or {}
        allowed = {"email", "first_name", "last_name"}
        present = set(initial.keys())
        forbidden = present.difference(allowed)
        if forbidden:
            raise serializers.ValidationError(
                api_error_payload(
                    code=ErrorCode.UNSAFE_FIELD,
                    message="This endpoint only supports self-profile fields.",
                    detail=f"Unsupported field(s): {', '.join(sorted(forbidden))}.",
                    hint="Use only: email, first_name, last_name.",
                )
            )
        return super().validate(attrs)


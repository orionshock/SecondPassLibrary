from rest_framework import serializers

from core.errors import ErrorCode, api_error_payload

from .models import UserProfile
from core.errors import ErrorCode, api_error_payload


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ["id", "role", "external_subject_id", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class CurrentUserSerializer(serializers.Serializer):
    class GroupSummarySerializer(serializers.Serializer):
        id = serializers.UUIDField()
        name = serializers.CharField()
        slug = serializers.SlugField()
        discoverability = serializers.ChoiceField(choices=["listed", "unlisted"])
        membership_role = serializers.ChoiceField(choices=["reader", "curator"])
        is_public_group = serializers.BooleanField()

    username = serializers.CharField()
    email = serializers.EmailField(allow_blank=True)
    profile_id = serializers.UUIDField()
    role = serializers.CharField()
    is_owner = serializers.BooleanField()
    capabilities = serializers.DictField(child=serializers.BooleanField())
    groups = GroupSummarySerializer(many=True)
    curated_group_ids = serializers.ListField(child=serializers.UUIDField())


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


class ManagedUserSerializer(serializers.Serializer):
    class ManagedUserGroupSummarySerializer(serializers.Serializer):
        id = serializers.UUIDField()
        name = serializers.CharField()
        slug = serializers.SlugField()
        discoverability = serializers.ChoiceField(choices=["listed", "unlisted"])
        membership_role = serializers.ChoiceField(choices=["reader", "curator"])
        is_public_group = serializers.BooleanField()

    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField(allow_blank=True)
    first_name = serializers.CharField(allow_blank=True)
    last_name = serializers.CharField(allow_blank=True)
    is_active = serializers.BooleanField()
    date_joined = serializers.DateTimeField()
    last_login = serializers.DateTimeField(allow_null=True)
    is_owner = serializers.BooleanField()
    profile_id = serializers.UUIDField(allow_null=True)
    role = serializers.CharField(allow_blank=True)
    groups = ManagedUserGroupSummarySerializer(many=True)


class ManagedUserPatchSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)
    role = serializers.ChoiceField(
        required=False,
        choices=[
            UserProfile.ROLE_MANAGER,
            UserProfile.ROLE_LIBRARIAN,
            UserProfile.ROLE_READER,
        ],
    )

    def validate(self, attrs):
        initial = getattr(self, "initial_data", {}) or {}
        forbidden = {"password", "user_permissions", "groups", "is_superuser", "is_staff", "username"}
        present = forbidden.intersection(set(initial.keys()))
        if present:
            raise serializers.ValidationError(
                api_error_payload(
                    code=ErrorCode.UNSAFE_FIELD,
                    message="This endpoint only supports profile-safe fields.",
                    detail=f"Unsupported field(s): {', '.join(sorted(present))}.",
                    hint="Use only: email, first_name, last_name, is_active, role.",
                )
            )
        return super().validate(attrs)

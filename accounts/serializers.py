from django.contrib.auth import get_user_model
from rest_framework import serializers

from core.errors import ErrorCode, api_error_payload

from .models import UserProfile


User = get_user_model()


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
        membership_id = serializers.UUIDField()
        id = serializers.UUIDField()
        name = serializers.CharField()
        slug = serializers.SlugField()
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


class ManagedUserCreateSerializer(serializers.Serializer):
    username = serializers.CharField()
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    first_name = serializers.CharField(required=False, allow_blank=True, default="")
    last_name = serializers.CharField(required=False, allow_blank=True, default="")
    role = serializers.ChoiceField(
        required=False,
        default=UserProfile.ROLE_READER,
        choices=[
            UserProfile.ROLE_MANAGER,
            UserProfile.ROLE_LIBRARIAN,
            UserProfile.ROLE_READER,
        ],
    )
    is_active = serializers.BooleanField(required=False, default=True)

    def validate_username(self, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Username is required.")
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with that username already exists.")
        return value

    def validate(self, attrs):
        initial = getattr(self, "initial_data", {}) or {}

        forbidden_explicit = {"password", "password1", "password2"}
        present = set(initial.keys())
        present_forbidden = forbidden_explicit.intersection(present)
        if present_forbidden:
            raise serializers.ValidationError(
                api_error_payload(
                    code=ErrorCode.UNSAFE_FIELD,
                    message="Password fields are not accepted.",
                    detail=f"Unsupported field(s): {', '.join(sorted(present_forbidden))}.",
                    hint="Omit password fields; the system generates a temporary password.",
                )
            )

        allowed = {"username", "email", "first_name", "last_name", "role", "is_active"}
        forbidden = present.difference(allowed)
        if forbidden:
            raise serializers.ValidationError(
                api_error_payload(
                    code=ErrorCode.UNSAFE_FIELD,
                    message="This endpoint only supports safe user fields.",
                    detail=f"Unsupported field(s): {', '.join(sorted(forbidden))}.",
                    hint="Use only: username, email, first_name, last_name, role, is_active.",
                )
            )

        return super().validate(attrs)

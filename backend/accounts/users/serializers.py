from django.contrib.auth import get_user_model
from rest_framework import serializers

from accounts.models import UserProfile
from core.errors import ErrorCode, api_error_payload


User = get_user_model()


class ManagedUserSerializer(serializers.Serializer):
    class ManagedUserGroupSummarySerializer(serializers.Serializer):
        id = serializers.UUIDField()
        name = serializers.CharField()
        is_public_group = serializers.BooleanField()
        is_curator = serializers.BooleanField()

    profile_id = serializers.UUIDField()
    username = serializers.CharField()
    email = serializers.EmailField(allow_blank=True)
    first_name = serializers.CharField(allow_blank=True)
    last_name = serializers.CharField(allow_blank=True)
    is_active = serializers.BooleanField()
    date_joined = serializers.DateTimeField()
    last_login = serializers.DateTimeField(allow_null=True)
    is_owner = serializers.BooleanField()
    role = serializers.CharField(allow_blank=True)
    must_change_password = serializers.BooleanField()
    groups = ManagedUserGroupSummarySerializer(many=True)


class UserChoiceSerializer(serializers.Serializer):
    profile_id = serializers.UUIDField(source="profile.id", read_only=True)
    username = serializers.CharField(read_only=True)


class UserChoiceQuerySerializer(serializers.Serializer):
    q = serializers.CharField(required=False, allow_blank=True, max_length=150)
    exclude_group = serializers.UUIDField(required=False)


class ManagedUserListQuerySerializer(serializers.Serializer):
    q = serializers.CharField(required=False, allow_blank=True, max_length=255)
    role = serializers.ChoiceField(
        required=False,
        allow_blank=True,
        choices=["owner", "manager", "librarian", "reader", "curator"],
    )
    is_active = serializers.ChoiceField(
        required=False,
        allow_blank=True,
        choices=["true", "false"],
    )
    ordering = serializers.ChoiceField(
        required=False,
        allow_blank=True,
        choices=[
            "username",
            "-username",
            "name",
            "-name",
            "role",
            "-role",
            "is_active",
            "-is_active",
        ],
    )

    def validate_q(self, value: str) -> str:
        return value.strip()

    def validate_role(self, value: str) -> str:
        if value == "curator" and not self.context.get("advanced_groups_enabled", False):
            raise serializers.ValidationError("Curator filtering is unavailable in simple mode.")
        return value


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
    must_change_password = serializers.BooleanField(required=False)

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


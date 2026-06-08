from typing import Any, cast

from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from core import policies
from core.errors import ErrorCode, api_error_payload

from .models import (
    BookGroupAssignment,
    LibraryGroup,
    LibraryGroupMembership,
    is_public_group,
)

class LibraryGroupSerializer(serializers.ModelSerializer):
    is_public_group = serializers.SerializerMethodField(read_only=True)
    membership_role = serializers.SerializerMethodField(read_only=True)

    def get_is_public_group(self, obj: LibraryGroup) -> bool:
        return is_public_group(obj)

    def get_membership_role(self, obj: LibraryGroup) -> str | None:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user is None or getattr(user, "is_anonymous", False):
            return None

        cache = getattr(obj, "_prefetched_objects_cache", {})
        if "memberships" in cache:
            membership = cast(Any, obj).memberships.all().first()
            return membership.role if membership is not None else None

        role = (
            LibraryGroupMembership.objects.filter(group=obj, user=user)
            .values_list("role", flat=True)
            .first()
        )
        return cast(str | None, role)

    class Meta:
        model = LibraryGroup
        fields = [
            "id",
            "name",
            "description",
            "is_public_group",
            "membership_role",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class LibraryGroupCreateSerializer(serializers.Serializer):
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True)

    def validate_name(self, value):
        v = (value or "").strip()
        if not v:
            raise serializers.ValidationError("This field is required.")
        if len(v) > 255:
            raise serializers.ValidationError("Name is too long.")
        return v

    def validate_description(self, value):
        return (value or "").strip()


class LibraryGroupPresentationUpdateSerializer(serializers.ModelSerializer):
    """
    Presentation-only update serializer.

    Allowed fields:
    - description

    Identity fields are rejected if present in the request payload.
    """

    class Meta:
        model = LibraryGroup
        fields = ["description"]

    def validate(self, attrs):
        initial = getattr(self, "initial_data", {}) or {}
        if "name" in initial or "slug" in initial:
            raise serializers.ValidationError(
                api_error_payload(
                    code=ErrorCode.GROUP_IDENTITY_IMMUTABLE,
                    message="Group identity fields cannot be updated via this endpoint.",
                    detail="Only 'description' can be updated.",
                    hint="Use PATCH with only 'description'.",
                )
            )
        if "discoverability" in initial:
            raise serializers.ValidationError(
                api_error_payload(
                    code=ErrorCode.UNSAFE_FIELD,
                    message="This endpoint only supports group description updates.",
                    detail="Unsupported field: discoverability.",
                    hint="Use PATCH with only 'description'.",
                )
            )
        return super().validate(attrs)

    def update(self, instance: LibraryGroup, validated_data: dict[str, Any]):
        request = self.context.get("request")
        user = getattr(request, "user", None)

        if "description" in validated_data:
            if not policies.can_edit_group_description(user=user, group=instance):
                raise PermissionDenied("Not allowed.")
            instance.description = validated_data["description"]

        instance.save(update_fields=["description", "updated_at"])
        return instance


class BookGroupAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookGroupAssignment
        fields = ["id", "book", "group", "added_by", "created_at", "updated_at"]
        read_only_fields = fields


class LibraryGroupMembershipSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField(allow_blank=True)
    role = serializers.ChoiceField(choices=[LibraryGroupMembership.ROLE_READER, LibraryGroupMembership.ROLE_CURATOR])
    is_owner = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class LibraryGroupMembershipCreateSerializer(serializers.Serializer):
    user = serializers.IntegerField()
    role = serializers.ChoiceField(
        required=False,
        choices=[LibraryGroupMembership.ROLE_READER, LibraryGroupMembership.ROLE_CURATOR],
        default=LibraryGroupMembership.ROLE_READER,
    )


class LibraryGroupMembershipPatchSerializer(serializers.Serializer):
    role = serializers.ChoiceField(
        required=True,
        choices=[LibraryGroupMembership.ROLE_READER, LibraryGroupMembership.ROLE_CURATOR],
    )

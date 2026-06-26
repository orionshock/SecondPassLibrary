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
    is_curator = serializers.SerializerMethodField(read_only=True)
    capabilities = serializers.SerializerMethodField(read_only=True)

    def get_is_public_group(self, obj: LibraryGroup) -> bool:
        return is_public_group(obj)

    def get_is_curator(self, obj: LibraryGroup) -> bool:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user is None or getattr(user, "is_anonymous", False):
            return False

        cache = getattr(obj, "_prefetched_objects_cache", {})
        if "memberships" in cache:
            membership = cast(Any, obj).memberships.all().first()
            return bool(membership.is_curator) if membership is not None else False

        return bool(
            LibraryGroupMembership.objects.filter(group=obj, user=user)
            .values_list("is_curator", flat=True)
            .first()
        )

    def get_capabilities(self, obj: LibraryGroup) -> dict[str, bool]:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user is None or getattr(user, "is_anonymous", False):
            return {
                "can_edit_description": False,
                "can_manage_books": False,
                "can_create_shelf": False,
                "can_manage_members": False,
                "can_manage_identity": False,
                "can_delete": False,
            }

        from shelves import policies as shelf_policies
        from shelves.models import Shelf

        return {
            "can_edit_description": policies.can_edit_group_description(user=user, group=obj),
            "can_manage_books": policies.can_manage_group_books(user=user, group=obj),
            "can_create_shelf": shelf_policies.can_create_shelf(
                user=user,
                owner_type=Shelf.OWNER_TYPE_GROUP,
                owner_group=obj,
            ),
            "can_manage_members": policies.can_manage_group_membership(user=user, group=obj),
            "can_manage_identity": policies.can_manage_group_identity(user=user, group=obj),
            "can_delete": policies.can_delete_library_group(user, group=obj),
        }

    class Meta:
        model = LibraryGroup
        fields = [
            "id",
            "name",
            "description",
            "is_public_group",
            "is_curator",
            "capabilities",
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
    is_owner = serializers.BooleanField()
    is_curator = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class LibraryGroupMembershipCreateSerializer(serializers.Serializer):
    user = serializers.IntegerField()
    is_curator = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        initial = getattr(self, "initial_data", {}) or {}
        if "role" in initial:
            raise serializers.ValidationError(
                {"role": "Membership role is not supported. Use is_curator."}
            )
        return super().validate(attrs)


class LibraryGroupMembershipPatchSerializer(serializers.Serializer):
    is_curator = serializers.BooleanField(required=True)

    def validate(self, attrs):
        initial = getattr(self, "initial_data", {}) or {}
        if "role" in initial:
            raise serializers.ValidationError(
                {"role": "Membership role is not supported. Use is_curator."}
            )
        return super().validate(attrs)

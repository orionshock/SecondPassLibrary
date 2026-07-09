from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers

from accounts.models import UserProfile
from library.models import LibraryGroupMembership


class LibraryGroupMembershipSerializer(serializers.ModelSerializer):
    user_id = serializers.SerializerMethodField(read_only=True)
    user_display = serializers.SerializerMethodField(read_only=True)
    role = serializers.SerializerMethodField(read_only=True)
    group_id = serializers.UUIDField(source="group.id", read_only=True)

    def get_user_id(self, obj: LibraryGroupMembership):
        return obj.user.profile.id

    def get_user_display(self, obj: LibraryGroupMembership) -> str:
        display = obj.user.get_full_name().strip()
        return display or obj.user.get_username()

    def get_role(self, obj: LibraryGroupMembership) -> str:
        return obj.user.profile.role

    class Meta:
        model = LibraryGroupMembership
        fields = ["id", "user_id", "user_display", "role", "is_curator", "group_id"]
        read_only_fields = fields


class _RejectUnknownFieldsMixin:
    def to_internal_value(self, data):
        if isinstance(data, dict):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError(
                    {field: "Unknown field." for field in sorted(unknown)}
                )
        return super().to_internal_value(data)


class MembershipCreateSerializer(_RejectUnknownFieldsMixin, serializers.Serializer):
    user_id = serializers.UUIDField(required=True)
    role = serializers.ChoiceField(choices=UserProfile.ROLE_CHOICES, required=False)
    is_curator = serializers.BooleanField(required=False, default=False)

    def validate_user_id(self, value):
        User = get_user_model()
        try:
            profile = UserProfile.objects.select_related("user").get(pk=value)
        except UserProfile.DoesNotExist as exc:
            raise serializers.ValidationError("Unknown user.") from exc
        if not User.objects.filter(pk=profile.user_id).exists():
            raise serializers.ValidationError("Unknown user.")
        return value


class MembershipPatchSerializer(_RejectUnknownFieldsMixin, serializers.Serializer):
    role = serializers.ChoiceField(choices=UserProfile.ROLE_CHOICES, required=False)
    is_curator = serializers.BooleanField(required=False)

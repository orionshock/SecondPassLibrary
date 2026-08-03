from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers

from accounts.models import UserProfile
from accounts.user_payloads import compact_user_payload
from library.models import LibraryGroupMembership


class LibraryGroupMembershipSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField(read_only=True)

    def get_user(self, obj: LibraryGroupMembership):
        return compact_user_payload(obj.user)

    class Meta:
        model = LibraryGroupMembership
        fields = ["user", "is_curator", "created_at", "updated_at"]
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
    is_curator = serializers.BooleanField(required=False)

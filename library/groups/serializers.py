from __future__ import annotations

from rest_framework import serializers

from library.groups.public_group import is_public_group
from library.models import LibraryGroup


class LibraryGroupSerializer(serializers.ModelSerializer):
    is_public_group = serializers.SerializerMethodField(read_only=True)

    def get_is_public_group(self, obj: LibraryGroup) -> bool:
        return is_public_group(obj)

    class Meta:
        model = LibraryGroup
        fields = ["id", "name", "description", "is_public_group"]
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


class LibraryGroupCreateSerializer(_RejectUnknownFieldsMixin, serializers.Serializer):
    name = serializers.CharField(allow_blank=False, trim_whitespace=True)
    description = serializers.CharField(required=False, allow_blank=True)


class LibraryGroupPatchSerializer(_RejectUnknownFieldsMixin, serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=False, trim_whitespace=True)
    description = serializers.CharField(required=False, allow_blank=True)

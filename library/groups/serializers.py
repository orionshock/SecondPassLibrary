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

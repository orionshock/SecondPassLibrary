from __future__ import annotations

from rest_framework import serializers

from library.models import BookGroupAssignment


class BookGroupAssignmentSerializer(serializers.ModelSerializer):
    group_id = serializers.UUIDField(source="group.id", read_only=True)
    book_id = serializers.UUIDField(source="book.id", read_only=True)

    class Meta:
        model = BookGroupAssignment
        fields = ["id", "group_id", "book_id"]
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


class BookGroupAssignmentCreateSerializer(_RejectUnknownFieldsMixin, serializers.Serializer):
    book_id = serializers.UUIDField(required=True)

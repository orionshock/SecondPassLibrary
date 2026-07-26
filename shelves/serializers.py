from __future__ import annotations

from typing import Any, cast

from rest_framework import serializers

from accounts.models import UserClientSession
from accounts.user_payloads import compact_user_payload
from library.groups.public_group import is_public_group
from library.catalog.serializers import (
    BookListSerializer,
    BookPreviewSerializer,
    RejectUnknownFieldsMixin,
)

from .models import Shelf, ShelfItem
from .services import can_edit_shelf


def _request_can_edit_shelf(*, request, shelf: Shelf) -> bool:
    user = getattr(request, "user", None)
    if user is None:
        return False
    if isinstance(getattr(request, "auth", None), UserClientSession):
        if shelf.owner_type != Shelf.OWNER_TYPE_USER:
            return False
        return getattr(shelf, "owner_user_id", None) == getattr(user, "id", None)
    return can_edit_shelf(user=user, shelf=shelf)


class ShelfSerializer(serializers.ModelSerializer):
    owner_user = serializers.SerializerMethodField(read_only=True)
    owner_group = serializers.SerializerMethodField(read_only=True)
    created_by = serializers.SerializerMethodField(read_only=True)
    item_count = serializers.IntegerField(read_only=True)
    matched_item_id = serializers.UUIDField(read_only=True, allow_null=True, required=False)
    can_edit = serializers.SerializerMethodField(read_only=True)
    preview_books = serializers.SerializerMethodField(read_only=True)

    def get_owner_user(self, obj: Shelf) -> dict[str, Any] | None:
        user = obj.owner_user
        if user is None:
            return None
        return compact_user_payload(user)

    def get_owner_group(self, obj: Shelf) -> dict[str, Any] | None:
        group = obj.owner_group
        if group is None:
            return None
        return {"id": group.id, "name": group.name, "is_public_group": is_public_group(group)}

    def get_created_by(self, obj: Shelf) -> dict[str, Any] | None:
        user = obj.created_by
        if user is None:
            return None
        return compact_user_payload(user)

    def get_can_edit(self, obj: Shelf) -> bool:
        request = self.context.get("request")
        if request is None:
            return False
        return _request_can_edit_shelf(request=request, shelf=obj)

    def get_preview_books(self, obj: Shelf) -> list[dict[str, Any]]:
        books = getattr(obj, "_preview_books", [])
        return cast(
            list[dict[str, Any]],
            BookPreviewSerializer(
                books,
                many=True,
                context=self.context,
            ).data,
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self.context.get("include_preview_books", False):
            data.pop("preview_books", None)
        return data

    class Meta:
        model = Shelf
        fields = [
            "id",
            "name",
            "description",
            "owner_type",
            "owner_user",
            "owner_group",
            "visibility",
            "item_count",
            "matched_item_id",
            "can_edit",
            "preview_books",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ShelfCreateSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    owner_type = serializers.ChoiceField(choices=[Shelf.OWNER_TYPE_USER, Shelf.OWNER_TYPE_GROUP])
    owner_group = serializers.UUIDField(required=False, allow_null=True)
    visibility = serializers.ChoiceField(
        choices=[Shelf.VISIBILITY_PRIVATE, Shelf.VISIBILITY_LISTED],
        required=False,
        default=Shelf.VISIBILITY_PRIVATE,
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs.get("owner_type") == Shelf.OWNER_TYPE_GROUP and not attrs.get(
            "owner_group"
        ):
            raise serializers.ValidationError(
                {"owner_group": "This field is required for group-owned shelves."}
            )
        return attrs


class ShelfPatchSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    visibility = serializers.ChoiceField(
        choices=[Shelf.VISIBILITY_PRIVATE, Shelf.VISIBILITY_LISTED],
        required=False,
    )


class ShelfItemSerializer(serializers.ModelSerializer):
    book = BookListSerializer(read_only=True)
    added_by = serializers.SerializerMethodField(read_only=True)

    def get_added_by(self, obj: ShelfItem) -> dict[str, Any] | None:
        user = obj.added_by
        if user is None:
            return None
        return compact_user_payload(user)

    class Meta:
        model = ShelfItem
        fields = [
            "id",
            "shelf",
            "book",
            "position",
            "added_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ShelfItemCreateSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    book = serializers.UUIDField()
    position = serializers.IntegerField(required=False, allow_null=True)


class ShelfItemPatchSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    position = serializers.IntegerField(required=False)
    move = serializers.ChoiceField(choices=["up", "down"], required=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if ("position" in attrs) == ("move" in attrs):
            raise serializers.ValidationError("Provide exactly one of position or move.")
        return attrs

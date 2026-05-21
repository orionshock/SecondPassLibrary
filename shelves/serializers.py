from __future__ import annotations

from typing import Any, cast

from django.contrib.auth import get_user_model
from rest_framework import serializers

from library.models import Book, LibraryGroup, is_public_group
from library.serializers import AuthorSummarySerializer, SeriesSummarySerializer
from accounts.models import UserClientSession

from .models import Shelf, ShelfItem
from .policies import can_edit_shelf


User = get_user_model()


class ShelfOwnerGroupSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    is_public_group = serializers.BooleanField()


class ShelfOwnerUserSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()


class ShelfSerializer(serializers.ModelSerializer):
    owner_user = serializers.SerializerMethodField(read_only=True)
    owner_group = serializers.SerializerMethodField(read_only=True)
    created_by = serializers.SerializerMethodField(read_only=True)
    item_count = serializers.IntegerField(read_only=True)
    matched_item_id = serializers.UUIDField(read_only=True, allow_null=True, required=False)
    can_edit = serializers.SerializerMethodField(read_only=True)

    def get_owner_user(self, obj: Shelf) -> dict[str, Any] | None:
        user = obj.owner_user
        if user is None:
            return None
        return {"id": cast(int, user.pk), "username": user.get_username()}

    def get_owner_group(self, obj: Shelf) -> dict[str, Any] | None:
        group = obj.owner_group
        if group is None:
            return None
        return {"id": group.id, "name": group.name, "is_public_group": is_public_group(group)}

    def get_created_by(self, obj: Shelf) -> dict[str, Any] | None:
        user = obj.created_by
        if user is None:
            return None
        return {"id": cast(int, user.pk), "username": user.get_username()}

    def get_can_edit(self, obj: Shelf) -> bool:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user is None:
            return False
        # Client API bearer tokens may only edit personal shelves owned by the token user.
        if isinstance(getattr(request, "auth", None), UserClientSession):
            return (
                obj.owner_type == Shelf.OWNER_TYPE_USER
                and getattr(obj, "owner_user_id", None) == getattr(user, "id", None)
            )
        return can_edit_shelf(user=user, shelf=obj)

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
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ShelfCreateSerializer(serializers.Serializer):
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True)
    owner_type = serializers.ChoiceField(choices=[Shelf.OWNER_TYPE_USER, Shelf.OWNER_TYPE_GROUP])
    owner_group = serializers.UUIDField(required=False, allow_null=True)
    visibility = serializers.ChoiceField(
        choices=[Shelf.VISIBILITY_PRIVATE, Shelf.VISIBILITY_LISTED],
        required=False,
        default=Shelf.VISIBILITY_PRIVATE,
    )


class ShelfPatchSerializer(serializers.Serializer):
    name = serializers.CharField(required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    visibility = serializers.ChoiceField(
        choices=[Shelf.VISIBILITY_PRIVATE, Shelf.VISIBILITY_LISTED],
        required=False,
    )


class BookSummarySerializer(serializers.ModelSerializer):
    authors = AuthorSummarySerializer(many=True, read_only=True)
    series = SeriesSummarySerializer(read_only=True, allow_null=True)
    has_file = serializers.SerializerMethodField(read_only=True)
    cover_url = serializers.SerializerMethodField(read_only=True)

    def get_has_file(self, obj: Book) -> bool:
        return bool(getattr(obj, "file", None))

    def get_cover_url(self, obj: Book) -> str | None:
        cover = getattr(obj, "cover_file", None)
        if not cover:
            return None
        try:
            url = cover.url
        except Exception:
            return None

        request = self.context.get("request")
        if request is not None:
            return request.build_absolute_uri(url)
        return url

    class Meta:
        model = Book
        fields = ["id", "title", "authors", "series", "has_file", "cover_url"]
        read_only_fields = fields


class ShelfItemSerializer(serializers.ModelSerializer):
    book = BookSummarySerializer(read_only=True)
    added_by = serializers.SerializerMethodField(read_only=True)

    def get_added_by(self, obj: ShelfItem) -> dict[str, Any] | None:
        user = obj.added_by
        if user is None:
            return None
        return {"id": cast(int, user.pk), "username": user.get_username()}

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


class ShelfItemCreateSerializer(serializers.Serializer):
    book = serializers.UUIDField()
    position = serializers.IntegerField(required=False, allow_null=True)


class ShelfItemPatchSerializer(serializers.Serializer):
    position = serializers.IntegerField(required=True)

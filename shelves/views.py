from __future__ import annotations

from typing import Any, cast

from django.db.models import Q
from django.http import Http404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from core import policies as core_policies
from library.models import Book, LibraryGroup, LibraryGroupMembership

from .models import Shelf, ShelfItem
from .serializers import (
    ShelfCreateSerializer,
    ShelfItemCreateSerializer,
    ShelfItemPatchSerializer,
    ShelfItemSerializer,
    ShelfPatchSerializer,
    ShelfSerializer,
)
from .services import (
    add_book_to_shelf,
    create_shelf,
    delete_shelf,
    remove_book_from_shelf,
    update_shelf,
    visible_shelf_items_for_user,
)


class ShelfViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Shelf.objects.all()
    permission_classes = [IsAuthenticated]
    ordering = ["name", "created_at"]

    def get_serializer_class(self):
        if self.action == "create":
            return ShelfCreateSerializer
        if self.action in {"partial_update"}:
            return ShelfPatchSerializer
        if self.action in {"items", "add_item"}:
            return ShelfItemCreateSerializer
        if self.action in {"patch_item"}:
            return ShelfItemPatchSerializer
        return ShelfSerializer

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset().select_related("owner_user", "owner_group", "created_by")

        if core_policies.can_manage_library(user):
            visible_qs = qs
        else:
            visible_qs = qs.filter(
                Q(owner_type=Shelf.OWNER_TYPE_USER, owner_user=user)
                | Q(owner_type=Shelf.OWNER_TYPE_USER, visibility=Shelf.VISIBILITY_LISTED)
                | Q(
                    owner_type=Shelf.OWNER_TYPE_GROUP,
                    owner_group__memberships__user=user,
                )
            ).distinct()

        owner_group = self.request.query_params.get("owner_group")
        if owner_group:
            visible_qs = visible_qs.filter(owner_type=Shelf.OWNER_TYPE_GROUP, owner_group_id=owner_group)

        book = self.request.query_params.get("book")
        if book:
            visible_qs = visible_qs.filter(items__book_id=book).distinct()

        return visible_qs

    def get_object(self):
        obj = super().get_object()
        from .policies import can_view_shelf

        if not can_view_shelf(user=self.request.user, shelf=obj):
            raise Http404()
        return obj

    def create(self, request, *args, **kwargs):
        serializer = cast(Any, self.get_serializer(data=request.data or {}))
        serializer.is_valid(raise_exception=True)
        data = cast(dict[str, Any], serializer.validated_data)

        owner_type = data["owner_type"]
        owner_group = None
        if owner_type == Shelf.OWNER_TYPE_GROUP:
            group_id = data.get("owner_group")
            if not group_id:
                raise PermissionDenied("Missing owner_group.")
            try:
                owner_group = LibraryGroup.objects.get(pk=group_id)
            except LibraryGroup.DoesNotExist as exc:
                raise Http404() from exc

        shelf = create_shelf(
            request.user,
            name=data["name"],
            description=data.get("description") or "",
            owner_type=owner_type,
            owner_user=request.user if owner_type == Shelf.OWNER_TYPE_USER else None,
            owner_group=owner_group,
            visibility=data.get("visibility") or Shelf.VISIBILITY_PRIVATE,
        )
        out = ShelfSerializer(shelf, context={"request": request})
        return Response(out.data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        shelf = self.get_object()
        serializer = cast(Any, self.get_serializer(data=request.data or {}, partial=True))
        serializer.is_valid(raise_exception=True)
        data = cast(dict[str, Any], serializer.validated_data)
        updated = update_shelf(request.user, shelf, **data)
        out = ShelfSerializer(updated, context={"request": request})
        return Response(out.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        shelf = self.get_object()
        delete_shelf(request.user, shelf)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get", "post"], url_path="items")
    def items(self, request, *args, **kwargs):
        shelf = self.get_object()

        if request.method == "GET":
            qs = visible_shelf_items_for_user(request.user, shelf)
            page = self.paginate_queryset(qs)
            items = list(page) if page is not None else list(qs)
            out = ShelfItemSerializer(items, many=True, context={"request": request})
            if page is not None:
                return self.get_paginated_response(out.data)
            return Response(out.data)

        serializer = cast(Any, ShelfItemCreateSerializer(data=request.data or {}))
        serializer.is_valid(raise_exception=True)
        data = cast(dict[str, Any], serializer.validated_data)
        try:
            book = Book.objects.get(pk=data["book"])
        except Book.DoesNotExist as exc:
            raise Http404() from exc

        item = add_book_to_shelf(
            request.user,
            shelf=shelf,
            book=book,
            position=data.get("position"),
        )
        out = ShelfItemSerializer(item, context={"request": request})
        return Response(out.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch", "delete"], url_path=r"items/(?P<item_id>[^/.]+)")
    def item_detail(self, request, item_id: str | None = None, *args, **kwargs):
        shelf = self.get_object()
        if item_id is None:
            raise Http404()

        try:
            item = ShelfItem.objects.select_related("book").get(pk=item_id, shelf=shelf)
        except ShelfItem.DoesNotExist as exc:
            raise Http404() from exc

        if request.method == "DELETE":
            remove_book_from_shelf(request.user, shelf=shelf, book_or_item=item)
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = cast(Any, ShelfItemPatchSerializer(data=request.data or {}))
        serializer.is_valid(raise_exception=True)
        position = cast(int, serializer.validated_data["position"])

        from .policies import can_edit_shelf

        if not can_edit_shelf(user=request.user, shelf=shelf):
            raise PermissionDenied("Not allowed.")
        item.position = position
        item.save(update_fields=["position", "updated_at"])
        out = ShelfItemSerializer(item, context={"request": request})
        return Response(out.data, status=status.HTTP_200_OK)

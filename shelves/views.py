from __future__ import annotations

from typing import Any, NoReturn, cast

from django.db.models import Count, Exists, F, OuterRef, Window
from django.db.models.functions import RowNumber
from django.http import Http404
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import mixins, status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers

from library import policies as library_policies
from library.models import Book, BookGroupAssignment, LibraryGroup
from library.preview_books import (
    PREVIEW_BOOK_LIMIT,
    attach_preview_books_from_queryset,
    include_preview_books,
)
from accounts.authentication import ClientBearerAuthentication
from accounts.models import UserClientSession

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
    move_shelf_item,
    remove_book_from_shelf,
    set_shelf_item_position,
    update_shelf,
    visible_shelf_items_for_user,
)
from .policies import can_edit_shelf_for_request, visible_shelf_filter
from .querysets import build_visible_shelf_list_queryset


def _attach_shelf_preview_books(*, shelves, user) -> None:
    shelf_list = list(shelves)
    shelf_ids = [shelf.id for shelf in shelf_list]
    if not shelf_ids:
        return

    queryset = ShelfItem.objects.select_related("book").filter(shelf_id__in=shelf_ids)
    if not library_policies.can_manage_library(user):
        visible_assignment = BookGroupAssignment.objects.filter(
            book_id=OuterRef("book_id"),
            group__memberships__user=user,
        )
        queryset = queryset.filter(Exists(visible_assignment))

    queryset = (
        queryset.annotate(
            _preview_parent_id=F("shelf_id"),
            _preview_rank=Window(
                expression=RowNumber(),
                partition_by=[F("shelf_id")],
                order_by=[
                    F("position").asc(),
                    F("id").asc(),
                    F("book_id").asc(),
                ],
            ),
        )
        .filter(_preview_rank__lte=PREVIEW_BOOK_LIMIT)
        .order_by("_preview_parent_id", "_preview_rank")
    )

    attach_preview_books_from_queryset(
        parents=shelf_list,
        queryset=queryset,
        get_book=lambda item: item.book,
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
    authentication_classes = [
        SessionAuthentication,
        ClientBearerAuthentication,
    ]
    permission_classes = [IsAuthenticated]
    ordering = ["name", "created_at"]

    # Map of DRF action -> allowed HTTP methods for client bearer auth.
    client_bearer_allowed: dict[str, set[str]] = {
        "list": {"GET"},
        "retrieve": {"GET"},
        "create": {"POST"},
        "partial_update": {"PATCH"},
        "update": {"PUT"},
        "destroy": {"DELETE"},
        "items": {"GET", "POST"},
        "item_detail": {"PATCH", "DELETE"},
    }

    def initial(self, request, *args, **kwargs):
        # Pylance can't reliably infer the `super()` type for a mixin; at runtime
        # this is always a DRF view/viewset that implements `initial`.
        cast(Any, super()).initial(request, *args, **kwargs)
        if isinstance(getattr(request, "auth", None), UserClientSession):
            action = getattr(self, "action", "") or ""
            allowed = self.client_bearer_allowed.get(str(action), set())
            if request.method.upper() not in allowed:
                raise PermissionDenied("Client API tokens are not allowed for this endpoint/action.")

    def _request_write_allowed_for_shelf(self, *, request, shelf: Shelf) -> bool:
        return can_edit_shelf_for_request(request=request, shelf=shelf)

    def _write_denied_message(self, *, request, items: bool = False) -> str:
        if isinstance(getattr(request, "auth", None), UserClientSession):
            if items:
                return "Client API tokens may only modify items in personal shelves you own."
            return "Client API tokens may only edit personal shelves you own."
        return "Not allowed."

    def get_serializer_class(self):
        if self.action == "create":
            return ShelfCreateSerializer
        if self.action in {"partial_update", "update"}:
            return ShelfPatchSerializer
        return ShelfSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["include_preview_books"] = include_preview_books(self.request)
        return context

    def _raise_drf_validation(self, exc: DjangoValidationError) -> NoReturn:
        raise serializers.ValidationError(
            exc.message_dict if hasattr(exc, "message_dict") else exc.messages
        )

    def get_queryset(self):
        user = self.request.user
        qs = (
            super()
            .get_queryset()
            .select_related("owner_user", "owner_group", "created_by")
            .annotate(item_count=Count("items"))
        )

        if self.action == "list":
            visible_qs = build_visible_shelf_list_queryset(
                queryset=qs,
                user=user,
                query_params=self.request.query_params,
            )
        else:
            visible_qs = qs.filter(visible_shelf_filter(user)).distinct()
        return visible_qs.order_by("name", "created_at")

    def get_object(self):
        obj = super().get_object()
        from .policies import can_view_shelf

        if not can_view_shelf(user=self.request.user, shelf=obj):
            raise Http404()
        return obj

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        shelves = list(page) if page is not None else list(queryset)

        if include_preview_books(request):
            _attach_shelf_preview_books(shelves=shelves, user=request.user)

        serializer = self.get_serializer(shelves, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if include_preview_books(request):
            _attach_shelf_preview_books(shelves=[instance], user=request.user)

        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = cast(Any, self.get_serializer(data=request.data or {}))
        serializer.is_valid(raise_exception=True)
        data = cast(dict[str, Any], serializer.validated_data)

        owner_type = data["owner_type"]
        if isinstance(getattr(request, "auth", None), UserClientSession):
            # Client API bearer tokens may only create personal shelves.
            if owner_type != Shelf.OWNER_TYPE_USER:
                raise PermissionDenied("Client API tokens may only create personal shelves.")
        owner_group = None
        if owner_type == Shelf.OWNER_TYPE_GROUP:
            group_id = data.get("owner_group")
            if not group_id:
                raise PermissionDenied("Missing owner_group.")
            try:
                owner_group = LibraryGroup.objects.get(pk=group_id)
            except LibraryGroup.DoesNotExist as exc:
                raise Http404() from exc

        try:
            shelf = create_shelf(
                request.user,
                name=data["name"],
                description=data.get("description") or "",
                owner_type=owner_type,
                owner_user=request.user if owner_type == Shelf.OWNER_TYPE_USER else None,
                owner_group=owner_group,
                visibility=data.get("visibility") or Shelf.VISIBILITY_PRIVATE,
            )
        except DjangoValidationError as exc:
            self._raise_drf_validation(exc)
        out = ShelfSerializer(shelf, context={"request": request})
        return Response(out.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        # Treat PUT the same as PATCH for this API (partial updates only).
        return self.partial_update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        shelf = self.get_object()
        if not self._request_write_allowed_for_shelf(request=request, shelf=shelf):
            raise PermissionDenied(self._write_denied_message(request=request))
        serializer = cast(Any, self.get_serializer(data=request.data or {}, partial=True))
        serializer.is_valid(raise_exception=True)
        data = cast(dict[str, Any], serializer.validated_data)
        try:
            updated = update_shelf(request.user, shelf, **data)
        except DjangoValidationError as exc:
            self._raise_drf_validation(exc)
        out = ShelfSerializer(updated, context={"request": request})
        return Response(out.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        shelf = self.get_object()
        if not self._request_write_allowed_for_shelf(request=request, shelf=shelf):
            raise PermissionDenied(self._write_denied_message(request=request))
        delete_shelf(request.user, shelf)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _items_get(self, request, shelf: Shelf) -> Response:
        qs = visible_shelf_items_for_user(request.user, shelf)
        page = self.paginate_queryset(qs)
        items = list(page) if page is not None else list(qs)
        out = ShelfItemSerializer(items, many=True, context={"request": request})
        if page is not None:
            return self.get_paginated_response(out.data)
        return Response(out.data)

    def _items_post(self, request, shelf: Shelf) -> Response:
        if not self._request_write_allowed_for_shelf(request=request, shelf=shelf):
            raise PermissionDenied(self._write_denied_message(request=request, items=True))

        serializer = cast(Any, ShelfItemCreateSerializer(data=request.data or {}))
        serializer.is_valid(raise_exception=True)
        data = cast(dict[str, Any], serializer.validated_data)
        try:
            book = Book.objects.get(pk=data["book"])
        except Book.DoesNotExist as exc:
            raise Http404() from exc

        try:
            item = add_book_to_shelf(
                request.user,
                shelf=shelf,
                book=book,
                position=data.get("position"),
            )
        except DjangoValidationError as exc:
            self._raise_drf_validation(exc)
        out = ShelfItemSerializer(item, context={"request": request})
        return Response(out.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get", "post"], url_path="items")
    def items(self, request, *args, **kwargs):
        shelf = self.get_object()

        if request.method == "GET":
            return self._items_get(request, shelf)

        return self._items_post(request, shelf)

    def _item_delete(self, request, shelf: Shelf, item: ShelfItem) -> Response:
        if not self._request_write_allowed_for_shelf(request=request, shelf=shelf):
            raise PermissionDenied(self._write_denied_message(request=request, items=True))
        remove_book_from_shelf(request.user, shelf=shelf, book_or_item=item)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _item_patch(self, request, shelf: Shelf, item: ShelfItem) -> Response:
        if not self._request_write_allowed_for_shelf(request=request, shelf=shelf):
            raise PermissionDenied(self._write_denied_message(request=request, items=True))

        serializer = cast(Any, ShelfItemPatchSerializer(data=request.data or {}))
        serializer.is_valid(raise_exception=True)
        data = cast(dict[str, Any], serializer.validated_data)
        try:
            if "move" in data:
                item = move_shelf_item(
                    request.user,
                    shelf=shelf,
                    item=item,
                    direction=cast(str, data["move"]),
                )
            else:
                item = set_shelf_item_position(
                    request.user,
                    shelf=shelf,
                    item=item,
                    position=cast(int, data["position"]),
                )
        except DjangoValidationError as exc:
            self._raise_drf_validation(exc)
        out = ShelfItemSerializer(item, context={"request": request})
        return Response(out.data, status=status.HTTP_200_OK)

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
            return self._item_delete(request, shelf, item)

        return self._item_patch(request, shelf, item)

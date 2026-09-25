from __future__ import annotations

from functools import cached_property
from typing import Any, NoReturn, cast

from django.http import Http404
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import mixins, status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers

from library.catalog.preview_books import parse_preview_book_limit
from library.catalog.ordering import parse_ordering_param
from accounts.client_sessions.authentication import ClientBearerAuthentication
from accounts.models import UserClientSession
from library.queries import visible_groups_for_user

from .models import Shelf, ShelfItem
from .serializers import (
    ShelfCreateSerializer,
    ShelfEditorItemSerializer,
    ShelfItemCreateSerializer,
    ShelfItemPatchSerializer,
    ShelfItemSerializer,
    ShelfPatchSerializer,
    ShelfSerializer,
)
from .item_queries import (
    attach_shelf_preview_books,
    editor_shelf_items,
    visible_shelf_item_ids,
    visible_shelf_items_for_user,
)
from .item_services import (
    add_book_to_shelf,
    move_shelf_item,
    remove_book_from_shelf,
    set_shelf_item_position,
)
from .policies import books_available_to_shelf_editor, request_can_edit_shelf
from .services import (
    create_shelf,
    delete_shelf,
    update_shelf,
)
from .querysets import (
    apply_shelf_item_ordering,
    apply_shelf_ordering,
    build_visible_shelf_list_queryset,
    filter_readable_shelves,
    with_visible_item_count,
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
            if (request.method or "").upper() not in allowed:
                raise PermissionDenied("Client API tokens are not allowed for this endpoint/action.")

    def _request_write_allowed_for_shelf(self, *, request, shelf: Shelf) -> bool:
        return request_can_edit_shelf(request=request, shelf=shelf)

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
        context["include_preview_books"] = self.preview_book_limit is not None
        return context

    @cached_property
    def preview_book_limit(self) -> int | None:
        if self.action not in {"list", "retrieve"}:
            return None
        return parse_preview_book_limit(self.request)

    def _raise_drf_validation(self, exc: DjangoValidationError) -> NoReturn:
        raise serializers.ValidationError(
            exc.message_dict if hasattr(exc, "message_dict") else exc.messages
        )

    def get_queryset(self):
        user = self.request.user
        qs = (
            super()
            .get_queryset()
            .select_related(
                "owner_user__profile",
                "owner_group",
                "created_by__profile",
            )
        )

        if self.action == "list":
            visible_qs = build_visible_shelf_list_queryset(
                queryset=qs,
                user=user,
                query_params=self.request.query_params,
            )
            visible_qs = with_visible_item_count(visible_qs, user=user)
            ordering = parse_ordering_param(
                self.request,
                allowed={"name", "-name", "item_count", "-item_count"},
                default="name",
            )
            return apply_shelf_ordering(visible_qs, ordering)

        visible_qs = filter_readable_shelves(
            with_visible_item_count(qs, user=user),
            user=user,
        )
        return visible_qs.order_by("name", "id")

    def get_object(self):
        return super().get_object()

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        shelves = list(page) if page is not None else list(queryset)

        if self.preview_book_limit is not None:
            attach_shelf_preview_books(
                shelves=shelves,
                user=request.user,
                limit=self.preview_book_limit,
            )

        serializer = self.get_serializer(shelves, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if self.preview_book_limit is not None:
            attach_shelf_preview_books(
                shelves=[instance],
                user=request.user,
                limit=self.preview_book_limit,
            )

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
            owner_group = visible_groups_for_user(request.user).filter(pk=group_id).first()
            if owner_group is None:
                raise Http404()

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
        shelf = self.get_queryset().get(pk=shelf.pk)
        out = ShelfSerializer(shelf, context={"request": request})
        return Response(out.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        raise MethodNotAllowed("PUT")

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
        item_view = str(request.query_params.get("view") or "").strip().lower()
        if item_view not in {"", "edit"}:
            raise serializers.ValidationError(
                {"view": "Must be edit when supplied."}
            )

        if item_view == "edit":
            # Keep editor projection assembly here unless it gains another consumer
            # or starts owning domain rules. Policies/queries own visibility, services
            # own mutation invariants, and DRF owns pagination/response shaping.
            if not self._request_write_allowed_for_shelf(request=request, shelf=shelf):
                raise PermissionDenied(self._write_denied_message(request=request, items=True))
            parse_ordering_param(
                request,
                allowed={"position"},
                default="position",
            )
            qs = editor_shelf_items(shelf=shelf)
            # Editor reads retain unavailable personal Shelf items as placeholders;
            # locked mutation services separately recheck current eligibility.
            visible_ids = visible_shelf_item_ids(user=request.user, shelf=shelf)
            total_count = qs.count()
            visible_count = len(visible_ids)
            page = self.paginate_queryset(qs)
            items = list(page) if page is not None else list(qs)
            out = ShelfEditorItemSerializer(
                items,
                many=True,
                context={
                    "request": request,
                    "visible_item_ids": visible_ids,
                },
            )
            if page is not None:
                response = self.get_paginated_response(out.data)
                response.data["visible_item_count"] = visible_count
                response.data["unavailable_item_count"] = total_count - visible_count
                return response
            return Response(
                {
                    "count": total_count,
                    "visible_item_count": visible_count,
                    "unavailable_item_count": total_count - visible_count,
                    "results": out.data,
                }
            )

        qs = visible_shelf_items_for_user(request.user, shelf)
        ordering = parse_ordering_param(
            request,
            allowed={"position", "-position", "title", "-title", "author", "-author"},
            default="position",
        )
        qs = apply_shelf_item_ordering(qs, ordering)
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
        book = books_available_to_shelf_editor(user=request.user, shelf=shelf).filter(
            pk=data["book"]
        ).first()
        if book is None:
            raise Http404()

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
        if item.pk not in visible_shelf_item_ids(user=request.user, shelf=shelf):
            raise Http404()

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
        except (ShelfItem.DoesNotExist, DjangoValidationError, ValueError) as exc:
            raise Http404() from exc

        if request.method == "DELETE":
            return self._item_delete(request, shelf, item)

        return self._item_patch(request, shelf, item)

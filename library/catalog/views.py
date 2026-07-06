from django.db import IntegrityError, transaction
from django.db.models import Count, Exists, F, OuterRef, Prefetch, Q, Window
from django.db.models.functions import Random, RowNumber
from django.http import Http404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from library import policies
from core.errors import ErrorCode, api_error_response

from .serializers import (
    AuthorSerializer,
    BookIdentifierSerializer,
    BookIdentifierWriteSerializer,
    BookSerializer,
    SeriesSerializer,
)
from .ordering import (
    apply_book_ordering,
    apply_taxonomy_ordering,
    parse_ordering_param,
)
from ..models import Author, Book, BookGroupAssignment, BookIdentifier, Series
from .preview_books import (
    PREVIEW_BOOK_LIMIT,
    attach_preview_books_from_queryset,
    include_preview_books,
)
from ..view_mixins import ClientBearerReadOnlyMixin


def _visible_book_preview_queryset(user):
    queryset = Book.objects.only("id", "title", "cover_file")
    if policies.can_manage_library(user):
        return queryset

    visible_assignment = BookGroupAssignment.objects.filter(
        book_id=OuterRef("pk"),
        group__memberships__user=user,
    )
    return queryset.filter(Exists(visible_assignment))


def _attach_author_preview_books(*, authors, user) -> None:
    author_list = list(authors)
    author_ids = [author.id for author in author_list]
    if not author_ids:
        return

    queryset = (
        _visible_book_preview_queryset(user)
        .filter(authors__id__in=author_ids)
        .annotate(
            _preview_parent_id=F("authors__id"),
            _preview_rank=Window(
                expression=RowNumber(),
                partition_by=[F("authors__id")],
                order_by=[Random(), F("id").asc()],
            ),
        )
        .filter(_preview_rank__lte=PREVIEW_BOOK_LIMIT)
        .order_by("_preview_parent_id", "_preview_rank")
    )

    attach_preview_books_from_queryset(
        parents=author_list,
        queryset=queryset,
        get_book=lambda book: book,
    )


def _attach_series_preview_books(*, series, user) -> None:
    series_list = list(series)
    series_ids = [item.id for item in series_list]
    if not series_ids:
        return

    queryset = (
        _visible_book_preview_queryset(user)
        .filter(series_id__in=series_ids)
        .annotate(
            _preview_parent_id=F("series_id"),
            _preview_rank=Window(
                expression=RowNumber(),
                partition_by=[F("series_id")],
                order_by=[
                    F("series_index").asc(nulls_last=True),
                    F("id").asc(),
                ],
            ),
        )
        .filter(_preview_rank__lte=PREVIEW_BOOK_LIMIT)
        .order_by("_preview_parent_id", "_preview_rank")
    )

    attach_preview_books_from_queryset(
        parents=series_list,
        queryset=queryset,
        get_book=lambda book: book,
    )


class AuthorViewSet(ClientBearerReadOnlyMixin, viewsets.ModelViewSet):
    client_bearer_allowed = {"list": {"GET"}, "retrieve": {"GET"}}
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["include_preview_books"] = include_preview_books(self.request)
        return context

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if policies.can_manage_library(user):
            return queryset.annotate(book_count=Count("books", distinct=True))

        visible_books = Q(books__group_assignments__group__memberships__user=user)
        return (
            queryset.filter(visible_books)
            .annotate(book_count=Count("books", filter=visible_books, distinct=True))
            .distinct()
        )

    def perform_create(self, serializer):
        if not policies.can_manage_library(self.request.user):
            raise PermissionDenied("Not allowed.")
        serializer.save()

    def perform_update(self, serializer):
        if not policies.can_manage_library(self.request.user):
            raise PermissionDenied("Not allowed.")
        serializer.save()

    def perform_destroy(self, instance):
        if not policies.can_manage_library(self.request.user):
            raise PermissionDenied("Not allowed.")
        instance.delete()

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        ordering = parse_ordering_param(
            request,
            allowed={"name", "-book_count"},
            default="name",
        )
        queryset = apply_taxonomy_ordering(queryset, ordering)
        page = self.paginate_queryset(queryset)
        authors = list(page) if page is not None else list(queryset)

        if include_preview_books(request):
            _attach_author_preview_books(authors=authors, user=request.user)

        serializer = self.get_serializer(authors, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if include_preview_books(request):
            _attach_author_preview_books(authors=[instance], user=request.user)

        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class SeriesViewSet(ClientBearerReadOnlyMixin, viewsets.ModelViewSet):
    client_bearer_allowed = {"list": {"GET"}, "retrieve": {"GET"}}
    queryset = Series.objects.all()
    serializer_class = SeriesSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["include_preview_books"] = include_preview_books(self.request)
        return context

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if policies.can_manage_library(user):
            return queryset.annotate(book_count=Count("books", distinct=True))

        visible_books = Q(books__group_assignments__group__memberships__user=user)
        return (
            queryset.filter(visible_books)
            .annotate(book_count=Count("books", filter=visible_books, distinct=True))
            .distinct()
        )

    def perform_create(self, serializer):
        if not policies.can_manage_library(self.request.user):
            raise PermissionDenied("Not allowed.")
        serializer.save()

    def perform_update(self, serializer):
        if not policies.can_manage_library(self.request.user):
            raise PermissionDenied("Not allowed.")
        serializer.save()

    def perform_destroy(self, instance):
        if not policies.can_manage_library(self.request.user):
            raise PermissionDenied("Not allowed.")
        instance.delete()

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        ordering = parse_ordering_param(
            request,
            allowed={"name", "-book_count"},
            default="name",
        )
        queryset = apply_taxonomy_ordering(queryset, ordering)
        page = self.paginate_queryset(queryset)
        series = list(page) if page is not None else list(queryset)

        if include_preview_books(request):
            _attach_series_preview_books(series=series, user=request.user)

        serializer = self.get_serializer(series, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if include_preview_books(request):
            _attach_series_preview_books(series=[instance], user=request.user)

        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class BookViewSet(ClientBearerReadOnlyMixin, viewsets.ModelViewSet):
    client_bearer_allowed = {"list": {"GET"}, "retrieve": {"GET"}}
    queryset = (
        Book.objects.select_related("series", "file")
        .prefetch_related(
            Prefetch("authors", queryset=Author.objects.order_by("name")),
            Prefetch(
                "identifiers",
                queryset=BookIdentifier.objects.order_by("scheme", "value"),
            ),
            Prefetch(
                "group_assignments",
                queryset=BookGroupAssignment.objects.select_related("group").order_by(
                    "group__name", "group__id"
                ),
            ),
        )
    )
    serializer_class = BookSerializer
    permission_classes = [IsAuthenticated]

    def _filter_visible_books(self, queryset):
        if not policies.can_manage_library(self.request.user):
            queryset = queryset.filter(
                group_assignments__group__memberships__user=self.request.user
            )
        return queryset

    def _apply_search_filter(self, queryset):
        q = (self.request.query_params.get("q") or "").strip()
        if q:
            return queryset.filter(
                Q(title__icontains=q)
                | Q(subtitle__icontains=q)
                | Q(authors__name__icontains=q)
                | Q(series__name__icontains=q)
                | Q(isbn__icontains=q)
                | Q(identifiers__value__icontains=q)
            )
        return queryset

    def _apply_book_filters(self, queryset):
        author_id = (self.request.query_params.get("author") or "").strip()
        if author_id:
            queryset = queryset.filter(authors__id=author_id)

        series_id = (self.request.query_params.get("series") or "").strip()
        if series_id:
            queryset = queryset.filter(series__id=series_id)

        language = (self.request.query_params.get("language") or "").strip()
        if language:
            queryset = queryset.filter(language__iexact=language)

        has_files = (self.request.query_params.get("has_files") or "").strip().lower()
        if has_files in {"true", "1", "yes", "y", "on"}:
            queryset = queryset.filter(file__isnull=False)
        elif has_files in {"false", "0", "no", "n", "off"}:
            queryset = queryset.filter(file__isnull=True)

        return queryset, series_id

    def _apply_book_list_ordering(self, queryset, *, series_id: str):
        allowed_ordering = {"title", "author", "series"}
        default_ordering = "title"
        if series_id:
            allowed_ordering.add("series_index")
            default_ordering = "series_index"

        ordering = parse_ordering_param(
            self.request,
            allowed=allowed_ordering,
            default=default_ordering,
        )
        return apply_book_ordering(queryset.distinct(), ordering)

    def get_queryset(self):
        queryset = self._filter_visible_books(super().get_queryset())
        queryset = self._apply_search_filter(queryset)
        queryset, series_id = self._apply_book_filters(queryset)
        return self._apply_book_list_ordering(queryset, series_id=series_id)

    def perform_create(self, serializer):
        # Books are file-backed and should be created via import only.
        raise PermissionDenied("Books can only be created via import.")

    def create(self, request, *args, **kwargs):
        # Explicit 405: this is not a supported API surface.
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def perform_update(self, serializer):
        if not policies.can_manage_library(self.request.user):
            raise PermissionDenied("Not allowed.")
        serializer.save()

    def perform_destroy(self, instance):
        # Book deletion is not supported through this API.
        raise PermissionDenied("Not allowed.")

    def destroy(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    @action(detail=True, methods=["get", "post"], url_path="identifiers")
    def identifiers(self, request, *args, **kwargs):
        book: Book = self.get_object()
        if request.method == "GET":
            qs = BookIdentifier.objects.filter(book=book).order_by("scheme", "value")
            serializer = BookIdentifierSerializer(qs, many=True)
            return Response(serializer.data)

        if not policies.can_manage_library(request.user):
            raise PermissionDenied("Not allowed.")

        create = BookIdentifierWriteSerializer(data=request.data or {})
        create.is_valid(raise_exception=True)
        data = create.validated_data

        try:
            with transaction.atomic():
                ident = BookIdentifier.objects.create(book=book, **data)
        except IntegrityError:
            return api_error_response(
                code=ErrorCode.INVALID_REQUEST,
                message="Duplicate identifier.",
                detail="An identifier with the same scheme and value already exists for this book.",
                hint="Use a different scheme/value or edit the existing identifier.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        serializer = BookIdentifierSerializer(ident)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"identifiers/(?P<identifier_id>[^/.]+)",
    )
    def identifier_detail(self, request, identifier_id: str | None = None, *args, **kwargs):
        book: Book = self.get_object()
        if identifier_id is None:
            raise Http404()

        try:
            ident = BookIdentifier.objects.get(pk=identifier_id, book=book)
        except BookIdentifier.DoesNotExist as exc:
            raise Http404() from exc

        if request.method == "DELETE":
            if not policies.can_manage_library(request.user):
                raise PermissionDenied("Not allowed.")
            ident.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        if not policies.can_manage_library(request.user):
            raise PermissionDenied("Not allowed.")

        patch = BookIdentifierWriteSerializer(instance=ident, data=request.data or {}, partial=True)
        patch.is_valid(raise_exception=True)
        data = patch.validated_data

        for k, v in data.items():
            setattr(ident, k, v)
        try:
            with transaction.atomic():
                ident.save()
        except IntegrityError:
            return api_error_response(
                code=ErrorCode.INVALID_REQUEST,
                message="Duplicate identifier.",
                detail="An identifier with the same scheme and value already exists for this book.",
                hint="Use a different scheme/value or edit the existing identifier.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        serializer = BookIdentifierSerializer(ident)
        return Response(serializer.data, status=status.HTTP_200_OK)

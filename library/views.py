from typing import Any, cast

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404
from django.db.models import Prefetch
from django.db.models import Count, Q
from django.db import IntegrityError
from django.db import transaction
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError

from rest_framework import mixins, viewsets
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response

from accounts.authentication import ClientBearerAuthentication
from accounts.models import UserClientSession

from .models import (
    Author,
    Book,
    BookFile,
    Series,
    BookIdentifier,
    LibraryGroup,
    LibraryGroupMembership,
    is_public_group,
    BookGroupAssignment,
)
from .catalog_serializers import (
    AuthorSerializer,
    BookFileSerializer,
    BookSerializer,
    BookIdentifierSerializer,
    BookIdentifierWriteSerializer,
    SeriesSerializer,
    ImportJobSerializer,
)
from .group_serializers import (
    LibraryGroupSerializer,
    LibraryGroupCreateSerializer,
    LibraryGroupPresentationUpdateSerializer,
    BookGroupAssignmentSerializer,
    LibraryGroupMembershipSerializer,
    LibraryGroupMembershipCreateSerializer,
    LibraryGroupMembershipPatchSerializer,
)
from .services import (
    generate_epub_download_filename,
    create_import_job_from_upload,
    process_import_job,
)
from .models import ImportJob
from .group_services import (
    add_book_to_group,
    ensure_book_public_assignment,
    get_public_group,
    remove_book_from_group,
    add_user_to_group,
    remove_user_from_group,
    update_user_group_membership,
    delete_library_group,
)
from core import policies
from core.errors import ErrorCode, api_error_response

User = get_user_model()


class ClientBearerReadOnlyMixin:
    """
    Allow Client API bearer tokens only for explicitly allowed read actions.

    Notes:
    - Session/basic auth continues to work normally.
    - If a request is authenticated via a client bearer token (request.auth is a
      UserClientSession), disallowed actions are rejected with 403.
    """

    authentication_classes = [
        SessionAuthentication,
        BasicAuthentication,
        ClientBearerAuthentication,
    ]

    # Map of DRF action -> allowed HTTP methods for client bearer auth.
    client_bearer_allowed: dict[str, set[str]] = {}

    def initial(self, request, *args, **kwargs):
        # Pylance can't reliably infer the `super()` type for a mixin; at runtime
        # this is always a DRF view/viewset that implements `initial`.
        cast(Any, super()).initial(request, *args, **kwargs)
        if isinstance(getattr(request, "auth", None), UserClientSession):
            action = getattr(self, "action", None)
            if not action:
                # Fallback for edge cases where DRF hasn't set `self.action` yet.
                ctx = getattr(request, "parser_context", None) or {}
                if isinstance(ctx, dict):
                    action = ctx.get("action") or ""
                else:
                    action = ""
            allowed = self.client_bearer_allowed.get(str(action), set())
            if request.method.upper() not in allowed:
                raise PermissionDenied("Client API tokens are read-only for this endpoint.")


class AuthorViewSet(ClientBearerReadOnlyMixin, viewsets.ModelViewSet):
    client_bearer_allowed = {"list": {"GET"}, "retrieve": {"GET"}}
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if policies.can_manage_library(user):
            return queryset.annotate(book_count=Count("books", distinct=True)).order_by("name")

        visible_books = Q(books__group_assignments__group__memberships__user=user)
        return (
            queryset.filter(visible_books)
            .annotate(book_count=Count("books", filter=visible_books, distinct=True))
            .distinct()
            .order_by("name")
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


class SeriesViewSet(ClientBearerReadOnlyMixin, viewsets.ModelViewSet):
    client_bearer_allowed = {"list": {"GET"}, "retrieve": {"GET"}}
    queryset = Series.objects.all()
    serializer_class = SeriesSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if policies.can_manage_library(user):
            return queryset.annotate(book_count=Count("books", distinct=True)).order_by("name")

        visible_books = Q(books__group_assignments__group__memberships__user=user)
        return (
            queryset.filter(visible_books)
            .annotate(book_count=Count("books", filter=visible_books, distinct=True))
            .distinct()
            .order_by("name")
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
    ordering_fields = ["title", "created_at", "updated_at", "published_date", "series_index"]
    ordering = ["title", "created_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        request = self.request

        if not policies.can_manage_library(request.user):
            queryset = queryset.filter(
                group_assignments__group__memberships__user=request.user
            )

        q = (request.query_params.get("q") or "").strip()
        if q:
            queryset = queryset.filter(
                Q(title__icontains=q)
                | Q(subtitle__icontains=q)
                | Q(authors__name__icontains=q)
                | Q(series__name__icontains=q)
                | Q(isbn__icontains=q)
                | Q(identifiers__value__icontains=q)
            )

        author_id = (request.query_params.get("author") or "").strip()
        if author_id:
            queryset = queryset.filter(authors__id=author_id)

        series_id = (request.query_params.get("series") or "").strip()
        if series_id:
            queryset = queryset.filter(series__id=series_id)

        language = (request.query_params.get("language") or "").strip()
        if language:
            queryset = queryset.filter(language__iexact=language)

        has_files = (request.query_params.get("has_files") or "").strip().lower()
        if has_files in {"true", "1", "yes", "y", "on"}:
            queryset = queryset.filter(file__isnull=False)
        elif has_files in {"false", "0", "no", "n", "off"}:
            queryset = queryset.filter(file__isnull=True)

        ordering = (request.query_params.get("ordering") or "").strip()
        if ordering:
            field = ordering.lstrip("-")
            if field in set(self.ordering_fields):
                queryset = queryset.order_by(ordering, "created_at")
        return queryset.distinct()

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


class BookFileViewSet(ClientBearerReadOnlyMixin, viewsets.ModelViewSet):
    client_bearer_allowed = {"list": {"GET"}, "retrieve": {"GET"}, "download": {"GET"}}
    queryset = (
        BookFile.objects.select_related("book", "book__series")
        .prefetch_related("book__authors")
        .all()
    )
    serializer_class = BookFileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        if policies.can_manage_library(self.request.user):
            return queryset
        return queryset.filter(book__group_assignments__group__memberships__user=self.request.user).distinct()

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

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, *args, **kwargs):
        book_file: BookFile = self.get_object()

        if not policies.can_download_book_file(user=request.user, book_file=book_file):
            raise PermissionDenied("Not allowed.")

        if not book_file.file:
            raise Http404("Stored file missing.")

        storage = book_file.file.storage
        name = book_file.file.name
        if not storage.exists(name):
            raise Http404("Stored file missing.")

        download_name = generate_epub_download_filename(book=book_file.book)
        file_handle = storage.open(name, "rb")
        return FileResponse(
            file_handle,
            as_attachment=True,
            filename=download_name,
            content_type="application/epub+zip",
        )


class ImportJobViewSet(
    ClientBearerReadOnlyMixin,
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    # Client bearer tokens should not be usable for imports (even read).
    client_bearer_allowed: dict[str, set[str]] = {}
    serializer_class = ImportJobSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        if not policies.can_manage_library(self.request.user):
            raise PermissionDenied("Not allowed.")
        return ImportJob.objects.prefetch_related("items").all()

    def create(self, request, *args, **kwargs):
        if not policies.can_import_books(request.user):
            raise PermissionDenied("Not allowed.")
        uploaded = request.FILES.get("file")
        if uploaded is None:
            return api_error_response(
                code=ErrorCode.MISSING_UPLOAD_FILE,
                message='Missing multipart upload field "file".',
                hint='Send a multipart/form-data request with a "file" field containing a .epub or .zip.',
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        try:
            job = create_import_job_from_upload(user=request.user, uploaded_file=uploaded)
            job = process_import_job(job=job)
        except ValueError as e:
            return api_error_response(
                code=ErrorCode.INVALID_UPLOAD_TYPE,
                message="Invalid upload type.",
                detail=str(e),
                hint="Upload must be a .epub or .zip file.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(job)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class LibraryGroupViewSet(
    ClientBearerReadOnlyMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    client_bearer_allowed = {"list": {"GET"}, "retrieve": {"GET"}, "books": {"GET"}}
    queryset = LibraryGroup.objects.all()
    permission_classes = [IsAuthenticated]
    ordering = ["name", "created_at"]

    def get_serializer_class(self):
        if self.action == "create":
            return LibraryGroupCreateSerializer
        if self.action == "partial_update":
            return LibraryGroupPresentationUpdateSerializer
        return LibraryGroupSerializer

    def get_queryset(self):
        queryset = super().get_queryset().order_by(*self.ordering)
        user = self.request.user

        membership_qs = LibraryGroupMembership.objects.filter(user=user)
        queryset = queryset.prefetch_related(Prefetch("memberships", queryset=membership_qs))

        if policies.can_manage_library(user):
            return queryset

        public = get_public_group()
        return queryset.filter(
            Q(id=public.id) | Q(memberships__user=user)
        ).distinct()

    def update(self, request, *args, **kwargs):
        # Disallow full PUT updates; only PATCH is supported for presentation fields.
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def create(self, request, *args, **kwargs):
        if not policies.can_create_library_group(request.user):
            raise PermissionDenied("Not allowed.")

        serializer = self.get_serializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        data = cast(dict[str, Any], serializer.validated_data)

        group = LibraryGroup.objects.create(
            name=data["name"],
            description=data.get("description") or "",
        )
        out = LibraryGroupSerializer(group, context={"request": request})
        return Response(out.data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        output = LibraryGroupSerializer(instance, context={"request": request})
        return Response(output.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        group: LibraryGroup = self.get_object()
        # delete_library_group handles Public protection and permission checks.
        try:
            delete_library_group(actor=request.user, group=group)
        except ValidationError as exc:
            raise DRFValidationError(detail={"detail": str(exc)}) from exc
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get", "post"], url_path="books")
    def books(self, request, *args, **kwargs):
        group: LibraryGroup = self.get_object()

        if request.method == "GET":
            if not policies.can_view_library_group(user=request.user, group=group):
                raise Http404()

            queryset = Book.objects.filter(group_assignments__group=group).distinct()
            if not policies.can_manage_library(request.user):
                accessible_ids = Book.objects.filter(
                    group_assignments__group__memberships__user=request.user
                ).values("id")
                queryset = queryset.filter(id__in=accessible_ids)

            page = self.paginate_queryset(queryset)
            serializer = BookSerializer(
                page if page is not None else queryset,
                many=True,
                context={"request": request},
            )
            if page is not None:
                return self.get_paginated_response(serializer.data)
            return Response(serializer.data)

        payload = request.data or {}
        book_id = payload.get("book")
        if not book_id:
            return api_error_response(
                code=ErrorCode.INVALID_REQUEST,
                message="Missing required field.",
                detail="Missing 'book'.",
                hint='POST JSON like {"book": "<book_id>"}',
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if policies.can_manage_library(request.user):
            book_qs = Book.objects.all()
        else:
            if is_public_group(group):
                raise PermissionDenied("Not allowed.")
            if not policies.can_curate_group(user=request.user, group=group):
                raise PermissionDenied("Not allowed.")
            book_qs = Book.objects.filter(
                group_assignments__group__memberships__user=request.user
            ).distinct()

        try:
            book = book_qs.get(pk=book_id)
        except Book.DoesNotExist as exc:
            raise Http404() from exc

        assignment = add_book_to_group(actor=request.user, book=book, group=group)
        serializer = BookGroupAssignmentSerializer(assignment, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"books/(?P<book_id>[^/.]+)")
    def remove_book(self, request, book_id: str | None = None, *args, **kwargs):
        group: LibraryGroup = self.get_object()
        if book_id is None:
            raise Http404()

        if policies.can_manage_library(request.user):
            book_qs = Book.objects.all()
        else:
            if is_public_group(group):
                raise PermissionDenied("Not allowed.")
            if not policies.can_curate_group(user=request.user, group=group):
                raise PermissionDenied("Not allowed.")
            book_qs = Book.objects.filter(group_assignments__group=group).distinct()

        try:
            book = book_qs.get(pk=book_id)
        except Book.DoesNotExist as exc:
            raise Http404() from exc

        remove_book_from_group(actor=request.user, book=book, group=group)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get", "post"], url_path="memberships")
    def memberships(self, request, *args, **kwargs):
        group: LibraryGroup = self.get_object()

        if request.method == "GET":
            # Read permission: allow group members (and Public viewers) to see the
            # membership list, while keeping membership mutation Manager/Owner-only.
            #
            # Do not expose membership lists for groups the user cannot view.
            if not policies.can_view_library_group(user=request.user, group=group):
                raise Http404()

            if policies.can_manage_library(request.user):
                pass
            elif is_public_group(group):
                pass
            elif LibraryGroupMembership.objects.filter(user=request.user, group=group).exists():
                pass
            else:
                raise Http404()

            qs = (
                LibraryGroupMembership.objects.select_related("user")
                .filter(group=group)
                .order_by("user__username", "id")
            )
            page = self.paginate_queryset(qs)
            memberships = list(page) if page is not None else list(qs)
            payload = []
            for membership in memberships:
                user = membership.user
                payload.append(
                    {
                        "id": membership.id,
                        "user_id": user.pk,
                        "username": user.get_username(),
                        "email": user.email or "",
                        "role": membership.role,
                        "is_owner": policies.is_owner(user),
                        "created_at": membership.created_at,
                        "updated_at": membership.updated_at,
                    }
                )
            serializer = LibraryGroupMembershipSerializer(payload, many=True)
            if page is not None:
                return self.get_paginated_response(serializer.data)
            return Response(serializer.data)

        if not policies.can_manage_group_membership(user=request.user, group=group):
            raise PermissionDenied("Not allowed.")

        create = LibraryGroupMembershipCreateSerializer(data=request.data or {})
        create.is_valid(raise_exception=True)
        data = create.validated_data

        user_id = data.get("user")
        role = data.get("role")
        try:
            target = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return api_error_response(
                code=ErrorCode.INVALID_REQUEST,
                message="User not found.",
                detail=f"No user with id={user_id}.",
                hint="Use a valid user id from /api/v1/accounts/users/.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            membership = add_user_to_group(
                actor=request.user, target_user=target, group=group, role=role
            )
        except ValidationError as exc:
            return api_error_response(
                code=ErrorCode.INVALID_REQUEST,
                message="Invalid membership request.",
                detail=str(exc),
                hint="Use role=reader|curator (curator only for non-Public groups).",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        user = membership.user
        payload = {
            "id": membership.id,
            "user_id": user.pk,
            "username": user.get_username(),
            "email": user.email or "",
            "role": membership.role,
            "is_owner": policies.is_owner(user),
            "created_at": membership.created_at,
            "updated_at": membership.updated_at,
        }
        serializer = LibraryGroupMembershipSerializer(payload)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"memberships/(?P<membership_id>[^/.]+)",
    )
    def membership_detail(
        self, request, membership_id: str | None = None, *args, **kwargs
    ):
        group: LibraryGroup = self.get_object()
        if not policies.can_manage_group_membership(user=request.user, group=group):
            raise PermissionDenied("Not allowed.")
        if membership_id is None:
            raise Http404()

        try:
            membership = LibraryGroupMembership.objects.select_related("user").get(
                pk=membership_id, group=group
            )
        except LibraryGroupMembership.DoesNotExist as exc:
            raise Http404() from exc

        if request.method == "DELETE":
            remove_user_from_group(actor=request.user, membership=membership)
            return Response(status=status.HTTP_204_NO_CONTENT)

        patch = LibraryGroupMembershipPatchSerializer(data=request.data or {})
        patch.is_valid(raise_exception=True)
        data = patch.validated_data

        try:
            membership = update_user_group_membership(
                actor=request.user, membership=membership, role=data["role"]
            )
        except ValidationError as exc:
            return api_error_response(
                code=ErrorCode.INVALID_REQUEST,
                message="Invalid membership update.",
                detail=str(exc),
                hint="Use role=reader|curator (curator only for non-Public groups).",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        user = membership.user
        payload = {
            "id": membership.id,
            "user_id": user.pk,
            "username": user.get_username(),
            "email": user.email or "",
            "role": membership.role,
            "is_owner": policies.is_owner(user),
            "created_at": membership.created_at,
            "updated_at": membership.updated_at,
        }
        serializer = LibraryGroupMembershipSerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)

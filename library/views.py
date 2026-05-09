from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404
from django.db.models import Prefetch
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied

from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response

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
from .serializers import (
    AuthorSerializer,
    BookFileSerializer,
    BookSerializer,
    SeriesSerializer,
    ImportJobSerializer,
    LibraryGroupSerializer,
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
    remove_book_from_group,
    add_user_to_group,
    remove_user_from_group,
    update_user_group_membership,
)
from core import policies
from core.errors import ErrorCode, api_error_response

User = get_user_model()


class AuthorViewSet(viewsets.ModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        if policies.can_manage_library(self.request.user):
            return queryset
        return queryset.filter(books__group_assignments__group__memberships__user=self.request.user).distinct()

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


class SeriesViewSet(viewsets.ModelViewSet):
    queryset = Series.objects.all()
    serializer_class = SeriesSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        if policies.can_manage_library(self.request.user):
            return queryset
        return queryset.filter(books__group_assignments__group__memberships__user=self.request.user).distinct()

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


class BookViewSet(viewsets.ModelViewSet):
    queryset = (
        Book.objects.select_related("series")
        .prefetch_related(
            Prefetch("authors", queryset=Author.objects.order_by("name")),
            Prefetch("files", queryset=BookFile.objects.order_by("created_at")),
            Prefetch(
                "identifiers",
                queryset=BookIdentifier.objects.order_by("scheme", "value"),
            ),
            Prefetch(
                "group_assignments",
                queryset=BookGroupAssignment.objects.select_related("group").order_by(
                    "group__name", "group__slug"
                ),
            ),
        )
    )
    serializer_class = BookSerializer
    permission_classes = [IsAuthenticated]
    ordering_fields = ["title", "created_at", "updated_at", "published_date"]
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
            queryset = queryset.filter(files__isnull=False)
        elif has_files in {"false", "0", "no", "n", "off"}:
            queryset = queryset.filter(files__isnull=True)

        ordering = (request.query_params.get("ordering") or "").strip()
        if ordering:
            field = ordering.lstrip("-")
            if field in set(self.ordering_fields):
                queryset = queryset.order_by(ordering, "created_at")
        return queryset.distinct()

    def perform_create(self, serializer):
        if not policies.can_manage_library(self.request.user):
            raise PermissionDenied("Not allowed.")
        book = serializer.save()
        ensure_book_public_assignment(book=book, added_by=self.request.user)

    def perform_update(self, serializer):
        if not policies.can_manage_library(self.request.user):
            raise PermissionDenied("Not allowed.")
        serializer.save()

    def perform_destroy(self, instance):
        if not policies.can_manage_library(self.request.user):
            raise PermissionDenied("Not allowed.")
        instance.delete()


class BookFileViewSet(viewsets.ModelViewSet):
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
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
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
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = LibraryGroup.objects.all()
    permission_classes = [IsAuthenticated]
    ordering = ["name", "created_at"]

    def get_serializer_class(self):
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

        return queryset.filter(
            Q(slug="public")
            | Q(discoverability=LibraryGroup.DISCOVERABILITY_LISTED)
            | Q(memberships__user=user)
        ).distinct()

    def update(self, request, *args, **kwargs):
        # Disallow full PUT updates; only PATCH is supported for presentation fields.
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        output = LibraryGroupSerializer(instance, context={"request": request})
        return Response(output.data, status=status.HTTP_200_OK)

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
        if not policies.can_manage_group_membership(user=request.user, group=group):
            raise PermissionDenied("Not allowed.")

        if request.method == "GET":
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

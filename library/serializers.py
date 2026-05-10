from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.reverse import reverse
from typing import Any, cast

from core import policies
from core.errors import ErrorCode, api_error_payload
from .models import (
    Author,
    Book,
    BookFile,
    Series,
    BookIdentifier,
    LibraryGroup,
    LibraryGroupMembership,
    BookGroupAssignment,
    is_public_group,
    ImportJob,
    ImportJobItem,
)


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Author
        fields = ["id", "name", "biography", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class AuthorSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Author
        fields = ["id", "name"]
        read_only_fields = fields


class SeriesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Series
        fields = ["id", "name", "summary", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class SeriesSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Series
        fields = ["id", "name"]
        read_only_fields = fields


class BookFileSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True, required=False)
    download_url = serializers.SerializerMethodField(read_only=True)

    def get_download_url(self, obj: BookFile) -> str:
        request = self.context.get("request")
        return reverse("library:bookfile-download", args=[obj.pk], request=request)

    class Meta:
        model = BookFile
        fields = [
            "id",
            "book",
            "file",
            "download_url",
            "format",
            "checksum",
            "file_size",
            "source_filename",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class BookIdentifierSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookIdentifier
        fields = ["scheme", "value", "source", "is_primary"]
        read_only_fields = fields


class BookFileSummarySerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField(read_only=True)
    checksum_short = serializers.SerializerMethodField(read_only=True)

    def get_download_url(self, obj: BookFile) -> str:
        request = self.context.get("request")
        return reverse("library:bookfile-download", args=[obj.pk], request=request)

    def get_checksum_short(self, obj: BookFile) -> str:
        return obj.checksum_short() if obj.checksum else ""

    class Meta:
        model = BookFile
        fields = ["id", "format", "file_size", "download_url", "checksum_short"]
        read_only_fields = fields


class BookSerializer(serializers.ModelSerializer):
    authors = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Author.objects.all()
    )
    series = serializers.PrimaryKeyRelatedField(
        queryset=Series.objects.all(), required=False, allow_null=True
    )
    file = serializers.SerializerMethodField(read_only=True)
    identifiers = serializers.SerializerMethodField(read_only=True)
    groups = serializers.SerializerMethodField(read_only=True)

    def get_identifiers(self, obj: Book):
        identifiers = cast(Any, obj).identifiers.all()
        return BookIdentifierSerializer(identifiers, many=True).data

    def get_groups(self, obj: Book):
        request = self.context.get("request")
        user = getattr(request, "user", None)

        # group_assignments may be prefetched (preferred), but works without it.
        try:
            assignments = list(cast(Any, obj).group_assignments.all())
        except Exception:
            assignments = []
        groups = [a.group for a in assignments if getattr(a, "group", None) is not None]

        if user is None or getattr(user, "is_anonymous", False):
            return []

        # Managers/Librarians/Owner can see full group assignment context.
        if policies.can_manage_library(user):
            visible_groups = groups
        else:
            # Readers/Curators only see groups they can view (public, listed, or member).
            visible_groups = [g for g in groups if policies.can_view_library_group(user=user, group=g)]

        visible_groups = sorted(visible_groups, key=lambda g: (g.name, g.slug))
        return [
            {
                "id": g.id,
                "name": g.name,
                "slug": g.slug,
                "is_public_group": is_public_group(g),
            }
            for g in visible_groups
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["authors"] = AuthorSummarySerializer(
            cast(Any, instance).authors.all(), many=True, context=self.context
        ).data
        data["series"] = (
            SeriesSummarySerializer(instance.series, context=self.context).data
            if instance.series is not None
            else None
        )
        return data

    def get_file(self, obj: Book):
        try:
            book_file = cast(Any, obj).file
        except Exception:
            book_file = None
        if book_file is None:
            return None
        return BookFileSummarySerializer(book_file, context=self.context).data

    class Meta:
        model = Book
        fields = [
            "id",
            "title",
            "subtitle",
            "summary",
            "publisher",
            "language",
            "published_date",
            "isbn",
            "subjects",
            "authors",
            "series",
            "series_index",
            "identifiers",
            "groups",
            "file",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def create(self, validated_data):
        authors = validated_data.pop("authors", [])
        book = Book.objects.create(**validated_data)
        book.authors.set(authors)
        return book

    def update(self, instance, validated_data):
        authors = validated_data.pop("authors", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if authors is not None:
            instance.authors.set(authors)
        instance.save()

        return instance


class ImportJobItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportJobItem
        fields = [
            "id",
            "status",
            "source_name",
            "book",
            "book_file",
            "message",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ImportJobSerializer(serializers.ModelSerializer):
    items = ImportJobItemSerializer(many=True, read_only=True)

    class Meta:
        model = ImportJob
        fields = [
            "id",
            "status",
            "source_type",
            "source_filename",
            "total_found",
            "imported_count",
            "duplicate_count",
            "failed_count",
            "message",
            "items",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class LibraryGroupSerializer(serializers.ModelSerializer):
    is_public_group = serializers.SerializerMethodField(read_only=True)
    membership_role = serializers.SerializerMethodField(read_only=True)

    def get_is_public_group(self, obj: LibraryGroup) -> bool:
        return is_public_group(obj)

    def get_membership_role(self, obj: LibraryGroup) -> str | None:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user is None or getattr(user, "is_anonymous", False):
            return None

        cache = getattr(obj, "_prefetched_objects_cache", {})
        if "memberships" in cache:
            membership = cast(Any, obj).memberships.all().first()
            return membership.role if membership is not None else None

        role = (
            LibraryGroupMembership.objects.filter(group=obj, user=user)
            .values_list("role", flat=True)
            .first()
        )
        return cast(str | None, role)

    class Meta:
        model = LibraryGroup
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "is_public_group",
            "membership_role",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class LibraryGroupPresentationUpdateSerializer(serializers.ModelSerializer):
    """
    Presentation-only update serializer.

    Allowed fields:
    - description

    Identity fields (name/slug) are rejected if present in the request payload.
    """

    class Meta:
        model = LibraryGroup
        fields = ["description"]

    def validate(self, attrs):
        initial = getattr(self, "initial_data", {}) or {}
        if "name" in initial or "slug" in initial:
            raise serializers.ValidationError(
                api_error_payload(
                    code=ErrorCode.GROUP_IDENTITY_IMMUTABLE,
                    message="Group identity fields cannot be updated via this endpoint.",
                    detail="Only 'description' can be updated.",
                    hint="Use PATCH with only 'description'.",
                )
            )
        if "discoverability" in initial:
            raise serializers.ValidationError(
                api_error_payload(
                    code=ErrorCode.UNSAFE_FIELD,
                    message="This endpoint only supports group description updates.",
                    detail="Unsupported field: discoverability.",
                    hint="Use PATCH with only 'description'.",
                )
            )
        return super().validate(attrs)

    def update(self, instance: LibraryGroup, validated_data: dict[str, Any]):
        request = self.context.get("request")
        user = getattr(request, "user", None)

        if "description" in validated_data:
            if not policies.can_edit_group_description(user=user, group=instance):
                raise PermissionDenied("Not allowed.")
            instance.description = validated_data["description"]

        instance.save(update_fields=["description", "updated_at"])
        return instance


class BookGroupAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookGroupAssignment
        fields = ["id", "book", "group", "added_by", "created_at", "updated_at"]
        read_only_fields = fields


class LibraryGroupMembershipSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField(allow_blank=True)
    role = serializers.ChoiceField(choices=[LibraryGroupMembership.ROLE_READER, LibraryGroupMembership.ROLE_CURATOR])
    is_owner = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class LibraryGroupMembershipCreateSerializer(serializers.Serializer):
    user = serializers.IntegerField()
    role = serializers.ChoiceField(
        required=False,
        choices=[LibraryGroupMembership.ROLE_READER, LibraryGroupMembership.ROLE_CURATOR],
        default=LibraryGroupMembership.ROLE_READER,
    )


class LibraryGroupMembershipPatchSerializer(serializers.Serializer):
    role = serializers.ChoiceField(
        required=True,
        choices=[LibraryGroupMembership.ROLE_READER, LibraryGroupMembership.ROLE_CURATOR],
    )

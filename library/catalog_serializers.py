from decimal import Decimal
from typing import Any, cast

from rest_framework import serializers
from rest_framework.reverse import reverse

from core import policies

from .models import (
    Author,
    Book,
    BookFile,
    BookIdentifier,
    ImportJob,
    ImportJobItem,
    Series,
    is_public_group,
)

class AuthorSerializer(serializers.ModelSerializer):
    book_count = serializers.IntegerField(read_only=True)
    preview_books = serializers.SerializerMethodField(read_only=True)

    def get_preview_books(self, obj: Author):
        preview_books = getattr(obj, "_preview_books", [])
        return BookPreviewSerializer(
            preview_books, many=True, context=self.context
        ).data

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self.context.get("include_preview_books", False):
            data.pop("preview_books", None)
        return data

    class Meta:
        model = Author
        fields = [
            "id",
            "name",
            "biography",
            "book_count",
            "preview_books",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class AuthorSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Author
        fields = ["id", "name"]
        read_only_fields = fields


class SeriesSerializer(serializers.ModelSerializer):
    book_count = serializers.IntegerField(read_only=True)
    preview_books = serializers.SerializerMethodField(read_only=True)

    def get_preview_books(self, obj: Series):
        preview_books = getattr(obj, "_preview_books", [])
        return BookPreviewSerializer(
            preview_books, many=True, context=self.context
        ).data

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self.context.get("include_preview_books", False):
            data.pop("preview_books", None)
        return data

    class Meta:
        model = Series
        fields = [
            "id",
            "name",
            "summary",
            "book_count",
            "preview_books",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SeriesSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Series
        fields = ["id", "name"]
        read_only_fields = fields


def book_cover_url(obj: Book, request=None) -> str | None:
    cover = getattr(obj, "cover_file", None)
    if not cover:
        return None
    try:
        url = cover.url
    except Exception:
        return None

    if request is not None:
        return request.build_absolute_uri(url)
    return url


class BookPreviewSerializer(serializers.ModelSerializer):
    cover_url = serializers.SerializerMethodField(read_only=True)

    def get_cover_url(self, obj: Book) -> str | None:
        return book_cover_url(obj, request=self.context.get("request"))

    class Meta:
        model = Book
        fields = ["id", "title", "cover_url"]
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
        fields = ["id", "scheme", "value", "source", "is_primary", "created_at", "updated_at"]
        read_only_fields = fields


class BookIdentifierWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookIdentifier
        fields = ["scheme", "value", "source", "is_primary"]

    def validate_scheme(self, value):
        v = (value or "").strip()
        if not v:
            raise serializers.ValidationError("This field is required.")
        return v

    def validate_value(self, value):
        v = (value or "").strip()
        if not v:
            raise serializers.ValidationError("This field is required.")
        return v

    def validate_source(self, value):
        return (value or "").strip()


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
    # These are optional in the product and API. Accept `null` from clients and
    # coerce to empty string for storage (model fields are blank=True, null=False).
    summary = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    isbn = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    series = serializers.PrimaryKeyRelatedField(
        queryset=Series.objects.all(), required=False, allow_null=True
    )
    file = serializers.SerializerMethodField(read_only=True)
    identifiers = serializers.SerializerMethodField(read_only=True)
    groups = serializers.SerializerMethodField(read_only=True)
    cover_url = serializers.SerializerMethodField(read_only=True)

    def validate(self, attrs: dict[str, Any]):
        if "summary" in attrs and attrs["summary"] is None:
            attrs["summary"] = ""
        if "isbn" in attrs and attrs["isbn"] is None:
            attrs["isbn"] = ""
        return super().validate(attrs)

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

        visible_groups = sorted(visible_groups, key=lambda g: (g.name, str(g.id)))
        return [
            {
                "id": g.id,
                "name": g.name,
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

    def get_cover_url(self, obj: Book) -> str | None:
        return book_cover_url(obj, request=self.context.get("request"))

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
            "cover_url",
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

    def validate_series_index(self, value):
        if value is None:
            return None

        # Accept integers or a single decimal place (e.g. 5 or 5.1).
        if not isinstance(value, Decimal):
            try:
                value = Decimal(str(value))
            except Exception as exc:
                raise serializers.ValidationError("Must be a number.") from exc

        if value < 0:
            raise serializers.ValidationError("Must be >= 0.")

        # Enforce at most one decimal place; reject 5.12, 5.123, etc.
        exp: int = int(value.as_tuple().exponent)
        if exp < -1:
            raise serializers.ValidationError("Must have at most one decimal place.")

        return value


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



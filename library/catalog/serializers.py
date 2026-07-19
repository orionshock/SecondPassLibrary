from __future__ import annotations

from django.urls import reverse
from rest_framework import serializers

from library.groups.public_group import is_public_group
from library.models import Author, Book, BookIdentifier, CatalogTag, LibraryGroup, Series


def book_cover_url(obj: Book, request=None) -> str | None:
    cover = getattr(obj, "cover_file", None)
    if not cover:
        return None
    try:
        url = cover.url
    except Exception:
        return None
    return request.build_absolute_uri(url) if request is not None else url


class AuthorSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Author
        fields = ["id", "name"]
        read_only_fields = fields


class SeriesSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Series
        fields = ["id", "name"]
        read_only_fields = fields


class CatalogTagSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = CatalogTag
        fields = ["id", "name", "slug"]
        read_only_fields = fields


class BookGroupSummarySerializer(serializers.ModelSerializer):
    is_public_group = serializers.SerializerMethodField(read_only=True)

    def get_is_public_group(self, obj: LibraryGroup) -> bool:
        return is_public_group(obj)

    class Meta:
        model = LibraryGroup
        fields = ["id", "name", "description", "is_public_group"]
        read_only_fields = fields


class PreviewBooksAxisMixin:
    def get_preview_books(self, obj) -> list[dict]:
        books = getattr(obj, "_preview_books", [])
        return BookPreviewSerializer(books, many=True, context=self.context).data

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self.context.get("include_preview_books", False):
            data.pop("preview_books", None)
        return data


class AuthorAxisSerializer(PreviewBooksAxisMixin, serializers.ModelSerializer):
    book_count = serializers.IntegerField(read_only=True)
    preview_books = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Author
        fields = ["id", "name", "sort_name", "biography", "book_count", "preview_books"]
        read_only_fields = fields


class SeriesAxisSerializer(PreviewBooksAxisMixin, serializers.ModelSerializer):
    book_count = serializers.IntegerField(read_only=True)
    preview_books = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Series
        fields = ["id", "name", "sort_name", "summary", "book_count", "preview_books"]
        read_only_fields = fields


class AuthorAxisUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    biography = serializers.CharField(required=False, allow_blank=True)


class SeriesAxisUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    summary = serializers.CharField(required=False, allow_blank=True)


class CatalogTagAxisSerializer(serializers.ModelSerializer):
    book_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = CatalogTag
        fields = ["id", "name", "slug", "book_count"]
        read_only_fields = fields


class BookSeriesSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField(source="series.id")
    name = serializers.CharField(source="series.name")
    sort_name = serializers.CharField(source="series.sort_name")
    series_index = serializers.DecimalField(max_digits=8, decimal_places=2, allow_null=True)


class BookIdentifierSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookIdentifier
        fields = ["id", "scheme", "value"]
        read_only_fields = fields


class BookIdentifierWriteSerializer(serializers.Serializer):
    scheme = serializers.ChoiceField(choices=BookIdentifier.SCHEME_CHOICES)
    value = serializers.CharField(max_length=512)


class SeriesReferenceField(serializers.Field):
    default_error_messages = {
        "invalid": "Use an existing series id or an object with a name.",
        "not_found": "Series not found.",
    }

    def to_internal_value(self, data):
        if data is None:
            return None
        if isinstance(data, dict):
            name = str(data.get("name", "")).strip()
            if not name or len(name) > 255:
                self.fail("invalid")
            return {"name": name}
        try:
            return Series.objects.get(pk=data)
        except (Series.DoesNotExist, TypeError, ValueError):
            self.fail("not_found")

    def to_representation(self, value):
        raise NotImplementedError


class BookFileSerializer(serializers.Serializer):
    format = serializers.CharField(source="file_format")
    file_size = serializers.IntegerField(allow_null=True)
    checksum = serializers.CharField(allow_blank=True, allow_null=True)
    download_url = serializers.SerializerMethodField(read_only=True)

    def get_download_url(self, obj: Book) -> str:
        path = reverse("library:book-download", kwargs={"book_id": obj.pk})
        request = self.context.get("request")
        return request.build_absolute_uri(path) if request is not None else path


class BookPreviewSerializer(serializers.ModelSerializer):
    cover_url = serializers.SerializerMethodField(read_only=True)

    def get_cover_url(self, obj: Book) -> str | None:
        return book_cover_url(obj, request=self.context.get("request"))

    class Meta:
        model = Book
        fields = ["id", "title", "cover_url"]
        read_only_fields = fields


class BookListSerializer(serializers.ModelSerializer):
    authors = serializers.SerializerMethodField(read_only=True)
    cover_url = serializers.SerializerMethodField(read_only=True)
    series = serializers.SerializerMethodField(read_only=True)
    tags = serializers.SerializerMethodField(read_only=True)

    def get_authors(self, obj: Book) -> list[dict]:
        authors = [link.author for link in obj.book_authors.all()]
        return AuthorSummarySerializer(authors, many=True).data

    def get_cover_url(self, obj: Book) -> str | None:
        return book_cover_url(obj, request=self.context.get("request"))

    def get_series(self, obj: Book) -> dict | None:
        link = getattr(obj, "book_series", None)
        if link is None:
            return None
        return BookSeriesSummarySerializer(link).data

    def get_tags(self, obj: Book) -> list[dict]:
        tags = [link.catalog_tag for link in obj.book_catalog_tags.all()]
        return CatalogTagSummarySerializer(tags, many=True).data

    class Meta:
        model = Book
        fields = [
            "id",
            "title",
            "sort_title",
            "subtitle",
            "authors",
            "series",
            "tags",
            "language",
            "publisher",
            "published_year",
            "published_month",
            "published_day",
            "published_date_precision",
            "cover_url",
            "file_format",
        ]
        read_only_fields = fields


class BookDetailSerializer(BookListSerializer):
    identifiers = BookIdentifierSerializer(many=True, read_only=True)
    catalog_tags = serializers.SerializerMethodField(read_only=True)
    file = serializers.SerializerMethodField(read_only=True)
    groups = serializers.SerializerMethodField(read_only=True)

    def get_file(self, obj: Book) -> dict | None:
        if not obj.book_file:
            return None
        return BookFileSerializer(obj, context=self.context).data

    def get_catalog_tags(self, obj: Book) -> list[dict]:
        tags = [link.catalog_tag for link in obj.book_catalog_tags.all()]
        return CatalogTagSummarySerializer(tags, many=True).data

    def get_groups(self, obj: Book) -> list[dict]:
        return BookGroupSummarySerializer(
            getattr(obj, "_visible_groups", []), many=True
        ).data

    class Meta(BookListSerializer.Meta):
        fields = [
            "id",
            "title",
            "sort_title",
            "subtitle",
            "authors",
            "series",
            "language",
            "publisher",
            "published_year",
            "published_month",
            "published_day",
            "published_date_precision",
            "cover_url",
            "description",
            "identifiers",
            "catalog_tags",
            "file",
            "groups",
        ]
        read_only_fields = fields
        read_only_fields = fields


class BookUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=512, required=False)
    subtitle = serializers.CharField(max_length=512, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    publisher = serializers.CharField(max_length=255, required=False, allow_blank=True)
    language = serializers.CharField(max_length=64, required=False, allow_blank=True)
    published_year = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=9999)
    published_month = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=12)
    published_day = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=31)
    published_date_precision = serializers.ChoiceField(
        choices=["", *[choice[0] for choice in Book.DATE_PRECISION_CHOICES]],
        required=False,
    )
    authors = serializers.PrimaryKeyRelatedField(queryset=Author.objects.all(), many=True, required=False)
    series = SeriesReferenceField(required=False, allow_null=True)
    series_index = serializers.DecimalField(
        max_digits=8,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    identifiers = BookIdentifierWriteSerializer(many=True, required=False)
    catalog_tags = serializers.ListField(
        child=serializers.CharField(max_length=255),
        required=False,
        allow_empty=True,
    )

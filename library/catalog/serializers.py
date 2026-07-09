from __future__ import annotations

from rest_framework import serializers

from library.models import Author, Book, CatalogTag, Series


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
        fields = ["id", "name"]
        read_only_fields = fields


class BookSeriesSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField(source="series.id")
    name = serializers.CharField(source="series.name")
    sort_name = serializers.CharField(source="series.sort_name")
    series_index = serializers.DecimalField(max_digits=8, decimal_places=2, allow_null=True)


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
    class Meta(BookListSerializer.Meta):
        fields = [*BookListSerializer.Meta.fields, "description"]
        read_only_fields = fields

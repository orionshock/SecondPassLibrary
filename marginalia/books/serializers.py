from __future__ import annotations

from rest_framework import serializers

from library.catalog.serializers import book_cover_url
from library.models import Book
from library.series_indexes import SERIES_INDEX_DECIMAL_PLACES, SERIES_INDEX_MAX_DIGITS


class MarginaliaBookSeriesSerializer(serializers.Serializer):
    id = serializers.UUIDField(source="series_id")
    name = serializers.CharField(source="series.name")
    series_index = serializers.DecimalField(
        max_digits=SERIES_INDEX_MAX_DIGITS,
        decimal_places=SERIES_INDEX_DECIMAL_PLACES,
        allow_null=True,
    )


class MarginaliaBookSummarySerializer(serializers.ModelSerializer):
    authors = serializers.SerializerMethodField()
    series = serializers.SerializerMethodField()
    cover_url = serializers.SerializerMethodField()
    can_open = serializers.BooleanField(read_only=True)
    session_count = serializers.IntegerField(read_only=True)
    active_session_count = serializers.IntegerField(read_only=True)
    last_activity_at = serializers.DateTimeField(read_only=True)

    def get_authors(self, book: Book) -> list[dict]:
        return [
            {"id": str(link.author_id), "name": link.author.name}
            for link in book.book_authors.all()
        ]

    def get_series(self, book: Book) -> dict | None:
        link = getattr(book, "book_series", None)
        if link is None:
            return None
        return MarginaliaBookSeriesSerializer(link).data

    def get_cover_url(self, book: Book) -> str | None:
        return book_cover_url(book, request=self.context.get("request"))

    class Meta:
        model = Book
        fields = [
            "id",
            "title",
            "authors",
            "series",
            "cover_url",
            "can_open",
            "session_count",
            "active_session_count",
            "last_activity_at",
        ]
        read_only_fields = fields


class MarginaliaSessionBookReferenceSerializer(serializers.ModelSerializer):
    cover_url = serializers.SerializerMethodField()
    can_open = serializers.SerializerMethodField()

    def get_cover_url(self, book: Book) -> str | None:
        return book_cover_url(book, request=self.context.get("request"))

    def get_can_open(self, _book: Book) -> bool:
        return bool(self.context.get("can_open", False))

    class Meta:
        model = Book
        fields = ["id", "title", "cover_url", "can_open"]
        read_only_fields = fields

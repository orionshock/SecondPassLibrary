from __future__ import annotations

from rest_framework import serializers

from library.models import Author, Book, Series


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


class BookPreviewSerializer(serializers.ModelSerializer):
    cover_url = serializers.SerializerMethodField(read_only=True)

    def get_cover_url(self, obj: Book) -> str | None:
        return book_cover_url(obj, request=self.context.get("request"))

    class Meta:
        model = Book
        fields = ["id", "title", "cover_url"]
        read_only_fields = fields

from rest_framework import serializers

from library.models import Author, CatalogTag, Series

from .books import BookPreviewSerializer
from .unknown_fields import RejectUnknownFieldsMixin


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


class AuthorAxisUpdateSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    sort_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    biography = serializers.CharField(required=False, allow_blank=True)


class AuthorCreateSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    name = serializers.CharField(max_length=255)
    sort_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    biography = serializers.CharField(required=False, allow_blank=True)


class SeriesAxisUpdateSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    sort_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    summary = serializers.CharField(required=False, allow_blank=True)


class SeriesCreateSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    name = serializers.CharField(max_length=255)
    sort_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    summary = serializers.CharField(required=False, allow_blank=True)


class CatalogTagAxisSerializer(serializers.ModelSerializer):
    book_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = CatalogTag
        fields = ["id", "name", "slug", "book_count"]
        read_only_fields = fields


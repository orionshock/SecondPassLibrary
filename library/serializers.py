from rest_framework import serializers
from rest_framework.reverse import reverse

from .models import (
    Author,
    Book,
    BookFile,
    Series,
    BookIdentifier,
    ImportJob,
    ImportJobItem,
)


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Author
        fields = ["id", "name", "biography", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class SeriesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Series
        fields = ["id", "name", "summary", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


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


class BookSerializer(serializers.ModelSerializer):
    authors = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Author.objects.all()
    )
    series = serializers.PrimaryKeyRelatedField(
        queryset=Series.objects.all(), required=False, allow_null=True
    )
    files = BookFileSerializer(many=True, read_only=True)
    identifiers = serializers.SerializerMethodField(read_only=True)

    def get_identifiers(self, obj: Book):
        identifiers = obj.identifiers.order_by("scheme", "value").all()
        return BookIdentifierSerializer(identifiers, many=True).data

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
            "files",
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

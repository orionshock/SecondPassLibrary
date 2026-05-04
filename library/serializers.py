from rest_framework import serializers

from .models import Author, Book, BookFile, BookMetadata, Series


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


class BookMetadataSerializer(serializers.ModelSerializer):
    book = serializers.PrimaryKeyRelatedField(
        queryset=Book.objects.all(), required=False
    )

    class Meta:
        model = BookMetadata
        fields = [
            "id",
            "book",
            "publisher",
            "language",
            "published_date",
            "isbn",
            "subjects",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class BookFileSerializer(serializers.ModelSerializer):
    file = serializers.FileField()

    class Meta:
        model = BookFile
        fields = [
            "id",
            "book",
            "file",
            "format",
            "checksum",
            "file_size",
            "source_filename",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class BookSerializer(serializers.ModelSerializer):
    authors = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Author.objects.all()
    )
    series = serializers.PrimaryKeyRelatedField(
        queryset=Series.objects.all(), required=False, allow_null=True
    )
    metadata = BookMetadataSerializer(required=False, allow_null=True)
    files = BookFileSerializer(many=True, read_only=True)

    class Meta:
        model = Book
        fields = [
            "id",
            "title",
            "subtitle",
            "summary",
            "authors",
            "series",
            "metadata",
            "files",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def create(self, validated_data):
        metadata_data = validated_data.pop("metadata", None)
        authors = validated_data.pop("authors", [])
        book = Book.objects.create(**validated_data)
        book.authors.set(authors)
        if metadata_data:
            BookMetadata.objects.create(book=book, **metadata_data)
        return book

    def update(self, instance, validated_data):
        metadata_data = validated_data.pop("metadata", None)
        authors = validated_data.pop("authors", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if authors is not None:
            instance.authors.set(authors)
        instance.save()

        if metadata_data is not None:
            metadata, _ = BookMetadata.objects.get_or_create(book=instance)
            for attr, value in metadata_data.items():
                setattr(metadata, attr, value)
            metadata.save()

        return instance

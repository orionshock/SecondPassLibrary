from rest_framework import serializers

from library.models import Book

from .models import Annotation, Device, ReadingProgress, ReadingSession


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = [
            "id",
            "name",
            "device_type",
            "last_seen_at",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ReadingSessionSerializer(serializers.ModelSerializer):
    book_title = serializers.CharField(source="book.title", read_only=True)

    class Meta:
        model = ReadingSession
        fields = [
            "id",
            "book",
            "book_title",
            "status",
            "name",
            "started_at",
            "completed_at",
            "is_active",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "started_at",
            "created_at",
            "updated_at",
            "book_title",
        ]


class ReadingSessionCreateSerializer(serializers.ModelSerializer):
    book = serializers.PrimaryKeyRelatedField(queryset=Book.objects.all())

    class Meta:
        model = ReadingSession
        fields = [
            "id",
            "book",
            "status",
            "name",
            "completed_at",
            "is_active",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ReadingProgressSerializer(serializers.ModelSerializer):
    def validate_device(self, device):
        request = self.context.get("request")
        if device is None or request is None or request.user.is_anonymous:
            return device
        if device.user_id != request.user.id:
            raise serializers.ValidationError("Invalid device.")
        return device

    class Meta:
        model = ReadingProgress
        fields = [
            "session",
            "device",
            "locator",
            "progression",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class AnnotationSerializer(serializers.ModelSerializer):
    def validate_session(self, session):
        request = self.context.get("request")
        if request is None or request.user.is_anonymous:
            return session
        if session.user_id != request.user.id:
            raise serializers.ValidationError("Invalid session.")
        return session

    def validate_device(self, device):
        request = self.context.get("request")
        if device is None or request is None or request.user.is_anonymous:
            return device
        if device.user_id != request.user.id:
            raise serializers.ValidationError("Invalid device.")
        return device

    class Meta:
        model = Annotation
        fields = [
            "id",
            "session",
            "device",
            "kind",
            "locator",
            "selected_text",
            "note",
            "color",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

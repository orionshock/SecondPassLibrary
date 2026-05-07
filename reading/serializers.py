from rest_framework import serializers

from library.models import Book

from .models import Annotation, Device, ReadingProgress, ReadingSession
from .locators import normalize_locator


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


class ReadingSessionPatchSerializer(serializers.ModelSerializer):
    """
    Client-safe session updates.

    Sessions are created via the dedicated active-session and start-over endpoints.
    This serializer supports editing only small user-controlled metadata fields.
    """

    class Meta:
        model = ReadingSession
        fields = ["name", "notes"]

    def validate(self, attrs):
        initial = getattr(self, "initial_data", {}) or {}
        allowed = {"name", "notes"}
        present = set(initial.keys())
        forbidden = present.difference(allowed)
        if forbidden:
            raise serializers.ValidationError(
                {
                    "detail": "Only 'name' and 'notes' can be updated via this endpoint."
                }
            )
        return super().validate(attrs)


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

    def validate_locator(self, locator):
        return normalize_locator(locator)


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

    def validate_locator(self, locator):
        return normalize_locator(locator)

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

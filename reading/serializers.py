from rest_framework import serializers

from .models import Annotation, Device, ReadingProgress, ReadingSession
from .locators import normalize_current_location


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
            "current_location",
            "progression",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["session", "created_at", "updated_at"]

    def validate_current_location(self, current_location):
        return normalize_current_location(current_location)


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
            "motivation",
            "target",
            "body",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_deleted", "created_at", "updated_at"]

    def validate_motivation(self, motivation):
        if motivation is None or (isinstance(motivation, str) and not motivation.strip()):
            raise serializers.ValidationError("This field is required.")
        return motivation

    def validate(self, attrs):
        initial = getattr(self, "initial_data", {}) or {}
        allowed = {"session", "device", "motivation", "target", "body"}
        present = set(initial.keys())
        unknown = present.difference(allowed)
        if unknown:
            unknown_sorted = ", ".join(sorted(unknown))
            raise serializers.ValidationError(
                {"detail": f"Unsupported fields: {unknown_sorted}."}
            )
        return super().validate(attrs)

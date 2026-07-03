from typing import Any, cast

from rest_framework import serializers

from library import policies as library_policies
from library.models import Author, Book, Series

from .models import (
    Annotation,
    ReadingProgress,
    ReadingSession,
)
from .annotation_profile_services import annotation_profile_representation
from .locators import normalize_current_location
from .profile import (
    CURRENT_READING_PROFILE_VERSION,
    validate_annotation_body,
    validate_annotation_target,
    validate_current_location,
    validate_profile_version,
)


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


class ReadingSessionBookSummarySerializer(serializers.ModelSerializer):
    authors = AuthorSummarySerializer(many=True, read_only=True)
    series = SeriesSummarySerializer(read_only=True, allow_null=True)
    cover_url = serializers.SerializerMethodField(read_only=True)

    def get_cover_url(self, obj: Book) -> str | None:
        cover = getattr(obj, "cover_file", None)
        if not cover:
            return None
        request = self.context.get("request")
        if request is not None:
            try:
                return request.build_absolute_uri(cover.url)
            except Exception:
                return None
        return getattr(cover, "url", None)

    class Meta:
        model = Book
        fields = ["id", "title", "authors", "series", "series_index", "cover_url"]
        read_only_fields = fields


class ReadingSessionSummarySerializer(serializers.ModelSerializer):
    book_id = serializers.UUIDField(read_only=True)
    progression = serializers.FloatField(read_only=True, allow_null=True)
    annotation_count = serializers.IntegerField(read_only=True)
    book = serializers.SerializerMethodField(read_only=True)
    can_open = serializers.SerializerMethodField(read_only=True)

    def _can_view_book(self, obj: ReadingSession) -> bool:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        book = getattr(obj, "book", None)
        return bool(
            user is not None
            and book is not None
            and library_policies.can_view_book(user=user, book=book)
        )

    def get_book(self, obj: ReadingSession) -> dict[str, Any]:
        request = self.context.get("request")
        book = cast(Book, getattr(obj, "book", None))
        if book is None:
            return {
                "id": None,
                "title": "",
                "authors": [],
                "series": None,
                "series_index": None,
                "cover_url": None,
            }

        # Don't leak hidden/inaccessible library metadata through user-owned sessions.
        if not self._can_view_book(obj):
            return {
                "id": str(book.id),
                "title": "",
                "authors": [],
                "series": None,
                "series_index": None,
                "cover_url": None,
            }

        return cast(
            dict[str, Any],
            ReadingSessionBookSummarySerializer(book, context={"request": request}).data,
        )

    def get_can_open(self, obj: ReadingSession) -> bool:
        return self._can_view_book(obj)

    class Meta:
        model = ReadingSession
        fields = [
            "id",
            "book_id",
            "name",
            "status",
            "is_active",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
            "notes",
            "progression",
            "annotation_count",
            "book",
            "can_open",
        ]
        read_only_fields = fields


class ReadingProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReadingProgress
        fields = [
            "session",
            "current_location",
            "progression",
            "profile_version",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["session", "created_at", "updated_at"]

    def validate_current_location(self, current_location):
        normalized = normalize_current_location(current_location)
        try:
            return validate_current_location(normalized)
        except ValueError as e:
            raise serializers.ValidationError(str(e)) from e

    def validate_profile_version(self, profile_version):
        try:
            return validate_profile_version(profile_version)
        except ValueError as e:
            raise serializers.ValidationError(str(e)) from e

    def validate(self, attrs):
        initial = getattr(self, "initial_data", {}) or {}
        allowed = {"current_location", "progression", "profile_version"}
        present = set(initial.keys())
        unknown = present.difference(allowed)
        if unknown:
            unknown_sorted = ", ".join(sorted(unknown))
            raise serializers.ValidationError(
                {"detail": f"Unsupported fields: {unknown_sorted}."}
            )

        # If the client omitted profile_version, set it to the current version.
        if "profile_version" not in attrs:
            attrs["profile_version"] = CURRENT_READING_PROFILE_VERSION
        return super().validate(attrs)


class AnnotationSerializer(serializers.ModelSerializer):
    motivation = serializers.JSONField()
    target = serializers.JSONField(write_only=True, required=False)
    body = serializers.JSONField(write_only=True, required=False)

    def validate_session(self, session):
        request = self.context.get("request")
        if request is None or request.user.is_anonymous:
            return session
        if session.user_id != request.user.id:
            raise serializers.ValidationError("Invalid session.")
        return session

    class Meta:
        model = Annotation
        fields = [
            "id",
            "session",
            "motivation",
            "target",
            "body",
            "profile_version",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_deleted", "created_at", "updated_at"]

    def validate_motivation(self, motivation):
        if motivation is None:
            raise serializers.ValidationError("This field is required.")
        if isinstance(motivation, str):
            v = motivation.strip()
            if not v:
                raise serializers.ValidationError("This field is required.")
            items = [v]
        elif isinstance(motivation, list):
            items = []
            for idx, m in enumerate(motivation):
                if not isinstance(m, str):
                    raise serializers.ValidationError(f"motivation[{idx}] must be a string.")
                t = m.strip()
                if not t:
                    raise serializers.ValidationError(f"motivation[{idx}] cannot be blank.")
                items.append(t)
        else:
            raise serializers.ValidationError("motivation must be a string or list of strings.")

        allowed = {c[0] for c in Annotation.MOTIVATION_CHOICES}
        if any(m not in allowed for m in items):
            raise serializers.ValidationError("Invalid motivation.")
        return items

    def validate_target(self, target):
        try:
            validated = validate_annotation_target(target)
        except ValueError as e:
            raise serializers.ValidationError(str(e)) from e

        selector = validated.get("selector") if isinstance(validated, dict) else None
        selector_value: str | None = None
        if isinstance(selector, dict):
            raw = selector.get("value")
            selector_value = raw if isinstance(raw, str) else None
        elif isinstance(selector, list):
            for item in selector:
                if not isinstance(item, dict):
                    continue
                if item.get("type") not in (None, "FragmentSelector"):
                    continue
                raw = item.get("value")
                if isinstance(raw, str) and raw:
                    selector_value = raw
                    break
        if not selector_value:
            raise serializers.ValidationError("A FragmentSelector with selector.value is required.")
        return validated

    def validate_body(self, body):
        try:
            return validate_annotation_body(body)
        except ValueError as e:
            raise serializers.ValidationError(str(e)) from e

    def validate_profile_version(self, profile_version):
        try:
            return validate_profile_version(profile_version)
        except ValueError as e:
            raise serializers.ValidationError(str(e)) from e

    def validate(self, attrs):
        initial = getattr(self, "initial_data", {}) or {}
        allowed = {
            "session",
            "motivation",
            "target",
            "body",
            "profile_version",
        }
        present = set(initial.keys())
        unknown = present.difference(allowed)
        if unknown:
            unknown_sorted = ", ".join(sorted(unknown))
            raise serializers.ValidationError(
                {"detail": f"Unsupported fields: {unknown_sorted}."}
            )

        # If the client omitted profile_version, set it to the current version.
        if "profile_version" not in attrs:
            attrs["profile_version"] = CURRENT_READING_PROFILE_VERSION

        if self.instance is None:
            if "target" not in attrs:
                raise serializers.ValidationError({"target": "This field is required."})
            if "body" not in attrs:
                # Bookmarks do not require a body payload. Default to [] and enforce
                # describing requirements later based on inferred anchor kind.
                attrs["body"] = []

        # Keep annotation session immutable for now (avoids cross-book inconsistencies).
        if self.instance is not None and "session" in attrs:
            if getattr(attrs["session"], "id", None) != getattr(self.instance, "session_id", None):
                raise serializers.ValidationError({"detail": "session cannot be changed."})
        return super().validate(attrs)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        return annotation_profile_representation(instance, cast(dict[str, Any], data))

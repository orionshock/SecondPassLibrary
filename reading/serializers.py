from typing import Any, cast

from rest_framework import serializers

from library import policies as library_policies
from library.models import Author, Book, Series

from .models import (
    HIGHLIGHT_COLOR_TOKENS,
    HIGHLIGHT_COLOR_YELLOW,
    SELECTOR_KIND_EPUB_CFI,
    Annotation,
    ReadingProgress,
    ReadingSession,
)
from .profile.locators import normalize_current_location
from .profile.validation import (
    CURRENT_READING_PROFILE_VERSION,
    MAX_BODY_VALUE_CHARS,
    MAX_SELECTOR_VALUE_CHARS,
    MAX_TEXT_QUOTE_CONTEXT_CHARS,
    normalize_epub_cfi,
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
    book = serializers.UUIDField(source="book_id", read_only=True)
    kind = serializers.CharField(source="anchor_kind")
    selector = serializers.JSONField(write_only=True)
    quote = serializers.JSONField(write_only=True, required=False)
    has_comment = serializers.SerializerMethodField()

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
            "book",
            "kind",
            "selector",
            "quote",
            "highlight_text",
            "highlight_color",
            "comment_text",
            "has_comment",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "book", "has_comment", "is_deleted", "created_at", "updated_at"]

    def get_has_comment(self, obj):
        return bool((obj.comment_text or "").strip())

    def validate_kind(self, kind):
        value = str(kind or "").strip()
        if value not in {Annotation.ANCHOR_KIND_BOOKMARK, Annotation.ANCHOR_KIND_HIGHLIGHT}:
            raise serializers.ValidationError("kind must be 'bookmark' or 'highlight'.")
        return value

    def validate_selector(self, selector):
        if not isinstance(selector, dict):
            raise serializers.ValidationError("selector must be an object.")
        unknown = set(selector.keys()).difference({"kind", "value"})
        if unknown:
            raise serializers.ValidationError(
                f"Unsupported selector fields: {', '.join(sorted(unknown))}."
            )
        kind = str(selector.get("kind") or "").strip()
        if kind != SELECTOR_KIND_EPUB_CFI:
            raise serializers.ValidationError("selector.kind must be 'epub_cfi'.")
        value = normalize_epub_cfi(selector.get("value"))
        if not value:
            raise serializers.ValidationError("selector.value is required.")
        if len(value) > MAX_SELECTOR_VALUE_CHARS:
            raise serializers.ValidationError(
                f"selector.value exceeds maximum length ({MAX_SELECTOR_VALUE_CHARS} chars)."
            )
        return {"kind": SELECTOR_KIND_EPUB_CFI, "value": value}

    def validate_quote(self, quote):
        if quote in (None, ""):
            return {}
        if not isinstance(quote, dict):
            raise serializers.ValidationError("quote must be an object.")
        unknown = set(quote.keys()).difference({"exact", "prefix", "suffix"})
        if unknown:
            raise serializers.ValidationError(
                f"Unsupported quote fields: {', '.join(sorted(unknown))}."
            )
        result: dict[str, str] = {}
        for key in ("exact", "prefix", "suffix"):
            if key not in quote:
                continue
            value = quote.get(key)
            if value is None:
                continue
            if not isinstance(value, str):
                raise serializers.ValidationError(f"quote.{key} must be a string.")
            if key == "exact" and len(value) > MAX_BODY_VALUE_CHARS:
                raise serializers.ValidationError(
                    f"quote.exact exceeds maximum length ({MAX_BODY_VALUE_CHARS} chars)."
                )
            if key in {"prefix", "suffix"} and len(value) > MAX_TEXT_QUOTE_CONTEXT_CHARS:
                raise serializers.ValidationError(
                    f"quote.{key} exceeds maximum length ({MAX_TEXT_QUOTE_CONTEXT_CHARS} chars)."
                )
            if value:
                result[key] = value
        return result

    def validate_highlight_text(self, value):
        if value is None:
            return ""
        if len(value) > MAX_BODY_VALUE_CHARS:
            raise serializers.ValidationError(
                f"highlight_text exceeds maximum length ({MAX_BODY_VALUE_CHARS} chars)."
            )
        return value

    def validate_comment_text(self, value):
        if value is None:
            return ""
        if len(value) > MAX_BODY_VALUE_CHARS:
            raise serializers.ValidationError(
                f"comment_text exceeds maximum length ({MAX_BODY_VALUE_CHARS} chars)."
            )
        return value

    def validate_highlight_color(self, value):
        if value is None:
            return ""
        token = value.strip()
        if token and token not in HIGHLIGHT_COLOR_TOKENS:
            raise serializers.ValidationError("Unsupported highlight_color token.")
        return token

    def validate(self, attrs):
        initial = getattr(self, "initial_data", {}) or {}
        allowed = {
            "session",
            "kind",
            "selector",
            "quote",
            "highlight_text",
            "highlight_color",
            "comment_text",
        }
        present = set(initial.keys())
        unknown = present.difference(allowed)
        if unknown:
            unknown_sorted = ", ".join(sorted(unknown))
            raise serializers.ValidationError(
                {"detail": f"Unsupported fields: {unknown_sorted}."}
            )

        if self.instance is None:
            if "selector" not in attrs:
                raise serializers.ValidationError({"selector": "This field is required."})

        # Keep annotation session immutable for now (avoids cross-book inconsistencies).
        if self.instance is not None and "session" in attrs:
            if getattr(attrs["session"], "id", None) != getattr(self.instance, "session_id", None):
                raise serializers.ValidationError({"detail": "session cannot be changed."})
        kind = attrs.get("anchor_kind") or getattr(self.instance, "anchor_kind", "")
        highlight_text = attrs.get("highlight_text", getattr(self.instance, "highlight_text", ""))
        highlight_color = attrs.get("highlight_color", getattr(self.instance, "highlight_color", ""))
        comment_text = attrs.get("comment_text", getattr(self.instance, "comment_text", ""))
        quote = attrs.get("quote") or {}

        if kind == Annotation.ANCHOR_KIND_BOOKMARK:
            if highlight_text or highlight_color or comment_text or quote:
                raise serializers.ValidationError(
                    {"detail": "Bookmarks cannot include highlight/comment/quote payload."}
                )
        elif kind == Annotation.ANCHOR_KIND_HIGHLIGHT:
            if not str(highlight_text or "").strip():
                raise serializers.ValidationError({"highlight_text": "This field is required for highlights."})
            exact = quote.get("exact") if isinstance(quote, dict) else None
            if exact and exact != highlight_text:
                raise serializers.ValidationError({"quote": "quote.exact must match highlight_text."})
            if "highlight_color" not in attrs and not highlight_color:
                attrs["highlight_color"] = HIGHLIGHT_COLOR_YELLOW
        return super().validate(attrs)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["kind"] = instance.anchor_kind
        data["selector"] = {
            "kind": instance.selector_kind,
            "value": instance.selector_value,
        }
        data["quote"] = {}
        if instance.quote_prefix:
            data["quote"]["prefix"] = instance.quote_prefix
        if instance.quote_suffix:
            data["quote"]["suffix"] = instance.quote_suffix
        if instance.highlight_text and data["quote"]:
            data["quote"]["exact"] = instance.highlight_text
            data["quote"] = {
                key: data["quote"][key]
                for key in ("exact", "prefix", "suffix")
                if key in data["quote"]
            }
        return cast(dict[str, Any], data)

from typing import Any, cast

from rest_framework import serializers

from core import policies
from library.models import Author, Book, Series

from .models import (
    Annotation,
    ReadingProgress,
    ReadingSession,
    SELECTOR_KIND_EPUB_CFI,
    HIGHLIGHT_COLOR_TOKENS,
    HIGHLIGHT_COLOR_YELLOW,
)
from .locators import normalize_current_location
from .profile import (
    CURRENT_READING_PROFILE_VERSION,
    EPUB_CFI_CONFORMS_TO,
    validate_annotation_body,
    validate_annotation_target,
    validate_current_location,
    validate_profile_version,
 )
from .w3c import build_publication_source


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
    # Keep for compatibility during active development.
    book_title = serializers.CharField(source="book.title", read_only=True)

    book_id = serializers.UUIDField(read_only=True)
    progression = serializers.FloatField(read_only=True, allow_null=True)
    annotation_count = serializers.IntegerField(read_only=True)
    book = serializers.SerializerMethodField(read_only=True)

    def get_book(self, obj: ReadingSession) -> dict[str, Any]:
        request = self.context.get("request")
        user = getattr(request, "user", None)
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
        if user is None or not policies.can_view_book(user=user, book=book):
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
            "book_title",
            "book",
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
    target = serializers.JSONField(write_only=True)
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
        if motivation is None or (isinstance(motivation, str) and not motivation.strip()):
            raise serializers.ValidationError("This field is required.")
        return motivation

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

        # Keep annotation session immutable for now (avoids cross-book inconsistencies).
        if self.instance is not None and "session" in attrs:
            if getattr(attrs["session"], "id", None) != getattr(self.instance, "session_id", None):
                raise serializers.ValidationError({"detail": "session cannot be changed."})
        return super().validate(attrs)

    def _compact_from_profile(
        self, *, motivation: str, target: dict[str, Any], body: list[dict[str, Any]]
    ) -> dict[str, str]:
        selector = target.get("selector")
        selector_value: str = ""
        quote_exact: str = ""
        quote_prefix: str = ""
        quote_suffix: str = ""

        if isinstance(selector, dict):
            raw_value = selector.get("value")
            if isinstance(raw_value, str) and raw_value:
                selector_value = raw_value
            elif raw_value is not None and raw_value != "":
                selector_value = str(raw_value)
        elif isinstance(selector, list):
            for item in selector:
                if not isinstance(item, dict):
                    continue
                stype = item.get("type")
                if stype == "TextQuoteSelector":
                    raw_exact = item.get("exact")
                    if isinstance(raw_exact, str) and raw_exact.strip() and not quote_exact:
                        quote_exact = raw_exact
                        raw_prefix = item.get("prefix")
                        raw_suffix = item.get("suffix")
                        quote_prefix = raw_prefix if isinstance(raw_prefix, str) else ""
                        quote_suffix = raw_suffix if isinstance(raw_suffix, str) else ""
                elif stype in (None, "FragmentSelector"):
                    raw_value = item.get("value")
                    if selector_value:
                        continue
                    if isinstance(raw_value, str) and raw_value:
                        selector_value = raw_value
                    elif raw_value is not None and raw_value != "":
                        selector_value = str(raw_value)

        highlight_text: str = ""
        highlight_color: str = ""
        comment_text: str = ""

        for b in body or []:
            if not isinstance(b, dict):
                continue
            if b.get("type") != "TextualBody":
                continue
            purpose = str(b.get("purpose") or "").strip()
            raw_value = b.get("value")
            value: str = raw_value if isinstance(raw_value, str) else ""
            raw_color = b.get("color")
            color: str = raw_color if isinstance(raw_color, str) else ""

            if purpose in ("highlighting", "describing") and (value or color):
                if not highlight_text:
                    highlight_text = value
                if not highlight_color and color:
                    highlight_color = color.strip()
            elif purpose == "commenting" and value:
                if not comment_text:
                    comment_text = value

        if quote_exact:
            if highlight_text and highlight_text != quote_exact:
                raise serializers.ValidationError(
                    {"target": "TextQuoteSelector.exact must match describing body value."}
                )
            if not highlight_text and motivation == Annotation.MOTIVATION_HIGHLIGHTING:
                highlight_text = quote_exact
            elif not highlight_text:
                # Only store quote context for highlight-style annotations. Other
                # motivations may legitimately omit a describing quote body.
                quote_exact = ""
                quote_prefix = ""
                quote_suffix = ""

        if highlight_text or highlight_color:
            if not highlight_color:
                highlight_color = HIGHLIGHT_COLOR_YELLOW
            elif highlight_color not in HIGHLIGHT_COLOR_TOKENS:
                raise serializers.ValidationError(
                    {"body": "Unsupported highlight color token."}
                )

        return {
            "selector_kind": SELECTOR_KIND_EPUB_CFI,
            "selector_value": selector_value,
            "highlight_text": highlight_text,
            "quote_prefix": quote_prefix,
            "quote_suffix": quote_suffix,
            "highlight_color": highlight_color,
            "comment_text": comment_text,
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)

        fragment: dict[str, str] = {"value": instance.selector_value}
        if instance.selector_kind == SELECTOR_KIND_EPUB_CFI:
            fragment["type"] = "FragmentSelector"
            fragment["conformsTo"] = EPUB_CFI_CONFORMS_TO
        else:
            # Safety fallback: avoid crashing list/detail if a bad row exists.
            fragment["type"] = "UnknownSelector"

        source = build_publication_source(book=instance.book)
        selector_out: object = fragment
        if (
            instance.highlight_text
            and (getattr(instance, "quote_prefix", "") or getattr(instance, "quote_suffix", ""))
        ):
            quote: dict[str, str] = {"type": "TextQuoteSelector", "exact": instance.highlight_text}
            if getattr(instance, "quote_prefix", ""):
                quote["prefix"] = instance.quote_prefix
            if getattr(instance, "quote_suffix", ""):
                quote["suffix"] = instance.quote_suffix
            selector_out = [fragment, quote]

        data["target"] = {"source": source, "selector": selector_out}

        bodies: list[dict] = []
        if instance.highlight_text or instance.highlight_color:
            b: dict = {"type": "TextualBody", "purpose": "describing", "value": instance.highlight_text or ""}
            # Color token is part of the stable highlight contract; default to yellow.
            b["color"] = (instance.highlight_color or HIGHLIGHT_COLOR_YELLOW)
            bodies.append(b)
        if instance.comment_text:
            bodies.append(
                {"type": "TextualBody", "purpose": "commenting", "value": instance.comment_text}
            )
        data["body"] = bodies
        return data

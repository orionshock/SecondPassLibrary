from rest_framework import serializers

from .models import Annotation, ReadingProgress, ReadingSession, SELECTOR_KIND_EPUB_CFI
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
        selector_value = selector.get("value") if isinstance(selector, dict) else None
        if not selector_value:
            raise serializers.ValidationError("selector.value is required.")
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
        self, *, target: dict, body: list[dict]
    ) -> dict[str, str]:
        selector = target.get("selector") if isinstance(target, dict) else None
        selector_value = (
            str(selector.get("value"))
            if isinstance(selector, dict) and selector.get("value")
            else ""
        )

        highlight_text = ""
        highlight_color = ""
        comment_text = ""

        for b in body or []:
            if not isinstance(b, dict):
                continue
            if b.get("type") != "TextualBody":
                continue
            purpose = (b.get("purpose") or "").strip()
            value = b.get("value") if isinstance(b.get("value"), str) else ""
            color = b.get("color") if isinstance(b.get("color"), str) else ""

            if purpose in ("highlighting", "describing") and (value or color):
                if not highlight_text:
                    highlight_text = value
                if not highlight_color and color:
                    highlight_color = color
            elif purpose == "commenting" and value:
                if not comment_text:
                    comment_text = value

        return {
            "selector_kind": SELECTOR_KIND_EPUB_CFI,
            "selector_value": selector_value,
            "highlight_text": highlight_text,
            "highlight_color": highlight_color,
            "comment_text": comment_text,
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)

        if instance.selector_kind != SELECTOR_KIND_EPUB_CFI:
            # Keep behavior explicit: today we only support EPUB CFI selectors.
            raise serializers.ValidationError({"detail": "Unsupported selector_kind."})

        selector = {
            "type": "FragmentSelector",
            "conformsTo": EPUB_CFI_CONFORMS_TO,
            "value": instance.selector_value,
        }

        source = build_publication_source(book=instance.book)
        data["target"] = {"source": source, "selector": selector}

        bodies: list[dict] = []
        if instance.highlight_text or instance.highlight_color:
            b: dict = {"type": "TextualBody", "purpose": "describing", "value": instance.highlight_text or ""}
            if instance.highlight_color:
                b["color"] = instance.highlight_color
            bodies.append(b)
        if instance.comment_text:
            bodies.append(
                {"type": "TextualBody", "purpose": "commenting", "value": instance.comment_text}
            )
        data["body"] = bodies
        return data

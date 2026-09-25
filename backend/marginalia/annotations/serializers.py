from __future__ import annotations

from rest_framework import serializers

from marginalia.cfi import validate_durable_cfi
from marginalia.models import (
    HIGHLIGHT_COLOR_CHOICES,
    HIGHLIGHT_COLOR_YELLOW,
    MAX_ANNOTATION_BODY_LENGTH,
    MAX_ANNOTATION_CLIENT_ID_LENGTH,
    MAX_LOCATION_LENGTH,
    MAX_LOCATION_LABEL_LENGTH,
    MAX_QUOTE_CONTEXT_LENGTH,
    Annotation,
)
from marginalia.serializer_fields import OpaqueStringField, StrictSerializer


BATCH_ANNOTATION_OPERATION_LIMIT = 100


class ClientIdField(OpaqueStringField):
    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if not value.strip():
            self.fail("blank")
        return value


class AnnotationLocationSerializer(StrictSerializer):
    location = OpaqueStringField(
        max_length=MAX_LOCATION_LENGTH,
        allow_blank=False,
        trim_whitespace=False,
        validators=[validate_durable_cfi],
    )
    location_label = OpaqueStringField(
        max_length=MAX_LOCATION_LABEL_LENGTH,
        allow_blank=True,
        default="",
        required=False,
        trim_whitespace=False,
    )


class HighlightBodySerializer(StrictSerializer):
    text = OpaqueStringField(
        max_length=MAX_ANNOTATION_BODY_LENGTH,
        allow_blank=False,
        trim_whitespace=False,
    )
    prefix = OpaqueStringField(
        max_length=MAX_QUOTE_CONTEXT_LENGTH,
        allow_blank=True,
        default="",
        required=False,
        trim_whitespace=False,
    )
    suffix = OpaqueStringField(
        max_length=MAX_QUOTE_CONTEXT_LENGTH,
        allow_blank=True,
        default="",
        required=False,
        trim_whitespace=False,
    )
    color = serializers.ChoiceField(
        choices=[choice[0] for choice in HIGHLIGHT_COLOR_CHOICES],
        default=HIGHLIGHT_COLOR_YELLOW,
        required=False,
    )
    note = OpaqueStringField(
        max_length=MAX_ANNOTATION_BODY_LENGTH,
        allow_blank=True,
        default="",
        required=False,
        trim_whitespace=False,
    )


class AnnotationUpsertSerializer(StrictSerializer):
    client_id = ClientIdField(
        max_length=MAX_ANNOTATION_CLIENT_ID_LENGTH,
        allow_blank=False,
        trim_whitespace=False,
    )
    kind = serializers.ChoiceField(
        choices=[choice[0] for choice in Annotation.KIND_CHOICES]
    )
    location = AnnotationLocationSerializer()
    body = HighlightBodySerializer(required=False)

    def to_internal_value(self, data):
        if (
            hasattr(data, "get")
            and data.get("kind") == Annotation.KIND_BOOKMARK
            and "body" in data
        ):
            raise serializers.ValidationError(
                {"body": "Bookmarks cannot include a body."}
            )
        return super().to_internal_value(data)

    def validate(self, attrs):
        if attrs["kind"] == Annotation.KIND_HIGHLIGHT and "body" not in attrs:
            raise serializers.ValidationError(
                {"body": "This field is required for highlights."}
            )
        return attrs


class AnnotationBatchOperationSerializer(StrictSerializer):
    action = serializers.ChoiceField(choices=["upsert", "delete"])
    annotation = AnnotationUpsertSerializer(required=False)
    client_id = ClientIdField(
        max_length=MAX_ANNOTATION_CLIENT_ID_LENGTH,
        allow_blank=False,
        required=False,
        trim_whitespace=False,
    )

    def validate(self, attrs):
        action = attrs["action"]
        if action == "upsert":
            if "annotation" not in attrs:
                raise serializers.ValidationError(
                    {"annotation": "This field is required for upsert."}
                )
            if "client_id" in attrs:
                raise serializers.ValidationError(
                    {"client_id": "Use annotation.client_id for upsert."}
                )
        elif "client_id" not in attrs:
            raise serializers.ValidationError(
                {"client_id": "This field is required for delete."}
            )
        elif "annotation" in attrs:
            raise serializers.ValidationError(
                {"annotation": "Delete operations cannot include an annotation."}
            )
        return attrs


class AnnotationBatchSerializer(StrictSerializer):
    operations = AnnotationBatchOperationSerializer(
        many=True,
        allow_empty=False,
        max_length=BATCH_ANNOTATION_OPERATION_LIMIT,
    )

    def validate_operations(self, operations):
        client_ids = [
            operation["annotation"]["client_id"]
            if operation["action"] == "upsert"
            else operation["client_id"]
            for operation in operations
        ]
        if len(client_ids) != len(set(client_ids)):
            raise serializers.ValidationError(
                "Each client_id may appear only once per batch."
            )
        return operations


class AnnotationSerializer(serializers.ModelSerializer):
    location = serializers.SerializerMethodField()
    body = serializers.SerializerMethodField()

    class Meta:
        model = Annotation
        fields = [
            "id",
            "client_id",
            "kind",
            "location",
            "body",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_location(self, annotation: Annotation) -> dict:
        return {
            "location": annotation.location,
            "location_label": annotation.location_label,
        }

    def get_body(self, annotation: Annotation) -> dict | None:
        if annotation.kind == Annotation.KIND_BOOKMARK:
            return None
        return {
            "text": annotation.highlight_text,
            "prefix": annotation.quote_prefix,
            "suffix": annotation.quote_suffix,
            "color": annotation.highlight_color or HIGHLIGHT_COLOR_YELLOW,
            "note": annotation.comment_text,
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.kind == Annotation.KIND_BOOKMARK:
            data.pop("body")
        return data


class AnnotationCollectionSerializer(serializers.Serializer):
    annotations = AnnotationSerializer(many=True)

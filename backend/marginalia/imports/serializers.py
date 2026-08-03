from rest_framework import serializers

from marginalia.models import MAX_ANNOTATION_BODY_LENGTH
from marginalia.serializer_fields import StrictSerializer


class MarginaliaImportPreviewSerializer(StrictSerializer):
    file = serializers.FileField(required=True)
    include_empty_sessions = serializers.BooleanField(default=False, required=False)


class MarginaliaImportUnmatchedQuerySerializer(StrictSerializer):
    import_token = serializers.CharField(trim_whitespace=False)


class MarginaliaImportSelectionSerializer(StrictSerializer):
    candidate_id = serializers.CharField(max_length=64)
    name = serializers.CharField(max_length=255, allow_blank=True, required=False)
    notes = serializers.CharField(
        max_length=MAX_ANNOTATION_BODY_LENGTH,
        allow_blank=True,
        required=False,
    )


class MarginaliaImportApplySerializer(StrictSerializer):
    import_token = serializers.CharField(
        min_length=32,
        max_length=128,
        trim_whitespace=False,
    )
    reading_sessions = MarginaliaImportSelectionSerializer(
        many=True,
        allow_empty=False,
    )

    def validate_reading_sessions(self, value):
        candidate_ids = [item["candidate_id"] for item in value]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise serializers.ValidationError(
                "Duplicate candidate IDs are not allowed."
            )
        return value

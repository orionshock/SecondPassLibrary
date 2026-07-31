from rest_framework import serializers

from marginalia.serializer_fields import StrictSerializer


class MarginaliaExportQuerySerializer(StrictSerializer):
    include_empty_sessions = serializers.BooleanField(default=False, required=False)


class MarginaliaSelectedExportSerializer(StrictSerializer):
    reading_session_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
        required=True,
    )
    include_empty_sessions = serializers.BooleanField(default=False, required=False)

    def validate_reading_session_ids(self, values):
        if len(values) != len(set(values)):
            raise serializers.ValidationError(
                "Duplicate Reading Session IDs are not allowed."
            )
        return values

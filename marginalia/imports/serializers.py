from rest_framework import serializers

from marginalia.serializer_fields import StrictSerializer


class MarginaliaImportPreviewSerializer(StrictSerializer):
    file = serializers.FileField(required=True)
    include_empty_sessions = serializers.BooleanField(default=False, required=False)

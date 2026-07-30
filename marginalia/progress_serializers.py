from __future__ import annotations

from rest_framework import serializers

from .models import MAX_CFI_LENGTH, MAX_LOCATION_LABEL_LENGTH, ReadingSession
from .serializer_fields import OpaqueStringField, StrictSerializer


class MarginaliaProgressSerializer(serializers.Serializer):
    cfi = serializers.CharField(source="progress_cfi")
    location_label = serializers.CharField(source="progress_location_label")
    updated_at = serializers.DateTimeField(source="progress_updated_at")


class MarginaliaProgressEnvelopeSerializer(serializers.Serializer):
    progress = MarginaliaProgressSerializer(allow_null=True)


class MarginaliaProgressPutSerializer(StrictSerializer):
    cfi = OpaqueStringField(
        max_length=MAX_CFI_LENGTH,
        allow_blank=False,
        trim_whitespace=False,
    )
    location_label = OpaqueStringField(
        max_length=MAX_LOCATION_LABEL_LENGTH,
        allow_blank=True,
        default="",
        required=False,
        trim_whitespace=False,
    )


class MarginaliaSessionCloseSerializer(StrictSerializer):
    name = serializers.CharField(max_length=255, allow_blank=True, required=False)
    notes = serializers.CharField(allow_blank=True, required=False)
    progress = MarginaliaProgressPutSerializer(required=False)


def progress_envelope(session: ReadingSession) -> dict:
    progress = session if session.progress_cfi else None
    return MarginaliaProgressEnvelopeSerializer({"progress": progress}).data

from __future__ import annotations

from rest_framework import serializers

from .models import ReadingSession
from .serializers import MarginaliaBookSummarySerializer


class MarginaliaProgressSerializer(serializers.Serializer):
    cfi = serializers.CharField(source="progress_cfi")
    location_label = serializers.CharField(source="progress_location_label")
    updated_at = serializers.DateTimeField(source="progress_updated_at")


class MarginaliaSessionDetailSerializer(serializers.ModelSerializer):
    annotation_count = serializers.IntegerField(read_only=True)
    last_activity_at = serializers.DateTimeField(read_only=True)
    progress = serializers.SerializerMethodField()

    def get_progress(self, session: ReadingSession) -> dict | None:
        if not session.progress_cfi:
            return None
        return MarginaliaProgressSerializer(session).data

    class Meta:
        model = ReadingSession
        fields = [
            "id",
            "name",
            "notes",
            "status",
            "started_at",
            "closed_at",
            "updated_at",
            "last_activity_at",
            "annotation_count",
            "progress",
        ]
        read_only_fields = fields


class MarginaliaSessionDetailContextSerializer(serializers.Serializer):
    book = MarginaliaBookSummarySerializer()


class MarginaliaSessionDetailEnvelopeSerializer(serializers.Serializer):
    context = MarginaliaSessionDetailContextSerializer()
    session = MarginaliaSessionDetailSerializer()


class MarginaliaSessionMetadataPatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReadingSession
        fields = ["name", "notes"]
        extra_kwargs = {
            "name": {"required": False},
            "notes": {"required": False},
        }

    def to_internal_value(self, data):
        if hasattr(data, "keys"):
            unknown = sorted(set(data.keys()) - set(self.fields))
            if unknown:
                raise serializers.ValidationError(
                    {field: "Unknown field." for field in unknown}
                )
        return super().to_internal_value(data)

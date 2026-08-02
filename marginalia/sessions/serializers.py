from __future__ import annotations

from rest_framework import serializers

from marginalia.books.serializers import (
    MarginaliaBookSummarySerializer,
    MarginaliaSessionBookReferenceSerializer,
)
from marginalia.models import MAX_CFI_LENGTH, MAX_LOCATION_LABEL_LENGTH, ReadingSession
from marginalia.serializer_fields import OpaqueStringField, StrictSerializer


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


class MarginaliaSessionSummarySerializer(serializers.ModelSerializer):
    annotation_count = serializers.IntegerField(read_only=True)
    last_activity_at = serializers.DateTimeField(read_only=True)

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
        ]
        read_only_fields = fields


class MarginaliaGlobalSessionSummarySerializer(MarginaliaSessionSummarySerializer):
    book = serializers.SerializerMethodField()

    def get_book(self, session: ReadingSession) -> dict:
        return MarginaliaSessionBookReferenceSerializer(
            session.book,
            context={
                "request": self.context.get("request"),
                "can_open": session.can_open,
            },
        ).data

    class Meta(MarginaliaSessionSummarySerializer.Meta):
        fields = [*MarginaliaSessionSummarySerializer.Meta.fields, "book"]
        read_only_fields = fields


class MarginaliaRecentSessionSerializer(serializers.ModelSerializer):
    last_activity_at = serializers.DateTimeField(read_only=True)
    book = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()

    def get_book(self, session: ReadingSession) -> dict:
        return MarginaliaSessionBookReferenceSerializer(
            session.book,
            context={
                "request": self.context.get("request"),
                "can_open": session.can_open,
            },
        ).data

    def get_progress(self, session: ReadingSession) -> dict | None:
        if not session.progress_cfi:
            return None
        return MarginaliaProgressSerializer(session).data

    class Meta:
        model = ReadingSession
        fields = ["id", "name", "status", "last_activity_at", "book", "progress"]
        read_only_fields = fields


class MarginaliaRecentSessionsQuerySerializer(serializers.Serializer):
    limit = serializers.IntegerField(
        min_value=1,
        max_value=50,
        default=10,
        required=False,
    )
    include_closed = serializers.BooleanField(default=False, required=False)


class MarginaliaAnnotationPresenceQuerySerializer(serializers.Serializer):
    has_annotations = serializers.BooleanField(required=False, allow_null=True)


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


class MarginaliaSessionCloseSerializer(StrictSerializer):
    name = serializers.CharField(max_length=255, allow_blank=True, required=False)
    notes = serializers.CharField(allow_blank=True, required=False)
    progress = MarginaliaProgressPutSerializer(required=False)


class MarginaliaOpenSerializer(StrictSerializer):
    name = serializers.CharField(max_length=255, allow_blank=True, required=False)
    notes = serializers.CharField(allow_blank=True, required=False)


class MarginaliaStartOverSerializer(StrictSerializer):
    name = serializers.CharField(max_length=255, allow_blank=True, required=False)
    notes = serializers.CharField(allow_blank=True, required=False)
    progress = MarginaliaProgressPutSerializer(required=False)


def progress_envelope(session: ReadingSession) -> dict:
    progress = session if session.progress_cfi else None
    return MarginaliaProgressEnvelopeSerializer({"progress": progress}).data

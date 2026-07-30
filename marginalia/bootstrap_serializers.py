from rest_framework import serializers

from .progress_serializers import MarginaliaProgressPutSerializer
from .serializer_fields import StrictSerializer


class MarginaliaOpenSerializer(StrictSerializer):
    name = serializers.CharField(max_length=255, allow_blank=True, required=False)
    notes = serializers.CharField(allow_blank=True, required=False)


class MarginaliaStartOverSerializer(StrictSerializer):
    name = serializers.CharField(max_length=255, allow_blank=True, required=False)
    notes = serializers.CharField(allow_blank=True, required=False)
    progress = MarginaliaProgressPutSerializer(required=False)

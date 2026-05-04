from rest_framework import serializers

from .models import UserProfile


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['id', 'role', 'external_subject_id', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class CurrentUserSerializer(serializers.Serializer):
    username = serializers.CharField()
    email = serializers.EmailField(allow_blank=True)
    profile_id = serializers.UUIDField()
    role = serializers.CharField()

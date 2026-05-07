from rest_framework import serializers

from .models import UserProfile


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ["id", "role", "external_subject_id", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class CurrentUserSerializer(serializers.Serializer):
    username = serializers.CharField()
    email = serializers.EmailField(allow_blank=True)
    profile_id = serializers.UUIDField()
    role = serializers.CharField()


class ManagedUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField(allow_blank=True)
    first_name = serializers.CharField(allow_blank=True)
    last_name = serializers.CharField(allow_blank=True)
    is_active = serializers.BooleanField()
    date_joined = serializers.DateTimeField()
    last_login = serializers.DateTimeField(allow_null=True)
    is_owner = serializers.BooleanField()
    profile_id = serializers.UUIDField(allow_null=True)
    role = serializers.CharField(allow_blank=True)


class ManagedUserPatchSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)
    role = serializers.ChoiceField(
        required=False,
        choices=[
            UserProfile.ROLE_MANAGER,
            UserProfile.ROLE_LIBRARIAN,
            UserProfile.ROLE_READER,
        ],
    )

    def validate(self, attrs):
        initial = getattr(self, "initial_data", {}) or {}
        forbidden = {"password", "user_permissions", "groups", "is_superuser", "is_staff", "username"}
        present = forbidden.intersection(set(initial.keys()))
        if present:
            raise serializers.ValidationError({"detail": "This endpoint only supports profile-safe fields."})
        return super().validate(attrs)

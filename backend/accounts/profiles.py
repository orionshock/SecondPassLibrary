from accounts.models import UserProfile


def get_or_create_profile(*, user) -> UserProfile:
    profile, _created = UserProfile.objects.get_or_create(user=user)
    return profile


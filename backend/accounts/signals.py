from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile
from .session_control import WEB_SESSION_GENERATION_KEY


User = get_user_model()


@receiver(post_save, sender=User)
def ensure_user_profile_exists(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)


@receiver(user_logged_in)
def stamp_web_session_generation(sender, request, user, **kwargs):
    if request is None or getattr(request, "session", None) is None:
        return
    generation = UserProfile.objects.values_list(
        "web_session_generation", flat=True
    ).get(user=user)
    request.session[WEB_SESSION_GENERATION_KEY] = generation

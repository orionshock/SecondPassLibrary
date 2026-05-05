from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .group_services import ensure_user_public_membership


User = get_user_model()


@receiver(post_save, sender=User)
def ensure_public_group_membership(sender, instance, created, **kwargs):
    if created:
        ensure_user_public_membership(user=instance)


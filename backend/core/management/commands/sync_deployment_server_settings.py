from django.core.management.base import BaseCommand, CommandError

from core.server_settings import synchronize_deployment_server_settings


class Command(BaseCommand):
    help = "Synchronize environment-owned values into stored Server Settings."

    def handle(self, *args, **options):
        try:
            synchronized = synchronize_deployment_server_settings()
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        if synchronized:
            self.stdout.write("Deployment Server Settings synchronized.")

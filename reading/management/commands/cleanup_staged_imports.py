from django.core.management.base import BaseCommand

from reading.import_staging import cleanup_staged_imports


class Command(BaseCommand):
    help = "Remove expired staged marginalia import preview files."

    def handle(self, *args, **options):
        removed = cleanup_staged_imports()
        self.stdout.write(f"Removed {removed} expired staged marginalia import file(s).")

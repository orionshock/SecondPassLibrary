from django.core.management.base import BaseCommand, CommandError

from library.services import ImportStatus, import_epub


class Command(BaseCommand):
    help = "Import a single EPUB file into the library"

    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str, help="Path to the EPUB file")

    def handle(self, *args, **options):
        file_path = options["file_path"]
        try:
            result = import_epub(file_path)
            if result.status == ImportStatus.DUPLICATE:
                self.stdout.write(
                    self.style.WARNING(f"EPUB already exists: {result.book.title}")
                )
            elif result.status == ImportStatus.IMPORTED:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully imported EPUB: {result.book.title}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"Failed to import EPUB: {result.message or 'Unknown error'}"
                    )
                )
        except ValueError as e:
            raise CommandError(str(e))
        except Exception as e:
            raise CommandError(f"Error importing EPUB: {str(e)}")

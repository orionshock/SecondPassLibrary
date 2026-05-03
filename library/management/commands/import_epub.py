from django.core.management.base import BaseCommand, CommandError

from library.services import import_epub


class Command(BaseCommand):
    help = 'Import a single EPUB file into the library'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Path to the EPUB file')

    def handle(self, *args, **options):
        file_path = options['file_path']
        try:
            book_file, is_duplicate = import_epub(file_path)
            if is_duplicate:
                self.stdout.write(
                    self.style.WARNING(f'EPUB already exists: {book_file.book.title}')
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully imported EPUB: {book_file.book.title}')
                )
        except ValueError as e:
            raise CommandError(str(e))
        except Exception as e:
            raise CommandError(f'Error importing EPUB: {str(e)}')
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
import tempfile
import os
from unittest.mock import patch, MagicMock
from pathlib import Path
import uuid

from django.conf import settings

from .models import Author, Book, BookFile, BookMetadata, Series
from .services import ImportStatus, import_epub


class LibraryModelTest(TestCase):
    def setUp(self):
        self.author = Author.objects.create(name='Test Author')
        self.series = Series.objects.create(name='Test Series')
        self.book = Book.objects.create(title='Test Book')
        self.book.authors.add(self.author)
        self.book.series = self.series
        self.book.series_index = 1
        self.book.save()

    def test_author_str(self):
        self.assertEqual(str(self.author), 'Test Author')

    def test_series_str(self):
        self.assertEqual(str(self.series), 'Test Series')

    def test_book_str(self):
        self.assertEqual(str(self.book), 'Test Book')

    def test_book_multiple_authors(self):
        author2 = Author.objects.create(name='Author 2')
        self.book.authors.add(author2)
        self.assertEqual(self.book.authors.count(), 2)

    def test_book_author_list(self):
        author_a = Author.objects.create(name='A Author')
        author_z = Author.objects.create(name='Z Author')
        self.book.authors.set([author_z, author_a])
        self.assertEqual(self.book.author_list(), 'A Author, Z Author')

    def test_book_metadata(self):
        metadata = BookMetadata.objects.create(book=self.book, publisher='Test Publisher')
        self.assertEqual(str(metadata), 'Metadata for Test Book')

    def test_book_file(self):
        # Note: In a real test, you'd use a test file
        book_file = BookFile.objects.create(
            book=self.book,
            file='test.epub',
            checksum='dummy',
            file_size=123,
            source_filename='original.epub'
        )
        self.assertEqual(str(book_file), 'Test Book - dummy...')
        self.assertEqual(book_file.checksum_short(), 'dummy')
        self.assertEqual(book_file.file_size_human(), '123 B')

    def test_book_file_file_size_human_units(self):
        book_file = BookFile.objects.create(
            book=self.book,
            file='test.epub',
            checksum='a' * 64,
            file_size=2048,
            source_filename='original.epub',
        )
        self.assertEqual(book_file.file_size_human(), '2.0 KB')


class LibraryAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client.login(username='testuser', password='testpass')

    def test_authenticated_access_books(self):
        response = self.client.get('/api/v1/library/books/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_authenticated_access_authors(self):
        response = self.client.get('/api/v1/library/authors/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class EPUBImportTest(TestCase):
    def setUp(self):
        # Create a temporary EPUB file for testing
        temp_root = Path(settings.BASE_DIR) / 'TestFiles'
        temp_root.mkdir(parents=True, exist_ok=True)
        self.temp_dir = str(temp_root / f'tmp_epub_{uuid.uuid4().hex}')
        os.makedirs(self.temp_dir, exist_ok=True)
        self.epub_path = os.path.join(self.temp_dir, 'test.epub')
        with open(self.epub_path, 'wb') as f:
            f.write(uuid.uuid4().hex.encode('utf-8'))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)

    @patch('library.services.epub.read_epub')
    def test_checksum_calculation(self, mock_read_epub):
        mock_book = MagicMock()
        mock_book.get_metadata.return_value = []
        mock_read_epub.return_value = mock_book

        import hashlib
        with open(self.epub_path, 'rb') as f:
            expected_checksum = hashlib.sha256(f.read()).hexdigest()

        result = import_epub(self.epub_path)
        self.assertEqual(result.status, ImportStatus.IMPORTED)
        self.assertEqual(result.checksum, expected_checksum)

    def test_invalid_extension(self):
        invalid_path = os.path.join(self.temp_dir, 'test.txt')
        with open(invalid_path, 'w') as f:
            f.write('not epub')
        with self.assertRaises(ValueError) as cm:
            import_epub(invalid_path)
        self.assertIn('must have .epub extension', str(cm.exception))

    def test_file_not_exists(self):
        non_existent = os.path.join(self.temp_dir, 'nonexistent.epub')
        with self.assertRaises(ValueError) as cm:
            import_epub(non_existent)
        self.assertIn('does not exist', str(cm.exception))

    @patch('library.services.epub.read_epub')
    def test_duplicate_detection(self, mock_read_epub):
        # Mock the epub object
        mock_book = MagicMock()
        mock_book.get_metadata.return_value = []
        mock_read_epub.return_value = mock_book

        # Calculate the actual checksum of the temp file
        import hashlib
        with open(self.epub_path, 'rb') as f:
            checksum = hashlib.sha256(f.read()).hexdigest()

        # Create a BookFile with the same checksum
        book = Book.objects.create(title='Existing Book')
        BookFile.objects.create(
            book=book,
            file='existing.epub',
            checksum=checksum,
            file_size=123,
            source_filename='existing.epub'
        )

        # Try to import again - should return existing
        result = import_epub(self.epub_path)
        self.assertEqual(result.status, ImportStatus.DUPLICATE)
        self.assertEqual(result.checksum, checksum)
        self.assertIsNotNone(result.book_file)
        self.assertIsNotNone(result.book)
        self.assertEqual(result.book.title, 'Existing Book')

    @patch('library.services.epub.read_epub')
    def test_import_minimal_epub(self, mock_read_epub):
        # Mock the epub object with minimal metadata
        mock_book = MagicMock()
        mock_book.get_metadata.side_effect = lambda ns, name: {
            'title': [('Test Title', {})],
            'creator': [('Test Author', {})],
            'language': [('en', {})],
        }.get(name, [])
        mock_read_epub.return_value = mock_book

        import hashlib
        with open(self.epub_path, 'rb') as f:
            expected_checksum = hashlib.sha256(f.read()).hexdigest()

        result = import_epub(self.epub_path)
        self.assertEqual(result.status, ImportStatus.IMPORTED)
        self.assertEqual(result.checksum, expected_checksum)
        self.assertIsNotNone(result.book_file)
        self.assertIsNotNone(result.book)
        self.assertEqual(result.book.title, 'Test Title')
        self.assertEqual(result.book.authors.first().name, 'Test Author')
        self.assertEqual(result.book_file.source_filename, 'test.epub')
        self.assertIsNotNone(result.book_file.file_size)
        self.assertIsNotNone(result.book_file.checksum)
        # Check file path
        expected_path = (
            f'books/{result.book_file.checksum[:2]}/{result.book_file.checksum[2:4]}/{result.book_file.checksum}.epub'
        )
        actual_name = result.book_file.file.name.replace('\\', '/')
        self.assertTrue(actual_name.endswith(expected_path))

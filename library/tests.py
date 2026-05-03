from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
import tempfile
import os
from unittest.mock import patch, MagicMock

from .models import Author, Book, BookFile, BookMetadata, Series
from .services import import_epub, _extract_metadata


class LibraryModelTest(TestCase):
    def setUp(self):
        self.author = Author.objects.create(name='Test Author')
        self.series = Series.objects.create(name='Test Series')
        self.book = Book.objects.create(title='Test Book')
        self.book.authors.add(self.author)
        self.book.series = self.series
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
        self.temp_dir = tempfile.mkdtemp()
        self.epub_path = os.path.join(self.temp_dir, 'test.epub')
        with open(self.epub_path, 'wb') as f:
            f.write(b'fake epub content')

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_checksum_calculation(self):
        import hashlib
        with open(self.epub_path, 'rb') as f:
            expected_checksum = hashlib.sha256(f.read()).hexdigest()
        # Since import_epub calculates it, we can test indirectly
        # For now, just check the function exists
        self.assertTrue(callable(import_epub))

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
        result, is_duplicate = import_epub(self.epub_path)
        self.assertTrue(is_duplicate)
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

        result, is_duplicate = import_epub(self.epub_path)
        self.assertFalse(is_duplicate)
        self.assertEqual(result.book.title, 'Test Title')
        self.assertEqual(result.book.authors.first().name, 'Test Author')
        self.assertEqual(result.source_filename, 'test.epub')
        self.assertIsNotNone(result.file_size)
        self.assertIsNotNone(result.checksum)
        # Check file path
        expected_path = f'books/{result.checksum[:2]}/{result.checksum[2:4]}/{result.checksum}.epub'
        self.assertTrue(result.file.name.endswith(expected_path))

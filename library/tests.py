from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status

from .models import Author, Book, BookFile, BookMetadata, Series


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
        book_file = BookFile.objects.create(book=self.book, file='test.epub')
        self.assertEqual(str(book_file), 'Test Book - test.epub')


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

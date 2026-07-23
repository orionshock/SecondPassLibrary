from django.test import SimpleTestCase
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from core.pagination import DefaultPageNumberPagination


class DefaultPageNumberPaginationTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def paginate(self, *, page_size=None):
        query = {} if page_size is None else {"page_size": page_size}
        request = Request(self.factory.get("/items/", query))
        paginator = DefaultPageNumberPagination()
        return list(paginator.paginate_queryset(list(range(250)), request))

    def test_default_page_size_is_twenty(self):
        self.assertEqual(len(self.paginate()), 20)

    def test_explicit_product_page_sizes_are_preserved(self):
        for page_size in (20, 30, 40, 50, 200):
            with self.subTest(page_size=page_size):
                self.assertEqual(len(self.paginate(page_size=page_size)), page_size)

    def test_page_size_is_capped_at_two_hundred(self):
        self.assertEqual(len(self.paginate(page_size=201)), 200)

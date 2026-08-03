from __future__ import annotations

import warnings

from django.http import HttpResponse, StreamingHttpResponse
from django.test import AsyncRequestFactory, RequestFactory, SimpleTestCase
from rest_framework.response import Response

from core.asgi_streaming import asgi_streaming_response_middleware


class ClosingIterator:
    def __init__(self):
        self._chunks = iter([b"first", b"second"])
        self.closed = False

    def __iter__(self):
        return self

    def __next__(self):
        return next(self._chunks)

    def close(self):
        self.closed = True


class ASGIStreamingResponseMiddlewareTests(SimpleTestCase):
    async def test_asgi_sync_stream_becomes_async_and_retains_cleanup(self):
        source = ClosingIterator()
        original = StreamingHttpResponse(source, content_type="text/plain")

        async def get_response(request):
            return original

        middleware = asgi_streaming_response_middleware(get_response)
        response = await middleware(AsyncRequestFactory().get("/stream/"))

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            content = b"".join([chunk async for chunk in response])
        response.close()

        self.assertIs(response, original)
        self.assertTrue(response.is_async)
        self.assertEqual(content, b"firstsecond")
        self.assertEqual(response["Content-Type"], "text/plain")
        self.assertTrue(source.closed)
        self.assertFalse(
            any("synchronous iterators" in str(item.message) for item in caught)
        )

    async def test_asgi_async_stream_is_unchanged(self):
        async def chunks():
            yield b"already async"

        iterator = chunks()
        original = StreamingHttpResponse(iterator)

        async def get_response(request):
            return original

        middleware = asgi_streaming_response_middleware(get_response)
        response = await middleware(AsyncRequestFactory().get("/stream/"))

        self.assertIs(response, original)
        self.assertTrue(response.is_async)
        self.assertIs(response._iterator, iterator)
        response.close()

    async def test_asgi_buffered_responses_are_unchanged(self):
        responses = [HttpResponse(b"plain"), Response({"status": "ok"})]

        for original in responses:
            with self.subTest(response=type(original).__name__):

                async def get_response(request):
                    return original

                middleware = asgi_streaming_response_middleware(get_response)
                response = await middleware(AsyncRequestFactory().get("/data/"))

                self.assertIs(response, original)
                self.assertFalse(response.streaming)
                response.close()

    def test_wsgi_sync_stream_remains_synchronous(self):
        original = StreamingHttpResponse([b"sync"])

        def get_response(request):
            return original

        middleware = asgi_streaming_response_middleware(get_response)
        response = middleware(RequestFactory().get("/stream/"))

        self.assertIs(response, original)
        self.assertFalse(response.is_async)
        self.assertEqual(b"".join(response.streaming_content), b"sync")

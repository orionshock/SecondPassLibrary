from __future__ import annotations

from collections.abc import Iterator
from itertools import islice

from asgiref.sync import sync_to_async
from django.core.handlers.asgi import ASGIRequest
from django.http import HttpRequest, HttpResponseBase, StreamingHttpResponse
from whitenoise.middleware import WhiteNoiseMiddleware


_ITERATOR_BATCH_SIZE = 16


def use_async_iterator_under_asgi(
    request: HttpRequest,
    response: HttpResponseBase,
) -> HttpResponseBase:
    """Keep a synchronous file iterator off the ASGI event-loop thread."""
    if (
        not isinstance(request, ASGIRequest)
        or not getattr(response, "streaming", False)
        or getattr(response, "is_async", False)
    ):
        return response

    streaming_response = response
    assert isinstance(streaming_response, StreamingHttpResponse)
    iterator = iter(streaming_response.streaming_content)
    streaming_response.streaming_content = _iterate_without_blocking_asgi(iterator)
    return response


async def _iterate_without_blocking_asgi(iterator: Iterator[bytes]):
    next_batch = sync_to_async(_next_batch, thread_sensitive=False)
    while chunks := await next_batch(iterator):
        for chunk in chunks:
            yield chunk


def _next_batch(iterator: Iterator[bytes]) -> list[bytes]:
    return list(islice(iterator, _ITERATOR_BATCH_SIZE))


class AsyncWhiteNoiseMiddleware(WhiteNoiseMiddleware):
    @staticmethod
    def serve(static_file, request):
        response = WhiteNoiseMiddleware.serve(static_file, request)
        return use_async_iterator_under_asgi(request, response)

from __future__ import annotations

from collections.abc import Iterator
from inspect import iscoroutinefunction
from itertools import islice
from typing import cast

from asgiref.sync import sync_to_async
from django.core.handlers.asgi import ASGIRequest
from django.http import HttpRequest, HttpResponseBase, StreamingHttpResponse
from django.utils.decorators import sync_and_async_middleware


_ITERATOR_BATCH_SIZE = 16


def _use_async_iterator_under_asgi(
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

    streaming_response = cast(StreamingHttpResponse, response)
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


@sync_and_async_middleware
def asgi_streaming_response_middleware(get_response):
    if iscoroutinefunction(get_response):

        async def middleware(request):
            response = await get_response(request)
            return _use_async_iterator_under_asgi(request, response)

    else:

        def middleware(request):
            response = get_response(request)
            return _use_async_iterator_under_asgi(request, response)

    return middleware

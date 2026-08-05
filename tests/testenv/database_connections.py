from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from threading import get_ident

from django.db import close_old_connections, connections
from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.backends.signals import connection_created


@contextmanager
def orm_worker_connection_scope() -> Iterator[None]:
    """Own and close every Django database connection used by this worker."""

    owner_thread = get_ident()
    created_connections = []

    def remember_connection(*, connection, **_kwargs):
        if get_ident() == owner_thread and connection not in created_connections:
            created_connections.append(connection)

    connection_created.connect(remember_connection, weak=False)
    try:
        close_old_connections()
        yield
    finally:
        connection_created.disconnect(remember_connection)
        for created_connection in created_connections:
            created_connection.close()
            if (
                created_connection.vendor == "sqlite"
                and created_connection.is_in_memory_db()
                and created_connection.connection is not None
            ):
                # SQLite's backend intentionally ignores close() for shared-memory
                # test databases. The parent thread keeps that database alive, so
                # explicitly close this worker's wrapper through Django's base API.
                BaseDatabaseWrapper.close(created_connection)
        connections.close_all()

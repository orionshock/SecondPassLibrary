from __future__ import annotations

import os
import traceback
from pathlib import Path


class _RollbackProbe(Exception):
    pass


def run_server_settings_worker(database_path: str, pipe, cache_seconds: float) -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "secondpass.settings")
    os.environ.setdefault("DJANGO_SECRET_KEY", "server-settings-worker-test-secret")

    import django

    django.setup()

    from django.core.cache import cache
    from django.db import connection, transaction

    from core.models import ServerSetting
    from core import server_settings
    from core.server_settings import get_server_name, set_server_name

    connection.close()
    connection.settings_dict["NAME"] = Path(database_path)
    server_settings.SERVER_SETTINGS_CACHE_SECONDS = cache_seconds
    cache.clear()

    while True:
        command, value = pipe.recv()
        try:
            if command == "bootstrap":
                with connection.schema_editor() as schema_editor:
                    schema_editor.create_model(ServerSetting)
                result = None
            elif command == "set":
                set_server_name(value)
                result = None
            elif command == "get":
                result = get_server_name()
            elif command == "rollback":
                try:
                    with transaction.atomic():
                        set_server_name(value)
                        raise _RollbackProbe
                except _RollbackProbe:
                    pass
                result = get_server_name()
            elif command == "close":
                pipe.send(("ok", None))
                return
            else:
                raise ValueError(f"Unknown worker command: {command}")
        except Exception:
            pipe.send(("error", traceback.format_exc()))
        else:
            pipe.send(("ok", result))

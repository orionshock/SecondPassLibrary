from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.conf import settings
from jsonschema import Draft202012Validator, ValidationError


SchemaValidationError = ValidationError


def load_marginalia_export_schema() -> dict[str, Any]:
    path = Path(settings.BASE_DIR) / "docs" / "specs" / "marginalia-export.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def assert_valid_marginalia_export(payload: dict[str, Any]) -> None:
    schema = load_marginalia_export_schema()
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)

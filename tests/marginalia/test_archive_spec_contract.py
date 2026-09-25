from __future__ import annotations

import copy
import json

from pathlib import Path
from unittest import TestCase

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from marginalia.archives.serialization import ARCHIVE_SCHEMA_VERSION, ARCHIVE_TYPE
from marginalia.archives.validation import parse_archive
from marginalia.profile import MARGINALIA_PROFILE_URI


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_SCHEMA_PATH = REPOSITORY_ROOT / "backend/marginalia/archives/schema.json"
SPEC_ROOT = REPOSITORY_ROOT / "docs/specs"
PROFILE_SCHEMA_PATH = SPEC_ROOT / "marginalia.schema.json"
EXPORT_SCHEMA_PATH = SPEC_ROOT / "marginalia-export.schema.json"
EXAMPLES_ROOT = SPEC_ROOT / "examples"

VALID_EXAMPLES = {
    "closed-session.json": "profile",
    "complete-export.json": "export",
}
INVALID_EXAMPLES = {"invalid-bookmark-with-body.json"}


class MarginaliaArchiveSpecContractTests(TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        cls.profile_schema = _load_json(PROFILE_SCHEMA_PATH)
        cls.export_schema = _load_json(EXPORT_SCHEMA_PATH)
        cls.runtime_schema = _load_json(RUNTIME_SCHEMA_PATH)

        Draft202012Validator.check_schema(cls.profile_schema)
        Draft202012Validator.check_schema(cls.export_schema)
        Draft202012Validator.check_schema(cls.runtime_schema)

        registry = Registry().with_resource(
            cls.profile_schema["$id"],
            Resource.from_contents(cls.profile_schema),
        )
        cls.profile_validator = Draft202012Validator(
            cls.profile_schema,
            format_checker=FormatChecker(),
        )
        cls.export_validator = Draft202012Validator(
            cls.export_schema,
            registry=registry,
            format_checker=FormatChecker(),
        )

    def test_documentation_schemas_compose_to_runtime_schema(self):
        composed = _compose_documentation_schema(
            export_schema=self.export_schema,
            profile_schema=self.profile_schema,
        )
        difference = _first_difference(
            _semantic_normalize(composed),
            _semantic_normalize(self.runtime_schema),
        )
        if difference is not None:
            self.fail(f"Runtime/documentation archive schema drift: {difference}")

        profile_uri = self.profile_schema["$id"].removesuffix("/schema.json")
        self.assertEqual(
            self.export_schema["properties"]["profile"]["const"],
            profile_uri,
        )
        self.assertEqual(profile_uri, MARGINALIA_PROFILE_URI)
        self.assertEqual(
            self.export_schema["properties"]["schemaVersion"]["const"],
            ARCHIVE_SCHEMA_VERSION,
        )
        self.assertEqual(
            self.export_schema["properties"]["type"]["const"],
            ARCHIVE_TYPE,
        )

    def test_retained_valid_examples_validate_offline(self):
        example_names = {path.name for path in EXAMPLES_ROOT.glob("*.json")}
        self.assertEqual(example_names, {*VALID_EXAMPLES, *INVALID_EXAMPLES})

        for name, schema_name in VALID_EXAMPLES.items():
            value = _load_json(EXAMPLES_ROOT / name)
            validator = (
                self.export_validator
                if schema_name == "export"
                else self.profile_validator
            )
            errors = sorted(validator.iter_errors(value), key=_error_key)
            with self.subTest(example=name):
                self.assertEqual([], errors, _example_error(name, errors))

        complete_export = _load_json(EXAMPLES_ROOT / "complete-export.json")
        parse_archive(json.dumps(complete_export))

    def test_invalid_bookmark_example_fails_body_rule(self):
        name = "invalid-bookmark-with-body.json"
        value = _load_json(EXAMPLES_ROOT / name)
        self.assertTrue(list(self.profile_validator.iter_errors(value)))

        bookmark_schema = {
            "$schema": self.profile_schema["$schema"],
            "$defs": self.profile_schema["$defs"],
            "$ref": "#/$defs/bookmark",
        }
        errors = sorted(
            Draft202012Validator(
                bookmark_schema,
                format_checker=FormatChecker(),
            ).iter_errors(value),
            key=_error_key,
        )
        self.assertTrue(
            any(
                error.validator == "additionalProperties"
                and "body" in error.message
                for error in errors
            ),
            _example_error(name, errors),
        )


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _compose_documentation_schema(*, export_schema: dict, profile_schema: dict):
    composed = copy.deepcopy(export_schema)
    book_schema = composed["properties"]["books"]["items"]
    reading_sessions = book_schema["properties"]["readingSessions"]
    expected_ref = f'{profile_schema["$id"]}#/$defs/readingSession'
    if reading_sessions["items"] != {"$ref": expected_ref}:
        raise AssertionError(
            "Documentation export schema must reference the normative profile "
            f"Reading Session definition: expected {expected_ref!r}."
        )

    reading_sessions["items"] = {"$ref": "#/$defs/readingSession"}
    composed["properties"]["books"]["items"] = {"$ref": "#/$defs/book"}
    composed["$defs"] = copy.deepcopy(profile_schema["$defs"])
    composed["$defs"]["book"] = book_schema
    return composed


def _semantic_normalize(value, *, parent_key: str = ""):
    if isinstance(value, dict):
        return {
            key: _semantic_normalize(item, parent_key=key)
            for key, item in value.items()
        }
    if isinstance(value, list):
        normalized = [_semantic_normalize(item) for item in value]
        if parent_key in {"allOf", "anyOf", "enum", "oneOf", "required", "type"}:
            return sorted(
                normalized,
                key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
            )
        return normalized
    return value


def _first_difference(expected, actual, *, path: str = "$") -> str | None:
    if type(expected) is not type(actual):
        return f"{path}: docs type {type(expected).__name__}, runtime type {type(actual).__name__}"
    if isinstance(expected, dict):
        expected_keys = set(expected)
        actual_keys = set(actual)
        if expected_keys != actual_keys:
            return (
                f"{path}: docs-only keys {sorted(expected_keys - actual_keys)!r}, "
                f"runtime-only keys {sorted(actual_keys - expected_keys)!r}"
            )
        for key in sorted(expected):
            difference = _first_difference(
                expected[key],
                actual[key],
                path=f"{path}.{key}",
            )
            if difference is not None:
                return difference
        return None
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return f"{path}: docs length {len(expected)}, runtime length {len(actual)}"
        for index, (expected_item, actual_item) in enumerate(zip(expected, actual)):
            difference = _first_difference(
                expected_item,
                actual_item,
                path=f"{path}[{index}]",
            )
            if difference is not None:
                return difference
        return None
    if expected != actual:
        return f"{path}: docs {expected!r}, runtime {actual!r}"
    return None


def _error_key(error) -> tuple[str, str, str]:
    return (_json_path(error.absolute_path), str(error.validator), error.message)


def _example_error(name: str, errors) -> str:
    if not errors:
        return f"{name}: expected a schema validation failure."
    details = "; ".join(
        f"{_json_path(error.absolute_path)} [{error.validator}]: {error.message}"
        for error in errors
    )
    return f"{name}: {details}"


def _json_path(parts) -> str:
    path = "$"
    for part in parts:
        path += f"[{part}]" if isinstance(part, int) else f".{part}"
    return path

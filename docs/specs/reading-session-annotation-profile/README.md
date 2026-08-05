# Reading Session and Annotation Profile

This directory contains the reusable Marginalia interchange profile for Reader
clients and portable archives.

Current profile URI:

```text
https://secondpasslibrary.local/specs/marginalia/0.1.0
```

## Authorities

- [schema.json](schema.json) is the normative machine-readable schema for
  Sessions, progress, locations, highlights, and bookmarks.
- [profile.md](profile.md) defines semantic rules that JSON Schema cannot state
  clearly, including identity, ordering, deletion, and lifecycle meaning.
- [marginalia-export.schema.json](../marginalia-export.schema.json) is the
  normative archive envelope and references this profile.
- [marginalia-export.md](../marginalia-export.md) explains envelope identity and
  packaging.

The JSON Schemas are the only machine-readable interchange authority. Product
UI SDK models describe live API data and are not portable archive types.

## Examples

- [complete-export.json](examples/complete-export.json) is the canonical valid
  end-to-end archive.
- [closed-session.json](examples/closed-session.json) is a valid illustrative
  standalone Session showing the closed-state condition and null progress.
- [invalid-bookmark-with-body.json](examples/invalid-bookmark-with-body.json) is
  intentionally invalid and must fail because bookmarks cannot contain `body`.

`tests/marginalia/test_archive_spec_contract.py` validates this exact fixture
set offline and checks semantic parity between both normative schemas and the
runtime bundled schema.

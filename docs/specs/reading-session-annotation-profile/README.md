# Second Pass Library Marginalia Profile

This directory is the canonical specification for Marginalia communication
between Second Pass Library and Reader clients.

Profile URI:

```text
https://secondpasslibrary.local/specs/marginalia/0.1.0
```

Files:

- `profile.md` — normative domain and interchange contract.
- `schema.json` — documentation schema for shared Session, progress, location,
  highlight, and bookmark shapes, including explicit portable identities.
- `types.ts` — matching TypeScript reference types.
- `examples/` — concise canonical examples, including a complete archive.

The export envelope is documented in `../marginalia-export.md` and
`../marginalia-export.schema.json`. It references the shared definitions here;
it does not define another annotation or Session model.

Files under `docs/` are documentation only. Runtime code and tests must not load
or validate them.

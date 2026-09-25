# EPUB Location Profile

## Status and syntax

This is the currently supported durable location profile for EPUB Books.
Locations are self-describing strings using the `epubcfi(...)` wrapper.

The accepted subset contains:

- compact structural EPUB CFI paths;
- character offsets;
- simple three-part ranges;
- element ID assertions on structural steps.

The first step is a positive even package-spine step. Later slash-prefixed
steps and terminal `:N` offsets use nonnegative decimal integers without
leading zeros, except `0`. Each `!` is followed by structural steps. A range
has one absolute parent path and two relative endpoints, each a structural path
with an optional character offset or a bare character offset. Range endpoints
do not contain indirection.

The profile rejects:

- text-location assertions after character offsets;
- temporal offsets;
- spatial offsets;
- unsupported parameters or extensions;
- malformed syntax or escapes.

Element IDs must be XML names without a colon. Second Pass policy limits each
ID assertion to 128 characters and all ID assertions in one CFI to 256
characters total. Those are compactness limits imposed by Second Pass, not
limits from the EPUB CFI specification.

## Runtime behavior

The server performs syntax/profile validation only. It does not resolve the
CFI against an EPUB or DOM, normalize it, repair it, or assign numeric meaning
to it. Accepted values are stored byte-for-byte unchanged.

Selected Book text and quote-recovery context belong in annotation `text`,
`prefix`, and `suffix`, never inside the location. The accepted subset is based
on the [EPUB CFI grammar](https://idpf.org/epub/linking/cfi/#sec-syntax).

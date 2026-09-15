from __future__ import annotations


TEXT_EXTS = {
    ".py",
    ".md",
    ".txt",
    ".html",
    ".css",
    ".js",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
}

MOJIBAKE_MARKERS = ("\u00c3", "\u00c2", "\u00e2")

# Keep this source ASCII-only so text repair never becomes its own test case.
PUNCT_REPLACEMENTS: dict[str, str] = {
    "\u2026": "...",
    "\u2014": "-",
    "\u2013": "-",
    "\u2019": "'",
    "\u2018": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u00a0": " ",
}

MOJIBAKE_SEQ_REPLACEMENTS: dict[str, str] = {
    "\u00e2\u20ac\u00a6": "...",
    "\u00e2\u20ac\u201d": "-",
    "\u00e2\u20ac\u201c": "-",
    "\u00e2\u20ac\u2122": "'",
    "\u00e2\u20ac\u02dc": "'",
    "\u00e2\u20ac\u0153": '"',
    "\u00e2\u20ac\u009d": '"',
    "\u00e2\u20ac\u017e": '"',
    "\u00c2\u00a0": " ",
    "\u00c2\u00b7": "-",
}


def decode_best_effort(data: bytes) -> str | None:
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def fix_mojibake_text(text: str) -> str:
    candidate = text
    if any(marker in text for marker in MOJIBAKE_MARKERS):
        for encoding in ("cp1252", "latin-1"):
            try:
                candidate = text.encode(encoding).decode("utf-8")
                break
            except UnicodeError:
                continue

    for source, replacement in MOJIBAKE_SEQ_REPLACEMENTS.items():
        candidate = candidate.replace(source, replacement)

    for source, replacement in PUNCT_REPLACEMENTS.items():
        candidate = candidate.replace(source, replacement)

    return candidate.replace("\r\n", "\n").replace("\r", "\n")


def has_mojibake_marker(text: str) -> bool:
    return any(marker in text for marker in MOJIBAKE_MARKERS)

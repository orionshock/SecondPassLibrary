"""Operator-declared base URLs for this Library deployment."""

from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.validators import URLValidator


def parse_library_urls(raw: str) -> list[str]:
    if not raw.strip():
        return []

    urls: list[str] = []
    seen: set[tuple[str, str, int | None]] = set()
    validator = URLValidator(schemes=["http", "https"])
    for part in raw.split(","):
        url = part.strip()
        try:
            if (
                not url
                or len(url) > 2048
                or any(ord(char) < 32 for char in part)
                or any(char.isspace() for char in url)
            ):
                raise ValueError
            if not url.startswith(("http://", "https://")):
                raise ValueError
            parsed = urlsplit(url)
            if (
                not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path not in ("", "/")
                or "?" in url
                or "#" in url
            ):
                raise ValueError
            port = parsed.port
            if port == 0:
                raise ValueError
            validator(url)
        except (ValueError, ValidationError) as exc:
            raise ImproperlyConfigured(
                "SECOND_PASS_LIBRARY_URLS must contain comma-separated HTTP(S) base URLs."
            ) from exc

        canonical = url.removesuffix("/")
        effective_port = port or (443 if parsed.scheme == "https" else 80)
        identity = (parsed.scheme, parsed.hostname.lower(), effective_port)
        if identity not in seen:
            seen.add(identity)
            urls.append(canonical)
    return urls

from __future__ import annotations

import sys


SUPPORTED_PYTHON = (3, 14)


def require_supported_python() -> None:
    running = sys.version_info[:2]
    if running != SUPPORTED_PYTHON:
        required = ".".join(map(str, SUPPORTED_PYTHON))
        actual = ".".join(map(str, running))
        raise RuntimeError(
            f"Second Pass Library requires Python {required}.x; running {actual}."
        )


if __name__ == "__main__":
    try:
        require_supported_python()
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from None

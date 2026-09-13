"""Probe the web service using a configured allowed host."""

import os
import urllib.request


def main():
    host = os.environ["DJANGO_ALLOWED_HOSTS"].split(",")[0].strip()
    request = urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/health/", headers={"Host": host}
    )
    with urllib.request.urlopen(request, timeout=3) as response:
        response.read()


if __name__ == "__main__":
    main()

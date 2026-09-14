from datetime import datetime, timezone


SERVER_VERSION = "live-dev-env"
SERVER_RELEASE_DATE = datetime.now(timezone.utc).date().isoformat()

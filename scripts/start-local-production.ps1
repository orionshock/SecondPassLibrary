$ErrorActionPreference = "Stop"

$PythonExecutable = "python"
$UvicornHost = "127.0.0.1"
$UvicornPort = 8000
$ProjectRoot = Split-Path -Parent $PSScriptRoot

$env:DJANGO_SETTINGS_MODULE = "secondpass.settings"
$env:DJANGO_DEBUG = "0"
$env:DJANGO_SECRET_KEY = "secondpass-local-production-mode-not-for-real-deployments"
$env:DJANGO_TIME_ZONE = "America/Phoenix"
$env:DJANGO_ALLOWED_HOSTS = "localhost,127.0.0.1,[::1]"
$env:DJANGO_CSRF_TRUSTED_ORIGINS = "http://localhost:8000,http://127.0.0.1:8000"
$env:DJANGO_SECURE_COOKIES = "0"
$env:DJANGO_TRUST_X_FORWARDED_PROTO = "0"
$env:DJANGO_USE_X_FORWARDED_HOST = "0"
$env:DJANGO_SILENCED_SYSTEM_CHECKS = "security.W004,security.W008,security.W012,security.W016"
$env:SECOND_PASS_ENABLE_DJANGO_ADMIN = "1"
$env:SECOND_PASS_ENABLE_WHITENOISE = "1"
$env:SECOND_PASS_USERDATA_DIR = Join-Path $ProjectRoot "userdata"
$env:SECOND_PASS_SERVER_VERSION = "0.1.0-dev"
$env:SECOND_PASS_SERVER_RELEASE = "pre-release"
$env:SECOND_PASS_SERVER_RELEASE_DATE = "2026-07-03"

Push-Location $ProjectRoot
try {
    & $PythonExecutable manage.py check --deploy
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & $PythonExecutable manage.py migrate --noinput
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & $PythonExecutable manage.py collectstatic --noinput
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    $UvicornArgs = @(
        "secondpass.asgi:application",
        "--host", $UvicornHost,
        "--port", $UvicornPort,
        "--workers", "1",
        "--no-access-log"
    )

    & $PythonExecutable -m uvicorn @UvicornArgs
    exit $LASTEXITCODE
} finally {
    Pop-Location
}

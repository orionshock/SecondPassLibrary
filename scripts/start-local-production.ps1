$ErrorActionPreference = "Stop"

$PythonExecutable = if ($env:PYTHON) { $env:PYTHON } else { "python" }
$Bind = if ($env:BIND) { $env:BIND } else { "127.0.0.1:8000" }
$WaitressThreads = if ($env:WAITRESS_THREADS) { $env:WAITRESS_THREADS } else { "4" }
$ProjectRoot = Split-Path -Parent $PSScriptRoot

$env:DJANGO_DEBUG = "0"
$env:SECOND_PASS_ENABLE_WHITENOISE = "1"
$env:DJANGO_SECRET_KEY = "secondpass-local-production-mode-not-for-real-deployments"
$env:DJANGO_ALLOWED_HOSTS = "localhost,127.0.0.1,[::1]"
$env:DJANGO_CSRF_TRUSTED_ORIGINS = "http://localhost:8000,http://127.0.0.1:8000"
$env:DJANGO_SECURE_COOKIES = "0"
$env:DJANGO_TRUST_X_FORWARDED_PROTO = "0"
$env:DJANGO_USE_X_FORWARDED_HOST = "0"
$env:SECOND_PASS_ENABLE_DJANGO_ADMIN = "1"
$env:DJANGO_SILENCED_SYSTEM_CHECKS = "security.W004,security.W008,security.W012,security.W016"

Write-Host "SECOND_PASS_ENABLE_DJANGO_ADMIN=$env:SECOND_PASS_ENABLE_DJANGO_ADMIN"

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

    $WaitressArgs = @(
        "--listen=$Bind",
        "--threads=$WaitressThreads",
        "secondpass.wsgi:application"
    )

    & $PythonExecutable -m waitress @WaitressArgs
    exit $LASTEXITCODE
} finally {
    Pop-Location
}

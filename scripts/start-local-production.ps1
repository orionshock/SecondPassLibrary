$ErrorActionPreference = "Stop"

$PythonExecutable = if ($env:PYTHON) { $env:PYTHON } else { "python" }
$Bind = if ($env:BIND) { $env:BIND } else { "127.0.0.1:8000" }
$ProjectRoot = Split-Path -Parent $PSScriptRoot

if ($Bind -match "[\[\]]" -or $Bind -notmatch "^(?<Host>[^\s:]+):(?<Port>[0-9]+)$") {
    [Console]::Error.WriteLine("BIND must use host:port syntax with a hostname or IPv4 address; IPv6 is not supported by this helper. Received: $Bind")
    exit 1
}

$UvicornHost = $Matches.Host
$UvicornPort = 0
if (-not [int]::TryParse($Matches.Port, [ref]$UvicornPort) -or $UvicornPort -lt 1 -or $UvicornPort -gt 65535) {
    [Console]::Error.WriteLine("BIND port must be an integer from 1 through 65535. Received: $Bind")
    exit 1
}

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

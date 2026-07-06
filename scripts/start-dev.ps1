$ErrorActionPreference = "Stop"

$PythonExecutable = if ($env:PYTHON) { $env:PYTHON } else { "python" }
$ProjectRoot = Split-Path -Parent $PSScriptRoot

$env:DJANGO_DEBUG = "1"
$env:SECOND_PASS_ENABLE_WHITENOISE = "0"
$env:DJANGO_ALLOWED_HOSTS = "localhost,127.0.0.1,[::1]"

Push-Location $ProjectRoot
try {
    & $PythonExecutable manage.py migrate --noinput
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & $PythonExecutable manage.py runserver @args
    exit $LASTEXITCODE
} finally {
    Pop-Location
}

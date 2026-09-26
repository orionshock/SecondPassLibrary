$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonExecutable = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$ManagePy = Join-Path $ProjectRoot "backend\manage.py"
$SeedArgs = @("seed_dev_users")
$PythonRuntimeCheck = Join-Path $ProjectRoot "tools\python_runtime.py"

& $PythonExecutable $PythonRuntimeCheck
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$env:DJANGO_SETTINGS_MODULE = "secondpass.settings"
$env:DJANGO_DEBUG = "1"
$env:DJANGO_SECRET_KEY = "secondpass-local-development-only"
$env:DJANGO_TIME_ZONE = "UTC"
$env:DJANGO_ALLOWED_HOSTS = "localhost,127.0.0.1,[::1]"
$env:DJANGO_CSRF_TRUSTED_ORIGINS = "http://localhost:8000,http://127.0.0.1:8000"
$env:DJANGO_SECURE_COOKIES = "0"
$env:DJANGO_TRUST_X_FORWARDED_PROTO = "0"
$env:DJANGO_USE_X_FORWARDED_HOST = "0"
$env:DJANGO_SILENCED_SYSTEM_CHECKS = ""
$env:SECOND_PASS_ENABLE_DJANGO_ADMIN = "1"
$env:SECOND_PASS_ENABLE_WHITENOISE = "0"
$env:SECOND_PASS_USERDATA_DIR = Join-Path $ProjectRoot "userdata"

$SeedArgs += $args

Push-Location $ProjectRoot
try {
    & $PythonExecutable $ManagePy @SeedArgs
    exit $LASTEXITCODE
} finally {
    Pop-Location
}

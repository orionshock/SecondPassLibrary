$ErrorActionPreference = "Stop"

$PythonExecutable = if ($env:PYTHON) { $env:PYTHON } else { "python" }
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$SeedArgs = @("seed_dev_users")

# An ordinary interactive shell is a development context unless the caller
# explicitly selected production settings.
if ([string]::IsNullOrWhiteSpace($env:DJANGO_DEBUG)) {
    $env:DJANGO_DEBUG = "1"
}

# The management command requires --force when run with production settings.
# Production configuration, including DJANGO_SECRET_KEY, remains caller-owned.
if ($env:DJANGO_DEBUG -eq "0") {
    $SeedArgs += "--force"
}
$SeedArgs += $args

Push-Location $ProjectRoot
try {
    & $PythonExecutable manage.py @SeedArgs
    exit $LASTEXITCODE
} finally {
    Pop-Location
}

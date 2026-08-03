$ErrorActionPreference = "Stop"

$PythonExecutable = "python"
$NpmExecutable = "npm.cmd"
$UvicornHost = "127.0.0.1"
$UvicornPort = 8000
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $ProjectRoot "backend"
$FrontendRoot = Join-Path $ProjectRoot "frontend"
$ManagePy = Join-Path $BackendRoot "manage.py"
$ProductUiAssets = Join-Path $BackendRoot "web\product_ui\assets"
$ReactPackage = Join-Path $FrontendRoot "package.json"
$ReactVitePackage = Join-Path $FrontendRoot "node_modules\vite\package.json"

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

Push-Location $ProjectRoot
try {
    if (-not (Test-Path -LiteralPath $ReactPackage -PathType Leaf)) {
        Write-Error "React workspace is missing at '$FrontendRoot'."
    }

    if (-not (Test-Path -LiteralPath $ReactVitePackage -PathType Leaf)) {
        Write-Error "React dependencies are missing. Run 'npm.cmd install' from '$FrontendRoot'."
    }

    Push-Location $FrontendRoot
    try {
        & $NpmExecutable run build
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
    } finally {
        Pop-Location
    }

    & $PythonExecutable $ManagePy check --deploy
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & $PythonExecutable $ManagePy migrate --noinput
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & $PythonExecutable $ManagePy collectstatic --noinput
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    if (Test-Path -LiteralPath $ProductUiAssets -PathType Container) {
        Remove-Item -LiteralPath $ProductUiAssets -Recurse -Force
    }

    $UvicornArgs = @(
        "secondpass.asgi:application",
        "--host", $UvicornHost,
        "--port", $UvicornPort,
        "--workers", "1",
        "--no-access-log"
    )

    Push-Location $BackendRoot
    try {
        & $PythonExecutable -m uvicorn @UvicornArgs
        exit $LASTEXITCODE
    } finally {
        Pop-Location
    }
} finally {
    Pop-Location
}

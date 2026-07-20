$ErrorActionPreference = "Stop"

$PythonExecutable = "python"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ReactRoot = Join-Path $ProjectRoot "web\react"
$ViteEntrypoint = Join-Path $ReactRoot "node_modules\vite\bin\vite.js"

$env:DJANGO_SETTINGS_MODULE = "secondpass.settings"
$env:DJANGO_DEBUG = "1"
$env:DJANGO_SECRET_KEY = "secondpass-local-development-only"
$env:DJANGO_TIME_ZONE = "America/Phoenix"
$env:DJANGO_ALLOWED_HOSTS = "localhost,127.0.0.1,[::1]"
$env:DJANGO_CSRF_TRUSTED_ORIGINS = "http://localhost:8000,http://127.0.0.1:8000,http://localhost:5174,http://127.0.0.1:5174"
$env:DJANGO_SECURE_COOKIES = "0"
$env:DJANGO_TRUST_X_FORWARDED_PROTO = "0"
$env:DJANGO_USE_X_FORWARDED_HOST = "0"
$env:DJANGO_SILENCED_SYSTEM_CHECKS = ""
$env:SECOND_PASS_ENABLE_DJANGO_ADMIN = "1"
$env:SECOND_PASS_ENABLE_WHITENOISE = "0"
$env:SECOND_PASS_USERDATA_DIR = Join-Path $ProjectRoot "userdata"

$ViteProcess = $null

Push-Location $ProjectRoot
try {
    & $PythonExecutable manage.py migrate --noinput
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    if (-not (Test-Path -LiteralPath $ViteEntrypoint -PathType Leaf)) {
        Write-Error "React dependencies are missing. Run 'npm.cmd install' from '$ReactRoot'."
    }

    $NodeExecutable = (Get-Command node -ErrorAction Stop).Source
    $ViteProcess = Start-Process `
        -FilePath $NodeExecutable `
        -ArgumentList $ViteEntrypoint `
        -WorkingDirectory $ReactRoot `
        -NoNewWindow `
        -PassThru

    Write-Host "React UI: http://localhost:5174"
    Write-Host "Django:  http://localhost:8000"

    & $PythonExecutable manage.py runserver @args
    exit $LASTEXITCODE
} finally {
    if ($null -ne $ViteProcess -and -not $ViteProcess.HasExited) {
        Stop-Process -Id $ViteProcess.Id
        $ViteProcess.WaitForExit()
    }
    Pop-Location
}

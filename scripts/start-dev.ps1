$ErrorActionPreference = "Stop"

$PythonExecutable = "python"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $ProjectRoot "backend"
$FrontendRoot = Join-Path $ProjectRoot "frontend"
$ManagePy = Join-Path $BackendRoot "manage.py"
$ViteEntrypoint = Join-Path $FrontendRoot "node_modules\vite\bin\vite.js"
$PythonRuntimeCheck = Join-Path $ProjectRoot "tools\python_runtime.py"

& $PythonExecutable $PythonRuntimeCheck
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

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
$HueyProcess = $null

Push-Location $ProjectRoot
try {
    & $PythonExecutable $ManagePy migrate --noinput
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    if (-not (Test-Path -LiteralPath $ViteEntrypoint -PathType Leaf)) {
        Write-Error "React dependencies are missing. Run 'npm.cmd install' from '$FrontendRoot'."
    }

    $NodeExecutable = (Get-Command node -ErrorAction Stop).Source
    $ViteProcess = Start-Process `
        -FilePath $NodeExecutable `
        -ArgumentList $ViteEntrypoint `
        -WorkingDirectory $FrontendRoot `
        -NoNewWindow `
        -PassThru

    $HueyProcess = Start-Process `
        -FilePath $PythonExecutable `
        -ArgumentList "manage.py", "run_huey" `
        -WorkingDirectory $BackendRoot `
        -NoNewWindow `
        -PassThru

    Write-Host "React UI: http://localhost:5174"
    Write-Host "Django:  http://localhost:8000"
    Write-Host "Huey:    maintenance worker running"

    & $PythonExecutable $ManagePy runserver @args
    exit $LASTEXITCODE
} finally {
    if ($null -ne $HueyProcess -and -not $HueyProcess.HasExited) {
        Stop-Process -Id $HueyProcess.Id
        $HueyProcess.WaitForExit()
    }
    if ($null -ne $ViteProcess -and -not $ViteProcess.HasExited) {
        Stop-Process -Id $ViteProcess.Id
        $ViteProcess.WaitForExit()
    }
    Pop-Location
}

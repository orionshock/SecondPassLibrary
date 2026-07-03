$ErrorActionPreference = "Stop"

$PythonExecutable = if ($env:PYTHON) { $env:PYTHON } else { "python" }
$Bind = if ($env:BIND) { $env:BIND } else { "0.0.0.0:8000" }
$WaitressThreads = if ($env:WAITRESS_THREADS) { $env:WAITRESS_THREADS } else { "4" }
$ProjectRoot = Split-Path -Parent $PSScriptRoot

$env:DJANGO_DEBUG = "0"

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

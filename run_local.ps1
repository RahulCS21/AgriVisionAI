$ErrorActionPreference = "Stop"
$env:AGRIVISION_ENV = "development"

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

$adminConfig = Join-Path $PSScriptRoot "instance\local_admin.json"
if (-not (Test-Path $adminConfig)) {
    & $python (Join-Path $PSScriptRoot "scripts\create_local_admin.py")
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

& $python (Join-Path $PSScriptRoot "app.py")
exit $LASTEXITCODE

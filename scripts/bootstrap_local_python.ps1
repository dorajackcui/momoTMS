param(
    [Parameter(Mandatory = $true)]
    [string]$PythonHome,

    [string]$TargetDir = ".python-home",

    [switch]$SkipVenv
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$source = (Resolve-Path $PythonHome).Path
$target = Join-Path $repoRoot $TargetDir

if (-not (Test-Path (Join-Path $source "python.exe"))) {
    throw "python.exe not found under $source"
}

Write-Host "Copying Python from $source to $target"
if (Test-Path $target) {
    Remove-Item -Recurse -Force $target
}

New-Item -ItemType Directory -Force $target | Out-Null
$null = robocopy $source $target /E /NFL /NDL /NJH /NJS /NP
if ($LASTEXITCODE -ge 8) {
    throw "robocopy failed with exit code $LASTEXITCODE"
}

if ($SkipVenv) {
    Write-Host "Python copied. Skipping venv creation."
    exit 0
}

$venvDir = Join-Path $repoRoot ".venv"
if (Test-Path $venvDir) {
    Remove-Item -Recurse -Force $venvDir
}

$workspacePython = Join-Path $target "python.exe"
Write-Host "Creating virtualenv from $workspacePython"
& $workspacePython -m venv $venvDir

Write-Host "Done. Use .\.venv\\Scripts\\python.exe from now on."

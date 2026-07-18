<#
.SYNOPSIS
    sonpipe installer for Windows.

.DESCRIPTION
    Installs the sonpipe command-line tool (and CED's sonpy) into an isolated
    Python virtual environment under %LOCALAPPDATA%\sonpipe, verifies the
    install, and prints the line you need to wire sonpipe into MATLAB.
    Optionally adds the venv's Scripts directory to your user PATH.

    On Windows, CED ships sonpy wheels for Python 3.9 - 3.14, so any of those
    interpreters will work.

.PARAMETER Venv
    Virtual environment location (default: %LOCALAPPDATA%\sonpipe\venv).

.PARAMETER Python
    Python launcher/interpreter to use (default: "py -3", falling back to
    "python").

.PARAMETER Source
    Path or pip spec to install (default: the repo if run inside it, else
    "sonpipe" from PyPI).

.PARAMETER Pypi
    Force installing "sonpipe" from PyPI.

.PARAMETER AddToPath
    Persistently add the venv Scripts directory to your user PATH.

.EXAMPLE
    ./install.ps1 -AddToPath
#>

[CmdletBinding()]
param(
    [string]$Venv,
    [string]$Python,
    [string]$Source,
    [switch]$Pypi,
    [switch]$AddToPath
)

$ErrorActionPreference = 'Stop'

function Info($m)  { Write-Host "[sonpipe] $m" -ForegroundColor Cyan }
function Warn($m)  { Write-Host "[sonpipe] WARNING: $m" -ForegroundColor Yellow }
function Fail($m)  { Write-Host "[sonpipe] ERROR: $m" -ForegroundColor Red; exit 1 }

if (-not $Venv) { $Venv = Join-Path $env:LOCALAPPDATA 'sonpipe\venv' }

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Choose the Python command.
$pyCmd = $null
if ($Python) {
    $pyCmd = $Python
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pyCmd = 'py -3'
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pyCmd = 'python'
} else {
    Fail "No Python found. Install Python 3 (https://www.python.org/downloads/) and retry."
}
Info "Using Python command: $pyCmd"

# Decide what to install.
if (-not $Source) {
    if ($Pypi) {
        $Source = 'sonpipe'
    } elseif (Test-Path (Join-Path $ScriptDir 'pyproject.toml')) {
        $Source = $ScriptDir
    } else {
        $Source = 'sonpipe'
    }
}
Info "Installing from: $Source"

# Create the venv.
Info "Creating virtual environment: $Venv"
$venvParent = Split-Path -Parent $Venv
if (-not (Test-Path $venvParent)) { New-Item -ItemType Directory -Force -Path $venvParent | Out-Null }
Invoke-Expression "$pyCmd -m venv `"$Venv`""

$PY = Join-Path $Venv 'Scripts\python.exe'
if (-not (Test-Path $PY)) { Fail "venv python not found at $PY" }

Info "Upgrading pip"
& $PY -m pip install --upgrade pip | Out-Null

Info "Installing sonpipe (also fetches CED's sonpy from PyPI)"
& $PY -m pip install $Source

# Verify.
Info "Verifying sonpipe CLI ..."
& $PY -m sonpipe --version
if ($LASTEXITCODE -ne 0) { Fail "sonpipe did not install correctly." }

Info "Verifying CED sonpy import ..."
& $PY -c "import sonpy; print('sonpy', sonpy.__version__)"
$sonpyOk = ($LASTEXITCODE -eq 0)
if (-not $sonpyOk) {
    Warn "sonpy could not be imported -- no sonpy wheel for this Python. Try a"
    Warn "different Python 3.x (CED ships Windows wheels for 3.9 - 3.14)."
}

$Cmd = Join-Path $Venv 'Scripts\sonpipe.exe'
$ScriptsDir = Join-Path $Venv 'Scripts'

if ($AddToPath) {
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    if ($userPath -notlike "*$ScriptsDir*") {
        [Environment]::SetEnvironmentVariable('Path', "$userPath;$ScriptsDir", 'User')
        Info "Added $ScriptsDir to your user PATH (restart your shell to pick it up)."
    }
}

Write-Host ""
Info "Done."
Write-Host "  Command: `"$Cmd`" --help"
Write-Host "  MATLAB:  add the repo's 'matlab' folder to your path, then run:"
Write-Host "             sonpipe.executable('$Cmd')"
if (-not $sonpyOk) { exit 1 }

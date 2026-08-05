[CmdletBinding()]
param(
    [string]$ProjectRoot = "C:\Users\22602\Desktop\test",
    [string]$OfflineLayout,
    [switch]$SkipBuildTools,
    [switch]$SkipChromaInstall
)

$ErrorActionPreference = "Stop"

function Get-VsInstaller {
    $installer = Join-Path $env:TEMP "vs_BuildTools.exe"
    if (-not (Test-Path -LiteralPath $installer)) {
        Write-Host "Downloading the official Visual Studio 2022 Build Tools installer..."
        Invoke-WebRequest -Uri "https://aka.ms/vs/17/release/vs_BuildTools.exe" -OutFile $installer
    }
    return $installer
}

function Import-VcVarsEnvironment([string]$VcVarsPath) {
    if (-not (Test-Path -LiteralPath $VcVarsPath)) {
        throw "vcvars64.bat was not found: $VcVarsPath"
    }

    # A child cmd.exe cannot mutate the parent PowerShell process directly.
    # Export its environment and import the variables into this session.
    $output = cmd.exe /d /s /c ('call "' + $VcVarsPath + '" && set')
    foreach ($line in $output) {
        if ($line -match '^(.*?)=(.*)$') {
            Set-Item -Path ("Env:" + $matches[1]) -Value $matches[2]
        }
    }

    if (-not (Get-Command cl.exe -ErrorAction SilentlyContinue)) {
        throw "The MSVC compiler was not added to PATH after loading vcvars64.bat."
    }
    Write-Host "MSVC compiler: $((Get-Command cl.exe).Source)"
}

function Find-VcVars64 {
    $vsWhereCandidates = @(
        "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe",
        "$env:ProgramFiles\Microsoft Visual Studio\Installer\vswhere.exe"
    )
    $vsWhere = $vsWhereCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $vsWhere) {
        throw "vswhere.exe was not found after Build Tools installation."
    }

    $installPath = & $vsWhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if (-not $installPath) {
        throw "A Visual Studio installation with the x64 C++ tools was not found."
    }
    $vcVars = Join-Path $installPath.Trim() "VC\Auxiliary\Build\vcvars64.bat"
    if (-not (Test-Path -LiteralPath $vcVars)) {
        throw "The expected vcvars64.bat was not found: $vcVars"
    }
    return $vcVars
}

function Install-BuildTools {
    $installer = Get-VsInstaller
    $layoutArgs = @(
        "--layout", $OfflineLayout,
        "--add", "Microsoft.VisualStudio.Workload.VCTools",
        "--add", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
        "--add", "Microsoft.VisualStudio.Component.Windows10SDK.19041",
        "--lang", "en-US"
    )

    if ($OfflineLayout) {
        New-Item -ItemType Directory -Path $OfflineLayout -Force | Out-Null
        Write-Host "Creating the offline Build Tools layout at $OfflineLayout..."
        & $installer @layoutArgs
        if ($LASTEXITCODE -ne 0) {
            throw "Offline layout creation failed with exit code $LASTEXITCODE."
        }
        Write-Host "Offline layout created. Install later with:"
        Write-Host "& `"$OfflineLayout\vs_BuildTools.exe`" --quiet --wait --norestart --add Microsoft.VisualStudio.Workload.VCTools --add Microsoft.VisualStudio.Component.VC.Tools.x86.x64 --add Microsoft.VisualStudio.Component.Windows10SDK.19041"
        return
    }

    $installArgs = @(
        "--quiet", "--wait", "--norestart", "--nocache",
        "--add", "Microsoft.VisualStudio.Workload.VCTools",
        "--add", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
        "--add", "Microsoft.VisualStudio.Component.Windows10SDK.19041"
    )
    Write-Host "Installing the minimal Visual Studio C++ Build Tools workload..."
    $process = Start-Process -FilePath $installer -ArgumentList $installArgs -Wait -PassThru
    if ($process.ExitCode -notin @(0, 3010)) {
        throw "Visual Studio Build Tools installation failed with exit code $($process.ExitCode)."
    }
    Remove-Item -LiteralPath $installer -Force -ErrorAction SilentlyContinue
}

function Update-Requirements([string]$RequirementsPath) {
    $lines = @(Get-Content -LiteralPath $RequirementsPath)
    $lines = @($lines | Where-Object { $_ -notmatch '^\s*chromadb\s*=' -and $_ -notmatch '^\s*chroma-hnswlib\s*=' })
    $insertAt = [Array]::IndexOf($lines, ($lines | Where-Object { $_ -match '^openai' } | Select-Object -First 1))
    if ($insertAt -lt 0) { $insertAt = $lines.Count }
    $newLines = @()
    if ($insertAt -gt 0) { $newLines += $lines[0..($insertAt - 1)] }
    $newLines += "chromadb==0.4.22"
    $newLines += "chroma-hnswlib==0.7.3"
    if ($insertAt -lt $lines.Count) { $newLines += $lines[$insertAt..($lines.Count - 1)] }
    Set-Content -LiteralPath $RequirementsPath -Value $newLines -Encoding UTF8
    Write-Host "Updated $RequirementsPath with chromadb==0.4.22 and chroma-hnswlib==0.7.3."
}

Set-Location -LiteralPath $ProjectRoot

# Offline mode only creates the redistributable installer layout.  It does not
# require Python or an existing Visual Studio installation on this machine.
if ($OfflineLayout) {
    Install-BuildTools
    Write-Host "Offline layout is ready at: $((Resolve-Path -LiteralPath $OfflineLayout).Path)"
    return
}

$activate = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
$venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Python 3.12 virtual environment not found: $venvPython"
}

function Invoke-VenvPip([string[]]$Arguments) {
    & $venvPython -m pip @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "pip command failed with exit code $($LASTEXITCODE): $($Arguments -join ' ')"
    }
}

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
$vcVarsPath = $null
try {
    $vcVarsPath = Find-VcVars64
} catch {
    if ($SkipBuildTools) {
        throw
    }
    Install-BuildTools
    $vcVarsPath = Find-VcVars64
}
Import-VcVarsEnvironment $vcVarsPath

if (-not $SkipChromaInstall) {
    # Dot-source activation so VIRTUAL_ENV/PATH remain available to callers.
    . $activate
    Invoke-VenvPip @("uninstall", "chroma-hnswlib", "-y")
    Invoke-VenvPip @("install", "chroma-hnswlib==0.7.3", "--no-cache-dir")
    Invoke-VenvPip @("install", "chromadb==0.4.22", "-i", "https://pypi.tuna.tsinghua.edu.cn/simple")
    Update-Requirements (Join-Path $ProjectRoot "backend\requirements.txt")
    Invoke-VenvPip @("check")
}

Write-Host "Chroma build environment is ready in this PowerShell session."

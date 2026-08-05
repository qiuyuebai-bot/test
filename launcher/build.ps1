param(
    [ValidateSet("win-x64", "win-arm64")]
    [string]$Runtime = "win-x64"
)

$ErrorActionPreference = "Stop"
$project = Join-Path $PSScriptRoot "Launcher.csproj"
$output = Join-Path $PSScriptRoot "publish"
$dotnetCandidates = @(
    (Join-Path $env:LOCALAPPDATA "dotnet8-sdk\dotnet.exe")
)
$systemDotnet = Get-Command dotnet.exe -ErrorAction SilentlyContinue
if ($null -ne $systemDotnet) {
    $dotnetCandidates += $systemDotnet.Source
}
$dotnetExe = $dotnetCandidates | Where-Object {
    Test-Path -LiteralPath $_
} | Select-Object -First 1
if ([string]::IsNullOrWhiteSpace($dotnetExe)) {
    throw "The .NET SDK was not found. Install the .NET 8 SDK and run this script again."
}

$sdkVersions = & $dotnetExe --list-sdks
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace(($sdkVersions -join "`n"))) {
    throw "The .NET SDK was not found. Install the .NET 8 SDK and run this script again."
}

& $dotnetExe publish $project `
    --configuration Release `
    --runtime $Runtime `
    --self-contained true `
    --output $output `
    -p:PublishSingleFile=true `
    -p:IncludeNativeLibrariesForSelfExtract=true

Write-Host ("Launcher published to " + (Join-Path $output "ProjectLauncher.exe"))

<#
.SYNOPSIS
  k6 性能测试运行脚本 (Windows PowerShell)

.DESCRIPTION
  自动检测本地 k6 或使用 Docker 运行性能测试场景。
  支持 smoke / load / stress / spike 四种场景。

.PARAMETER Scenario
  测试场景名称: smoke, load, stress, spike, all (默认 smoke)

.PARAMETER BaseUrl
  后端地址 (默认 http://localhost:8000)

.PARAMETER UseDocker
  强制使用 Docker 模式运行

.EXAMPLE
  .\run.ps1 -Scenario smoke
  .\run.ps1 -Scenario load -BaseUrl http://192.168.1.100:8000
  .\run.ps1 -Scenario stress -UseDocker
  .\run.ps1 -Scenario all
#>
param(
    [Parameter(Position=0)]
    [ValidateSet('smoke', 'load', 'stress', 'spike', 'all')]
    [string]$Scenario = 'smoke',

    [string]$BaseUrl = 'http://localhost:8000',

    [switch]$UseDocker
)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

$Scenarios = @('smoke', 'load', 'stress', 'spike')
if ($Scenario -ne 'all') {
    $Scenarios = @($Scenario)
}

function Test-K6Available {
    $cmd = Get-Command k6 -ErrorAction SilentlyContinue
    return $null -ne $cmd
}

function Test-DockerAvailable {
    $cmd = Get-Command docker -ErrorAction SilentlyContinue
    if ($null -eq $cmd) { return $false }
    docker info 2>$null | Out-Null
    return $LASTEXITCODE -eq 0
}

function Invoke-K6Scenario {
    param([string]$Name)

    $scriptPath = Join-Path $ScriptDir "$Name.js"
    if (-not (Test-Path $scriptPath)) {
        Write-Error "场景脚本不存在: $scriptPath"
        return
    }

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  场景: $Name" -ForegroundColor Cyan
    Write-Host "  目标: $BaseUrl" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan

    if ($UseDocker) {
        if (-not (Test-DockerAvailable)) {
            Write-Error "Docker 不可用，无法使用 Docker 模式"
        }
        $scriptContent = Get-Content $scriptPath -Raw
        $env:BASE_URL = $BaseUrl
        $scriptContent | docker run --rm -i --network host `
            -e BASE_URL=$BaseUrl `
            grafana/k6 run -
    }
    elseif (Test-K6Available) {
        $env:BASE_URL = $BaseUrl
        k6 run $scriptPath
    }
    elseif (Test-DockerAvailable) {
        Write-Host "未检测到本地 k6，使用 Docker 模式..." -ForegroundColor Yellow
        $scriptContent = Get-Content $scriptPath -Raw
        $scriptContent | docker run --rm -i --network host `
            -e BASE_URL=$BaseUrl `
            grafana/k6 run -
    }
    else {
        Write-Error "未检测到 k6 或 Docker，请安装其一:`n  choco install k6  (本地)`n  或安装 Docker Desktop"
    }
}

foreach ($s in $Scenarios) {
    Invoke-K6Scenario -Name $s
}

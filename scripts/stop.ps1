<#
.SYNOPSIS
  Stops the stack. Data (database and uploaded files) lives in Docker volumes and is kept.

.DESCRIPTION
  -Wsl also stops the process that keeps WSL awake, so WSL (and VmmemWSL's memory) can shut down by itself.
  -UnloadModel unloads the model from the GPU.
#>
param(
  [string]$Distro = 'Ubuntu',
  [switch]$Wsl,
  [switch]$UnloadModel
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot "_common.ps1")

$root = Split-Path -Parent $PSScriptRoot

$rootInWsl = (ConvertTo-WslPath $Distro $root)
Invoke-Wsl $Distro "cd '$rootInWsl' && docker compose down"
Write-Host 'Containrarna är stoppade, datat finns kvar.'

if ($UnloadModel) {
  $envFile = Join-Path $root '.env'
  $url = ((Get-Content $envFile -Encoding UTF8 | Where-Object { $_ -match '^OLLAMA_BASE_URL=' }) -replace '^OLLAMA_BASE_URL=', '').Trim()
  if (-not $url) { $url = 'http://localhost:11434' }
  foreach ($m in (Invoke-RestMethod "$($url.TrimEnd('/'))/api/ps").models) {
    $body = @{ model = $m.name; keep_alive = 0 } | ConvertTo-Json
    Invoke-RestMethod "$($url.TrimEnd('/'))/api/generate" -Method Post -Body $body -ContentType 'application/json' | Out-Null
    Write-Host "Avlastade $($m.name)."
  }
}

if ($Wsl) {
  $pidFile = Join-Path $env:TEMP 'kommunkoll-wsl-keepalive.pid'
  if (Test-Path $pidFile) {
    Stop-Process -Id ([int](Get-Content $pidFile)) -ErrorAction SilentlyContinue
    Remove-Item $pidFile
  }
  Write-Host 'WSL hålls inte längre vaken; den stängs av sig själv när inget körs.'
}

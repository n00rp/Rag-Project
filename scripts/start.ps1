<#
.SYNOPSIS
  Starts the whole local stack and warms the model: one command instead of five.

.DESCRIPTION
  1. keeps WSL awake (it shuts down by itself when no terminal is open, taking the containers with it)
  2. docker compose up -d (with AI_SERVICE_HOST=windows in .env: the database and API in Docker, ai-service as a
     Windows process on the GPU)
  3. checks that Ollama answers on the address in .env
  4. loads the model and keeps it in memory for -KeepAlive, so the first question does not take ~30 s
  5. waits until the API reports that database and AI service are up

  No machine settings are changed. Run from anywhere: .\scripts\start.ps1
#>
param(
  [string]$Distro = 'Ubuntu',
  [string]$KeepAlive = '24h',
  [int]$TimeoutSeconds = 180
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot "_common.ps1")

$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root '.env'

function Read-DotEnv([string]$path) {
  $map = @{}
  if (Test-Path $path) {
    foreach ($line in Get-Content $path -Encoding UTF8) {
      if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$' -and -not $line.TrimStart().StartsWith('#')) {
        $map[$Matches[1]] = $Matches[2]
      }
    }
  }
  return $map
}

function Wait-Until([scriptblock]$check, [int]$seconds) {
  $deadline = (Get-Date).AddSeconds($seconds)
  while ((Get-Date) -lt $deadline) {
    try { if (& $check) { return $true } } catch { }
    Start-Sleep -Seconds 2
  }
  return $false
}

$cfg = Read-DotEnv $envFile
if ($cfg.Count -eq 0) { throw ".env saknas: kopiera .env.example till .env och fyll i värdena." }
$ollama = if ($cfg['OLLAMA_BASE_URL']) { $cfg['OLLAMA_BASE_URL'].TrimEnd('/') } else { 'http://localhost:11434' }
$model = $cfg['LLM_MODEL']

# 1. Keep WSL awake. The process id is remembered so that stop.ps1 (and a second start) can find it.
$pidFile = Join-Path $env:TEMP 'kommunkoll-wsl-keepalive.pid'
$alive = $false
if (Test-Path $pidFile) { $alive = [bool](Get-Process -Id ([int](Get-Content $pidFile)) -ErrorAction SilentlyContinue) }
if (-not $alive) {
  $p = Start-Process -FilePath wsl -ArgumentList '-d', $Distro, '--', 'sleep', 'infinity' -WindowStyle Hidden -PassThru
  Set-Content -Path $pidFile -Value $p.Id
  Write-Host "WSL hålls vaken (pid $($p.Id))."
} else {
  Write-Host 'WSL hålls redan vaken.'
}

# 2. The stack.
Write-Host 'Startar containrarna...'
$rootInWsl = (ConvertTo-WslPath $Distro $root)
if ($cfg['AI_SERVICE_HOST'] -eq 'windows') {
  # ai-service runs here on Windows (GPU); the API container reaches it on the Windows address of the WSL network.
  $gateway = ((wsl -d $Distro -- ip route show default) -split '\s+')[2]
  if (-not $gateway) { throw 'Hittar inte Windows-adressen från WSL (ip route show default).' }
  Invoke-Wsl $Distro "cd '$rootInWsl' && docker compose up -d db && docker compose stop ai-service"
  if ($LASTEXITCODE -ne 0) { throw 'docker compose up db misslyckades.' }
  Write-Host 'Startar ai-service på Windows (GPU)...'
  Start-WindowsAiService $root $cfg
  Invoke-Wsl $Distro "cd '$rootInWsl' && AI_SERVICE_URL=http://${gateway}:8000/ docker compose up -d --no-deps api frontend && docker compose restart frontend"
  # (nginx resolves the API's address once at start; a re-created API container has a new one)
} else {
  Invoke-Wsl $Distro "cd '$rootInWsl' && docker compose up -d"
}
if ($LASTEXITCODE -ne 0) { throw 'docker compose up misslyckades.' }

# 3 + 4. Ollama and the model.
$ollamaUp = Wait-Until { (Invoke-RestMethod "$ollama/api/version" -TimeoutSec 3).version } 15
if (-not $ollamaUp) {
  Write-Warning "Ollama svarar inte på $ollama. Starta Ollama; appen fungerar men svar kräver modellen (offline-läge visas)."
} elseif ($cfg['LLM_BACKEND'] -eq 'ollama' -and $model) {
  Write-Host "Laddar $model och håller den i minnet i $KeepAlive..."
  $body = @{ model = $model; prompt = ''; keep_alive = $KeepAlive } | ConvertTo-Json
  Invoke-RestMethod "$ollama/api/generate" -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 180 | Out-Null
}

# 5. Wait for the API.
$ready = Wait-Until { $h = Invoke-RestMethod 'http://127.0.0.1:8080/health' -TimeoutSec 3; $h.database -and $h.aiService } $TimeoutSeconds
if ($ready) {
  # Warm the rest of the chain too: the embedding model in ai-service and the real chat path in Ollama.
  # (The query goes to ai-service directly with a throwaway owner, so no chat history is written.)
  Write-Host 'Värmer upp sökning och generering...'
  try {
    $warm = @{ owner_id = 'warmup'; question = 'uppvärmning' } | ConvertTo-Json
    Invoke-RestMethod 'http://127.0.0.1:8000/query' -Method Post -Body $warm -ContentType 'application/json; charset=utf-8' -TimeoutSec 120 | Out-Null
    if ($cfg['LLM_BACKEND'] -eq 'ollama' -and $model -and $ollamaUp) {
      $chat = @{ model = $model; max_tokens = 1; messages = @(@{ role = 'user'; content = 'Hej' }) } | ConvertTo-Json -Depth 4
      Invoke-RestMethod "$ollama/v1/chat/completions" -Method Post -Body $chat -ContentType 'application/json' -TimeoutSec 180 | Out-Null
    }
  } catch { Write-Warning "Uppvärmningen misslyckades (appen fungerar ändå): $($_.Exception.Message)" }
  Write-Host ''
  Write-Host 'Klart. Öppna http://127.0.0.1:3000' -ForegroundColor Green
} else {
  Write-Warning "API:et blev inte friskt inom $TimeoutSeconds s. Kolla: wsl -d $Distro -- docker compose logs --tail 50"
  exit 1
}

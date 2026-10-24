# Shared helpers for start.ps1, stop.ps1, backup.ps1 and restore.ps1 (dot-sourced).

function ConvertTo-WslPath([string]$distro, [string]$windowsPath) {
  # wslpath wants forward slashes.
  (wsl -d $distro -- wslpath -a ($windowsPath -replace '\\', '/')).Trim()
}

# Runs a bash command line inside WSL.
#
# Native commands (wsl, docker) print progress on stderr; with ErrorActionPreference=Stop Windows PowerShell 5.1
# would treat that as a failure, so the exit code ($LASTEXITCODE) is what decides. The command is written to a
# temporary script and run from there, because wsl.exe expands $VARIABLES in command lines itself, which breaks
# quoting (for example $POSTGRES_USER inside a container command).
function Invoke-Wsl([string]$distro, [string]$command) {
  $file = Join-Path $env:TEMP ('kommunkoll-' + [guid]::NewGuid().ToString('N') + '.sh')
  [IO.File]::WriteAllText($file, ($command -replace "`r`n", "`n") + "`n", (New-Object Text.UTF8Encoding($false)))
  $previous = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  try {
    $inWsl = ConvertTo-WslPath $distro $file
    wsl -d $distro -- bash $inWsl 2>&1 | ForEach-Object { "$_" } | Write-Host
  } finally {
    $ErrorActionPreference = $previous
    Remove-Item $file -ErrorAction SilentlyContinue
  }
}

# ai-service as a Windows process (AI_SERVICE_HOST=windows in .env): uses ai-service\.venv and the GPU, which the Docker
# image (CPU torch) cannot. The Docker API reaches it through the Windows address of the WSL network.
$script:AiPidFile = Join-Path $env:TEMP 'kommunkoll-ai-service.pid'

function Stop-WindowsAiService {
  if (Test-Path $script:AiPidFile) {
    Stop-Process -Id ([int](Get-Content $script:AiPidFile)) -Force -ErrorAction SilentlyContinue
    Remove-Item $script:AiPidFile -ErrorAction SilentlyContinue
  }
}

function Start-WindowsAiService([string]$root, [hashtable]$cfg, [int]$timeoutSeconds = 240) {
  Stop-WindowsAiService
  $python = Join-Path $root 'ai-service\.venv\Scripts\python.exe'
  if (-not (Test-Path $python)) { throw "ai-service\.venv saknas ($python). Skapa den enligt docs/dev-setup.md." }
  # The process inherits these; they are the same names as in .env, plus the database address as seen from Windows.
  foreach ($key in 'EMBEDDING_BACKEND', 'EMBEDDING_MODEL', 'EMBEDDING_DIM', 'MIN_SCORE', 'RESET_VECTORS_ON_DIM_CHANGE',
                   'RERANK_MODEL', 'LLM_BACKEND', 'LLM_MODEL', 'OLLAMA_BASE_URL', 'INTERNAL_API_KEY') {
    if ($cfg[$key]) { Set-Item -Path "Env:$key" -Value $cfg[$key] }
  }
  $env:DATABASE_URL = "postgresql://$($cfg['POSTGRES_USER']):$($cfg['POSTGRES_PASSWORD'])@127.0.0.1:5432/$($cfg['POSTGRES_DB'])"
  $log = Join-Path $env:TEMP 'kommunkoll-ai-service.log'
  $p = Start-Process -FilePath $python -ArgumentList '-X', 'utf8', '-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000' `
    -WorkingDirectory (Join-Path $root 'ai-service') -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $log -RedirectStandardError "$log.err"
  Set-Content -Path $script:AiPidFile -Value $p.Id
  $deadline = (Get-Date).AddSeconds($timeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    if ($p.HasExited) { throw "ai-service avslutades direkt. Se $log.err" }
    try { if ((Invoke-RestMethod 'http://127.0.0.1:8000/health' -TimeoutSec 3).status) { return } } catch { }
    Start-Sleep -Seconds 2
  }
  throw "ai-service svarade inte inom $timeoutSeconds s. Se $log.err"
}

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

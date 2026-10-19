<#
.SYNOPSIS
  Backs up the database and the uploaded PDF files to backups\<timestamp>\ (git-ignored).

.DESCRIPTION
  The stack must be running. Creates database.dump (pg_dump custom format) and uploads.tgz.
  Restore with .\scripts\restore.ps1 -Backup <folder>.
#>
param(
  [string]$Distro = 'Ubuntu',
  [string]$Destination
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot "_common.ps1")

$root = Split-Path -Parent $PSScriptRoot
if (-not $Destination) { $Destination = Join-Path $root ("backups\" + (Get-Date -Format 'yyyyMMdd-HHmmss')) }
New-Item -ItemType Directory -Force $Destination | Out-Null

$rootInWsl = (ConvertTo-WslPath $Distro $root)
$destInWsl = (ConvertTo-WslPath $Distro $Destination)

# Credentials come from the container's own environment, so nothing is read from .env here.
Invoke-Wsl $Distro "cd '$rootInWsl' && docker compose exec -T db sh -c 'pg_dump -U `$POSTGRES_USER -Fc `$POSTGRES_DB' > '$destInWsl/database.dump'"
if ($LASTEXITCODE -ne 0) { throw 'pg_dump misslyckades.' }

Invoke-Wsl $Distro "cd '$rootInWsl' && docker compose exec -T api tar czf - -C /data/uploads . > '$destInWsl/uploads.tgz'"
if ($LASTEXITCODE -ne 0) { throw 'Kunde inte packa uppladdade filer.' }

Get-ChildItem $Destination | ForEach-Object { Write-Host ("{0,-16} {1,10:N0} byte" -f $_.Name, $_.Length) }
Write-Host "Säkerhetskopia klar: $Destination" -ForegroundColor Green

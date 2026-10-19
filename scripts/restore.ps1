<#
.SYNOPSIS
  Restores a backup made by backup.ps1.

.DESCRIPTION
  By default the live database is REPLACED, and so are the uploaded files; you are asked to confirm.
  With -Database <name> the dump is restored into a separate database instead and nothing else is
  touched; use that to check that a backup is usable (then drop it with -DropAfter).
#>
param(
  [Parameter(Mandatory)][string]$Backup,
  [string]$Distro = 'Ubuntu',
  [string]$Database,
  [switch]$DropAfter,
  [switch]$Force
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot "_common.ps1")

$root = Split-Path -Parent $PSScriptRoot
$Backup = (Resolve-Path $Backup).Path
$dump = Join-Path $Backup 'database.dump'
$uploads = Join-Path $Backup 'uploads.tgz'
if (-not (Test-Path $dump)) { throw "Hittar inte $dump" }

$rootInWsl = (ConvertTo-WslPath $Distro $root)
$dumpInWsl = (ConvertTo-WslPath $Distro $dump)
$uploadsInWsl = (ConvertTo-WslPath $Distro $uploads)
$compose = "cd '$rootInWsl' && docker compose"

if ($Database) {
  # Check-only restore into a separate database.
  Invoke-Wsl $Distro "$compose exec -T db sh -c 'dropdb -U `$POSTGRES_USER --if-exists $Database; createdb -U `$POSTGRES_USER $Database'"
  Invoke-Wsl $Distro "$compose exec -T db sh -c 'pg_restore -U `$POSTGRES_USER -d $Database --no-owner' < '$dumpInWsl'"
  Write-Host "Återställd till databasen '$Database'."
  Invoke-Wsl $Distro "$compose exec -T db sh -c 'psql -U `$POSTGRES_USER -d $Database -tAc ""select count(*) from rag.chunks""'"
  if ($DropAfter) {
    Invoke-Wsl $Distro "$compose exec -T db sh -c 'dropdb -U `$POSTGRES_USER $Database'"
    Write-Host "Databasen '$Database' är borttagen."
  }
  return
}

if (-not $Force) {
  $answer = Read-Host 'Detta ERSÄTTER den riktiga databasen och de uppladdade filerna. Skriv "ja" för att fortsätta'
  if ($answer -ne 'ja') { Write-Host 'Avbröt.'; return }
}
Invoke-Wsl $Distro "$compose exec -T db sh -c 'pg_restore -U `$POSTGRES_USER -d `$POSTGRES_DB --clean --if-exists --no-owner' < '$dumpInWsl'"
if (Test-Path $uploads) {
  Invoke-Wsl $Distro "$compose exec -T api sh -c 'rm -rf /data/uploads/* && tar xzf - -C /data/uploads' < '$uploadsInWsl'"
}
Write-Host 'Återställt. Starta om API:et om något ser konstigt ut: docker compose restart api' -ForegroundColor Green

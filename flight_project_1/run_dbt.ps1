param(
  [Parameter(Position=0)]
  [ValidateSet('debug','deps','run','test','build','compile','clean')]
  [string]$Command = 'run',

  [Parameter(ValueFromRemainingArguments=$true)]
  [string[]]$Args
)

$ErrorActionPreference = 'Stop'

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Image = 'ghcr.io/dbt-labs/dbt-postgres:1.7.4'

Write-Host "Running dbt-core via Docker: $Command $($Args -join ' ')" 

$dockerArgs = @(
  'run','--rm',
  '-v', "${ProjectDir}:/usr/app",
  '-w','/usr/app',
  $Image,
  $Command,
  '--profiles-dir','/usr/app/.dbt_docker'
) + $Args

& docker @dockerArgs
if ($LASTEXITCODE -ne 0) {
  throw "dbt failed with exit code $LASTEXITCODE"
}

param(
  [Parameter(Mandatory = $true)]
  [string]$Message
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repositoryRoot

if (-not (git config user.name)) {
  git config user.name "PedroBarboni"
}
if (-not (git config user.email)) {
  git config user.email "209558839+PedroBarboni@users.noreply.github.com"
}

$hasOrigin = @(git remote) -contains "origin"
if (-not $hasOrigin) {
  git remote add origin "https://github.com/PedroBarboni/portal-gestao-operacional.git"
} else {
  $origin = git remote get-url origin
  if ($origin -ne "https://github.com/PedroBarboni/portal-gestao-operacional.git") {
    throw "O remote origin aponta para outro repositório: $origin"
  }
}

$paths = @(
  git diff --name-only
  git ls-files --others --exclude-standard
) | Where-Object { $_ } | Sort-Object -Unique

if ($paths) {
  git add -- $paths
}
$pending = git status --porcelain
if (-not $pending) {
  Write-Host "Nenhuma alteração pendente."
  exit 0
}

git commit -m $Message
git branch -M main
git push --set-upstream origin main

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$RepoRoot = Split-Path -Parent $RepoRoot
$Profile = Join-Path $PSScriptRoot 'profile.mock.json'
python -m ironengine_rl.validate $Profile --strict
python -m ironengine_rl.cli $Profile --validate-only --strict

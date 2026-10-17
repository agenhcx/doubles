# One-time local setup. First create EMPTY GitHub repository agenhcx/doubles.
# Run inside extracted C:\chenxi\bazi_project\doubles folder.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path $PSScriptRoot).Path
if ((Split-Path $root -Leaf) -ne 'doubles') { throw "Please extract this package to a folder named doubles: $root" }
if (Test-Path (Join-Path $root '.git')) { throw "Git directory already exists. Do not initialize twice." }
$parent = Split-Path $root -Parent
while ($parent) {
    if (Test-Path (Join-Path $parent '.git')) { throw "Refusing nested repository: found .git in $parent" }
    $next = Split-Path $parent -Parent
    if ($next -eq $parent) { break }
    $parent = $next
}
Push-Location $root
try {
    & git init -b main
    if ($LASTEXITCODE -ne 0) { throw 'git init failed' }
    & git add .
    if ($LASTEXITCODE -ne 0) { throw 'git add failed' }
    & git commit -m 'Bootstrap independent doubles research dataset'
    if ($LASTEXITCODE -ne 0) { throw 'git commit failed; check git user.name and user.email' }
    & git remote add origin 'https://github.com/agenhcx/doubles.git'
    if ($LASTEXITCODE -ne 0) { throw 'git remote add failed' }
    & git push -u origin main
    if ($LASTEXITCODE -ne 0) { throw 'git push failed; confirm that the empty remote exists and you have push access' }
    Write-Host "Success. Next time: git pull --ff-only; python .\scripts\run_all.py"
} finally { Pop-Location }

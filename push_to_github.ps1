# ============================================================
#  CQJTU Campus Assistant v3 - one-click push to GitHub
#
#  HOW TO USE:
#   1. Create an EMPTY public repo on GitHub named: cqjtu-campus
#      (do NOT tick "Add a README")
#   2. Right-click this file -> "Run with PowerShell"
#
#  NOTE: ASCII-only on purpose. Windows PowerShell 5.1 decodes
#  BOM-less UTF-8 as GBK, which mangles Chinese and breaks quotes.
# ============================================================

$ErrorActionPreference = "Stop"
$GhUser = "liyy66"
$Repo   = "cqjtu-campus"

if ($GhUser -eq "YOUR_USERNAME_HERE") {
    Write-Host ""
    Write-Host "  Fill in your GitHub username first (line: `$GhUser)." -ForegroundColor Yellow
    Read-Host "  Press Enter to close"
    exit 1
}

$Url  = "https://github.com/$GhUser/$Repo.git"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host ""
Write-Host "  Repository : $Url" -ForegroundColor Cyan
Write-Host ""

if ((git remote) -contains "origin") { git remote remove origin | Out-Null }
git remote add origin $Url
git branch -M main

Write-Host "  Pushing (about 13 MB, 1-2 min; GitHub will ask you to sign in)..." -ForegroundColor Cyan
Write-Host ""
git push -u origin main
$code = $LASTEXITCODE

Write-Host ""
if ($code -ne 0) {
    Write-Host "  PUSH FAILED." -ForegroundColor Red
    Write-Host "  Most likely: repo '$Repo' not created yet." -ForegroundColor Yellow
    Write-Host "  Create it at: https://github.com/new  (empty, Public, no README)" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "  Press Enter to close"
    exit $code
}

Write-Host "  PUSH OK" -ForegroundColor Green
Write-Host ""
Write-Host "  Two steps left in the browser:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  1) $Url"
Write-Host "     -> replace https:// with https:// and append /settings/pages"
Write-Host "        Set Source = GitHub Actions, then Save"
Write-Host ""
Write-Host "  2) https://github.com/$GhUser/$Repo/actions"
Write-Host "     Run workflow -> pick 'Crawl CQJTU Campus v3' -> Run workflow"
Write-Host "     First run is a FULL crawl, about 10-30 min. Normal."
Write-Host ""
Write-Host "  Site will live at:  https://$GhUser.github.io/$Repo/" -ForegroundColor Green
Write-Host ""
Read-Host "  Press Enter to close"

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

# GitHub 在大陆常被干扰，而本机 Clash（默认 7897）不一定开着。
# 探测端口：有就只给本仓库配代理；没有就清掉代理配置走直连，
# 否则会因"连不上代理"而失败（配置了代理但代理没运行 = 必然失败）。
$Proxy = "http://127.0.0.1:7897"
$hasProxy = $false
try {
    $t = Test-NetConnection -ComputerName 127.0.0.1 -Port 7897 -WarningAction SilentlyContinue
    $hasProxy = $t.TcpTestSucceeded
} catch {}
if ($hasProxy) {
    Write-Host "  Proxy detected: $Proxy (repo-level)" -ForegroundColor DarkGray
    git config http.proxy $Proxy
    git config https.proxy $Proxy
} else {
    git config --unset http.proxy 2>$null
    git config --unset https.proxy 2>$null
    Write-Host "  No local proxy detected, using direct connection" -ForegroundColor DarkGray
}
# 大仓库 + 弱网络：拉高缓冲、关掉低速中断
git config http.postBuffer "524288000"
git config http.lowSpeedLimit "0"
git config http.lowSpeedTime "999"

Write-Host "  Pushing (about 13 MB, 1-2 min; GitHub will ask you to sign in)..." -ForegroundColor Cyan
Write-Host ""

# 直连 13MB 容易被重置，失败自动重试
$code = 1
for ($i = 1; $i -le 3; $i++) {
    if ($i -gt 1) {
        Write-Host "  retry $i/3 ..." -ForegroundColor Yellow
        Start-Sleep -Seconds 5
    }
    git push -u origin main
    $code = $LASTEXITCODE
    if ($code -eq 0) { break }
}

Write-Host ""
if ($code -ne 0) {
    Write-Host "  PUSH FAILED." -ForegroundColor Red
    Write-Host ""
    Write-Host "  If it says 'Connection was reset' / 'Recv failure':" -ForegroundColor Yellow
    Write-Host "    - network to GitHub was interrupted." -ForegroundColor Yellow
    Write-Host "    - if Clash is running, make sure the port above matches" -ForegroundColor Yellow
    Write-Host "      (default 7897), then just run this file again." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  If it says 'rejected (fetch first)':" -ForegroundColor Yellow
    Write-Host "    - GitHub Actions pushed data on the remote." -ForegroundColor Yellow
    Write-Host "    - run: git pull --rebase origin main, then push again." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  If the repo does not exist yet:" -ForegroundColor Yellow
    Write-Host "    create it at https://github.com/new (empty, Public, no README)" -ForegroundColor Yellow
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

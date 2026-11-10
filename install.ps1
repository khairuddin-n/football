# Football Club installer: terminal command + Flow Launcher plugin.
# Usage (from this folder):
#   .\install.ps1                 # terminal command is "fc"
#   .\install.ps1 -Command ball   # pick your own command name
param([string]$Command = "fc")

$root = $PSScriptRoot
Write-Host "`n== Installing Football Club ==" -ForegroundColor Cyan

# 1. Python (used by the terminal command and Flow Launcher)
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py -or $py.Source -like "*WindowsApps*") {
    Write-Host "Python not found. Installing Python 3.12 with winget..." -ForegroundColor Yellow
    winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
    Write-Host "`nPython installed. Close ALL Windows Terminal windows, open a new one, then run .\install.ps1 again." -ForegroundColor Yellow
    return
}
Write-Host "[1/4] Python: $(& python --version)" -ForegroundColor Green

# 2. Terminal command
$bin = "$env:USERPROFILE\.local\bin"
New-Item -ItemType Directory -Force $bin | Out-Null
"@setlocal & set `"FOOTBALL_CLUB_CMD=$Command`" & python `"$root\cli.py`" %*" | Set-Content "$bin\$Command.cmd" -Encoding ASCII
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$bin*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$bin", "User")
    Write-Host "      Added $bin to your PATH (open a new terminal to use it)" -ForegroundColor Yellow
}
Write-Host "[2/4] Terminal command '$Command' created" -ForegroundColor Green

# 3. Flow Launcher plugin (a junction to this folder, so code changes apply right away)
$plugins = "$env:APPDATA\FlowLauncher\Plugins"
if (Test-Path $plugins) {
    $link = Join-Path $plugins "FootballClub"
    if ((Test-Path $link) -and -not (Get-Item $link -Force).LinkType) {
        Write-Host "[3/4] $link already exists and is not a link, skipped (remove it and run again)" -ForegroundColor Yellow
    } else {
        if (Test-Path $link) { cmd /c rmdir "$link" | Out-Null }
        New-Item -ItemType Junction -Path $link -Target $root | Out-Null
        Write-Host "[3/4] Flow Launcher plugin linked" -ForegroundColor Green
    }
} else {
    Write-Host "[3/4] Flow Launcher plugins folder not found ($plugins), skipped" -ForegroundColor Yellow
}

# 4. API key + favorite club (used by the terminal command; Flow has its own settings page too)
$cfg = "$env:APPDATA\football-club\config.json"
$hasKey = $env:FOOTBALL_DATA_API_KEY -or (Test-Path $cfg)
if (-not $hasKey) { & python "$root\cli.py" setup }
Write-Host "[4/4] Choose your favorite club" -ForegroundColor Cyan
& python "$root\cli.py" team

Write-Host "`nDone!" -ForegroundColor Green
Write-Host "- Terminal      : $Command, $Command fixtures, $Command table, $Command squad ..."
Write-Host "- Flow Launcher : restart Flow Launcher, then type 'fc' (make sure the plugin is enabled"
Write-Host "                  in Settings > Plugins > Football Club, and set your API key and club there)`n"

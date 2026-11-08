# Uruchamia Konwerter plikow w Dockerze i wypisuje adresy, pod ktorymi klienci znajda aplikacje.
#
# Uzycie (w katalogu projektu):
#   powershell -ExecutionPolicy Bypass -File .\uruchom-serwer.ps1
#   powershell -ExecutionPolicy Bypass -File .\uruchom-serwer.ps1 -Mailpit   # z testowa skrzynka pocztowa
#   powershell -ExecutionPolicy Bypass -File .\uruchom-serwer.ps1 -Stop      # zatrzymanie
param(
    [switch]$Mailpit,
    [switch]$Stop
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Nie znaleziono polecenia docker. Zainstaluj i uruchom Docker Desktop." -ForegroundColor Red
    exit 1
}
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker nie dziala. Uruchom Docker Desktop i poczekaj, az bedzie gotowy." -ForegroundColor Red
    exit 1
}

$profileArgs = @()
if ($Mailpit) { $profileArgs = @("--profile", "mailpit") }

if ($Stop) {
    docker compose --profile mailpit down
    exit $LASTEXITCODE
}

if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $secret = -join ($bytes | ForEach-Object { "{0:x2}" -f $_ })
    (Get-Content .env -Encoding UTF8) -replace '^SECRET_KEY=.*', "SECRET_KEY=$secret" | Set-Content .env -Encoding UTF8
    Write-Host "Utworzono plik .env z losowym SECRET_KEY. Uzupelnij w nim SMTP, aby kody szly e-mailem." -ForegroundColor Yellow
}

function Get-EnvValue([string]$name, [string]$default) {
    $line = Get-Content .env -Encoding UTF8 | Where-Object { $_ -match "^\s*$name\s*=" } | Select-Object -Last 1
    if (-not $line) { return $default }
    $value = ($line -split "=", 2)[1].Trim()
    if ($value) { return $value } else { return $default }
}

$port = Get-EnvValue "APP_PORT" "8000"
$bind = Get-EnvValue "BIND_ADDRESS" "0.0.0.0"

Write-Host "Budowanie i uruchamianie kontenerow..." -ForegroundColor Cyan
docker compose @profileArgs up -d --build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Czekam na gotowosc aplikacji..." -ForegroundColor Cyan
$health = $null
for ($i = 0; $i -lt 60; $i++) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$port/health" -TimeoutSec 2
        break
    } catch { Start-Sleep -Seconds 2 }
}
if (-not $health) {
    Write-Host "Aplikacja nie odpowiada. Sprawdz logi: docker compose logs app" -ForegroundColor Red
    exit 1
}

# Zapora Windows: regula przychodzaca dla portu aplikacji (wymaga uprawnien administratora).
if ($bind -ne "127.0.0.1") {
    $ruleName = "Konwerter plikow (TCP $port)"
    $rule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
    if (-not $rule) {
        $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
        if ($isAdmin) {
            New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP -LocalPort $port -Action Allow -Profile Private,Domain | Out-Null
            Write-Host "Dodano regule zapory: $ruleName (sieci prywatne i domenowe)." -ForegroundColor Green
        } else {
            Write-Host "UWAGA: brak reguly zapory dla portu $port. Inne komputery moga nie miec dostepu." -ForegroundColor Yellow
            Write-Host "Uruchom raz PowerShell jako administrator i wykonaj:" -ForegroundColor Yellow
            Write-Host "  New-NetFirewallRule -DisplayName `"$ruleName`" -Direction Inbound -Protocol TCP -LocalPort $port -Action Allow -Profile Private,Domain"
        }
    }
}

Write-Host ""
Write-Host "Konwerter dziala." -ForegroundColor Green
Write-Host "  Na tym komputerze:   http://localhost:$port"
if ($bind -ne "127.0.0.1") {
    $addresses = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" -and $_.InterfaceAlias -notmatch "vEthernet|WSL|Loopback|Docker" }
    foreach ($address in $addresses) {
        Write-Host ("  Z innych komputerow: http://{0}:{1}   ({2})" -f $address.IPAddress, $port, $address.InterfaceAlias)
    }
}
Write-Host ("  Poczta:               {0}" -f $health.email)
if ($health.email -eq "kod w interfejsie") {
    Write-Host "  UWAGA: SMTP nie jest skonfigurowany - kod logowania pokaze sie w przegladarce (tylko do testow)." -ForegroundColor Yellow
}
if ($Mailpit) {
    Write-Host "  Skrzynka testowa:     http://localhost:8025 (ustaw w .env SMTP_HOST=mailpit, SMTP_PORT=1025, SMTP_STARTTLS=false)"
}
Write-Host ""
Write-Host "Logi na zywo: docker compose logs -f app    Zatrzymanie: .\uruchom-serwer.ps1 -Stop"

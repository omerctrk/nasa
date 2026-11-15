# ASTRA HEALTH uçtan uca test: geçici, ayrı bir yığın kurar → senaryoları koşar → yığını siler.
# Asıl demo veritabanına dokunmaz (proje adı astra-e2e, ayrı volume, host portu yok).
# Aşamalar: ana (model kapalı, deterministik) · llm_yok (Ollama erişilemez) · llm_gercek (.env'deki Ollama)
# Çalıştırma: e2e_calistir.cmd'ye çift tık.  Rapor: tests\e2e\rapor\e2e_sonuc*.md
$ErrorActionPreference = "Continue"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $root
$rapor = Join-Path $PSScriptRoot "rapor"
New-Item -ItemType Directory -Force $rapor | Out-Null

if (-not (Test-Path ".env")) { Write-Host "HATA: proje kökünde .env yok." -ForegroundColor Red; Read-Host "Enter"; exit 1 }

# Geçici yığına özel tek kullanımlık parolalar (asıl hesaplar etkilenmez)
$env:SEED_ASTRONAUT_PASSWORD = "E2e-a-" + [guid]::NewGuid().ToString("N")
$env:SEED_GROUND_PASSWORD    = "E2e-g-" + [guid]::NewGuid().ToString("N")
$env:E2E_PHASE = "ana"; $env:E2E_LLM_BASE_URL = ""; $env:E2E_LLM_PROBE = ""
$dc = @("compose", "-p", "astra-e2e", "-f", "docker-compose.yml", "-f", "tests/e2e/docker-compose.e2e.yml")

function Adim($no, $yazi) { Write-Host "`n[$no/6] $yazi" -ForegroundColor Cyan }
function Dur($ne) {
  if ($LASTEXITCODE -ne 0) {
    Write-Host "`nHATA: $ne başarısız." -ForegroundColor Red
    docker @dc logs --no-color *> (Join-Path $rapor "docker.log")
    docker @dc down -v --remove-orphans | Out-Null
    Read-Host "Kapatmak için Enter"; exit 1
  }
}

Adim 1 "Eski e2e yığını temizleniyor..."
docker @dc down -v --remove-orphans 2>$null | Out-Null

Adim 2 "Boş veritabanı + migration (sa)..."
docker @dc run --rm migrate;                                Dur "Migration"

Adim 3 "Seed + 74 günlük demo davranış verisi (astra_app)..."
docker @dc run --rm seed;                                   Dur "Seed"
docker @dc run --rm seed python -m scripts.demo_data;       Dur "Demo verisi"

Adim 4 "API + işçi başlatılıyor..."
docker @dc up -d --wait api;                                Dur "API"

Adim 5 "Senaryolar koşuluyor (ana + model erişilemez + gerçek model)..."
function Asama($ad, $llm, $timeout) {
  $env:E2E_PHASE = $ad; $env:E2E_LLM_BASE_URL = $llm; $env:E2E_JOB_TIMEOUT = $timeout
  $env:E2E_LLM_PROBE = $llm
  if ($ad -ne "ana") { docker @dc up -d --force-recreate --wait api | Out-Host }
  Write-Host "`n--- aşama: $ad ---" -ForegroundColor Cyan
  docker @dc run --rm e2e 2>&1 | Tee-Object -FilePath (Join-Path $rapor "konsol_$ad.txt") | Out-Host
  $c = $LASTEXITCODE
  docker @dc logs --no-color api *> (Join-Path $rapor "api_$ad.log")
  return [int]$c
}
$gercekLlm = (Select-String -Path ".env" -Pattern '^LLM_BASE_URL=(.*)$' | Select-Object -First 1).Matches.Groups[1].Value
if (-not $gercekLlm) { $gercekLlm = "http://host.docker.internal:11434" }
$kod = 0
$kod = $kod -bor (Asama "ana" "" 90)
$kod = $kod -bor (Asama "llm_yok" "http://llm-erisilemez.invalid:11434" 120)
$kod = $kod -bor (Asama "llm_gercek" $gercekLlm 400)

Adim 6 "Geçici yığın siliniyor..."
docker @dc down -v --remove-orphans | Out-Null

if ($kod -eq 0) { Write-Host "`nTÜM SENARYOLAR GEÇTİ." -ForegroundColor Green }
else { Write-Host "`nBAŞARISIZ ADIM VAR. Rapor: tests\e2e\rapor\" -ForegroundColor Yellow }
Read-Host "Kapatmak için Enter"
exit $kod

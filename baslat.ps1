# ASTRA HEALTH: tek komutla her şeyi açar (veritabanı + API + frontend).
# Çalıştırma: baslat.cmd dosyasına çift tıkla.  Kapatma: bu pencerede Ctrl+C, sonra durdur.cmd
Set-Location $PSScriptRoot

function Adim($no, $yazi) { Write-Host "`n[$no/5] $yazi" -ForegroundColor Cyan }
function Kontrol($ne) {
  if ($LASTEXITCODE -ne 0) {
    Write-Host "`nHATA: $ne başarısız oldu. Yukarıdaki kırmızı satırlara bak." -ForegroundColor Red
    Read-Host "Kapatmak için Enter"
    exit 1
  }
}

if (-not (Test-Path ".env")) {
  Write-Host "HATA: .env dosyası bulunamadı (nasa klasöründe olmalı)." -ForegroundColor Red
  Read-Host "Kapatmak için Enter"; exit 1
}

Adim 1 "Veritabanı ve API başlatılıyor (Docker)..."
docker compose up -d api;            Kontrol "API'yi başlatma"

Adim 2 "Tablolar güncelleniyor..."
docker compose run --rm migrate;     Kontrol "Migration"

Adim 3 "Demo hesaplar ve sözlük yükleniyor..."
docker compose run --rm seed;        Kontrol "Seed"

Adim 4 "Demo takvimi bugüne hizalanıyor (görev günü 74 = bugün)..."
# Kuru çalışma değil: --apply. Reddederse (ör. 74. günden sonraki kayıt) demo yine açılır, uyarı verilir.
docker compose run --rm migrate python -m scripts.realign_demo --apply
if ($LASTEXITCODE -eq 3) { Write-Host "UYARI: takvim hizalanmadı (yukarıdaki nedene bak); demo mevcut takvimle açılıyor." -ForegroundColor Yellow }
elseif ($LASTEXITCODE -ne 0) { Kontrol "Takvim hizalama" }
# Sentetik fizyolojik/ortam ölçümleri (nabız…, SpO2, göz içi basıncı, radyasyon, kabin CO2):
# yalnız EKSİK gün/ölçümleri ekler (var olana dokunmaz), görev günü 74'e kadar.
docker compose run --rm seed python -m scripts.seed_physiological --apply;   Kontrol "Sentetik ölçümler"

Adim 5 "Frontend açılıyor..."
Set-Location frontend
# npm ci kilit dosyasıyla birebir uyum ister; sürüm farkı olan bilgisayarlarda npm install daha toleranslı
if (-not (Test-Path "node_modules\.bin\vite.cmd")) { npm install --no-audit --no-fund; Kontrol "npm install" }
# Önceki çalıştırmadan açık kalan Vite (5173) yeni kodu gölgeler: yalnız node süreciyse kapat.
$eski = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue |
  Select-Object -ExpandProperty OwningProcess -Unique
foreach ($pid5173 in $eski) {
  $p = Get-Process -Id $pid5173 -ErrorAction SilentlyContinue
  if ($p -and $p.ProcessName -eq "node") {
    Write-Host "Eski frontend sunucusu kapatılıyor (PID $pid5173)..." -ForegroundColor Yellow
    Stop-Process -Id $pid5173 -Force; Start-Sleep 1
  } elseif ($p) {
    Write-Host "HATA: 5173 portunu '$($p.ProcessName)' (PID $pid5173) kullanıyor; kapatıp tekrar deneyin." -ForegroundColor Red
    Read-Host "Kapatmak için Enter"; exit 1
  }
}
# Vite hazır olunca tarayıcı açılsın
Start-Process powershell -WindowStyle Hidden -ArgumentList '-NoProfile','-Command','Start-Sleep 5; Start-Process "http://127.0.0.1:5173/"'
Write-Host "`nHazır: http://127.0.0.1:5173/   API belgesi: http://127.0.0.1:8001/docs" -ForegroundColor Green
Write-Host "Kapatmak için Ctrl+C, ardından durdur.cmd`n" -ForegroundColor Green
npm run dev

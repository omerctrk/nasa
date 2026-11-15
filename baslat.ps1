# ASTRA HEALTH: tek komutla her şeyi açar (veritabanı + API + frontend).
# Çalıştırma: baslat.cmd dosyasına çift tıkla.  Kapatma: bu pencerede Ctrl+C, sonra durdur.cmd
Set-Location $PSScriptRoot

function Adim($no, $yazi) { Write-Host "`n[$no/4] $yazi" -ForegroundColor Cyan }
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

Adim 4 "Frontend açılıyor..."
Set-Location frontend
# npm ci kilit dosyasıyla birebir uyum ister; sürüm farkı olan bilgisayarlarda npm install daha toleranslı
if (-not (Test-Path "node_modules\.bin\vite.cmd")) { npm install --no-audit --no-fund; Kontrol "npm install" }
# Vite hazır olunca tarayıcı açılsın
Start-Process powershell -WindowStyle Hidden -ArgumentList '-NoProfile','-Command','Start-Sleep 5; Start-Process "http://127.0.0.1:5173/"'
Write-Host "`nHazır: http://127.0.0.1:5173/   API belgesi: http://127.0.0.1:8001/docs" -ForegroundColor Green
Write-Host "Kapatmak için Ctrl+C, ardından durdur.cmd`n" -ForegroundColor Green
npm run dev

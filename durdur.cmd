@echo off
cd /d "%~dp0"
docker compose stop
rem Acik kalan frontend (Vite, port 5173) da kapatilir
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { $p = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue; if ($p.ProcessName -eq 'node') { Stop-Process -Id $p.Id -Force } }"
echo Veritabani ve API durduruldu.
pause

@echo off
cd /d "%~dp0"
echo ASTRA HEALTH baslatiliyor...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0baslat.ps1"
echo.
echo Bitti. Bu pencereyi kapatmak icin bir tusa basin.
pause

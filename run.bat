@echo off
setlocal

REM Check that VPN is active before running
for /f "delims=" %%i in ('curl -s https://api.ipify.org') do set IP=%%i
set HOME_IP=23.115.156.177

if "%IP%" == "%HOME_IP%" (
    echo ERROR: VPN is not active! Please activate your VPN before running this script.
    exit /b 1
)

echo VPN is active. Current IP: %IP%

REM Run the auction scraper using uv
python main.py

@echo off
setlocal

REM Check if VPN check is enabled
if "%ENABLE_VPN_CHECK%" == "" (
    set ENABLE_VPN_CHECK=True
)

if /i "%ENABLE_VPN_CHECK%" == "True" (
    REM Check that VPN is active before running
    for /f "delims=" %%i in ('curl -s https://api.ipify.org') do set IP=%%i
    set HOME_IP=23.115.156.177

    if "%IP%" == "%HOME_IP%" (
        echo ERROR: VPN is not active! Please activate your VPN before running this script.
        exit /b 1
    )

    echo VPN is active. Current IP: %IP%
) else (
    echo WARNING: VPN check is disabled. Your IP may not be protected.
)

REM Run the auction scraper
python main.py

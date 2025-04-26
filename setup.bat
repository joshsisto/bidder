@echo off
setlocal

echo Setup script for the Auction Bot

REM Install Python dependencies
echo Installing Python dependencies...
pip install -r requirements.txt

REM Install Playwright browsers
echo Installing Playwright browsers...
python -m playwright install chromium

REM Check if Tesseract is installed
where tesseract >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo WARNING: Tesseract OCR not found in PATH.
    echo Please download and install Tesseract from:
    echo https://github.com/UB-Mannheim/tesseract/wiki
    echo.
    echo After installing, make sure the path in config.py points to your Tesseract installation.
    echo Default path: C:\Program Files\Tesseract-OCR\tesseract
)

echo Setup complete!
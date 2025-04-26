#!/bin/bash
# Setup script for the Auction Bot

# Detect OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux setup
    echo "Detected Linux system..."
    
    # Install Tesseract OCR and OpenCV dependencies
    echo "Installing Tesseract OCR and OpenCV dependencies..."
    sudo apt-get update
    sudo apt-get -y install tesseract-ocr libgl1-mesa-glx libsm6 libxext6 libxrender-dev
    
    # Verify Tesseract installation
    TESSERACT_VERSION=$(tesseract --version 2>/dev/null)
    if [ $? -eq 0 ]; then
        echo "✅ Tesseract installed successfully: $(echo "$TESSERACT_VERSION" | head -n 1)"
    else
        echo "❌ Failed to install Tesseract OCR. Please install it manually."
    fi
else
    # Windows or other OS
    echo "Detected non-Linux system. Please install Tesseract OCR manually if needed."
    echo "Windows: https://github.com/UB-Mannheim/tesseract/wiki"
fi

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Install Playwright browsers
echo "Installing Playwright browsers..."
python -m playwright install chromium

echo "Setup complete!"
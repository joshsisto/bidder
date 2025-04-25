"""
Configuration settings for the Auction Bot
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Create directory structure for output files
DATA_DIR = "data"
LOGS_DIR = os.path.join(DATA_DIR, "logs")
IMAGES_DIR = os.path.join(DATA_DIR, "images")
HTML_DIR = os.path.join(DATA_DIR, "html")
PROGRESS_DIR = os.path.join(DATA_DIR, "progress")
OUTPUT_DIR = os.path.join(DATA_DIR, "output")

# Create all required directories
for directory in [DATA_DIR, LOGS_DIR, IMAGES_DIR, HTML_DIR, PROGRESS_DIR, OUTPUT_DIR]:
    os.makedirs(directory, exist_ok=True)

# Configuration
HOME_IP = os.getenv('HOME_IP', "127.0.0.1")  # Your home IP to avoid
MAX_ITEMS = 100  # Maximum number of items to process
# AUCTION_URL = "https://www.bidrl.com/auction/high-end-auctions-9415-madison-ave-orangevale-ca-95662-april-25th-173079/bidgallery/perpage_NjA"
AUCTION_URL = "https://www.bidrl.com/auction/high-end-auction-415-richards-blvd-sacramento-ca-95811-may-2nd-173450/bidgallery/perpage_NjA"

# Search configuration
ENABLE_AMAZON_SEARCH = False  # Set to False to disable Amazon searches
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', "")
GOOGLE_CX = os.getenv('GOOGLE_CX', "")

# OCR Configuration
TESSERACT_PATH = r'C:\Program Files\Tesseract-OCR\tesseract'  # Update path if needed on different systems
TESSERACT_CONFIG = r'--oem 3 -l eng --psm 4'  # OCR Engine Mode 3, Page Segmentation Mode 4
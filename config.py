"""
Configuration settings for the Auction Bot
"""

import os
import logging
import platform
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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
ENABLE_VPN_CHECK = os.getenv('ENABLE_VPN_CHECK', 'True').lower() in ('true', '1', 't')  # VPN check toggle
HEADLESS_BROWSER = os.getenv('HEADLESS_BROWSER', 'True').lower() in ('true', '1', 't')  # Headless browser toggle
MAX_ITEMS = 100  # Maximum number of items to process
NETWORK_TIMEOUT = int(os.getenv('NETWORK_TIMEOUT', '60000'))  # Network timeout in milliseconds
# AUCTION_URL = "https://www.bidrl.com/auction/high-end-auctions-9415-madison-ave-orangevale-ca-95662-april-25th-173079/bidgallery/perpage_NjA"
AUCTION_URL = "https://www.bidrl.com/auction/highend-auction-212-harding-blvd-ste-g-roseville-ca-95678-may-2nd-173431/bidgallery/page_NQ"

# Search configuration
ENABLE_AMAZON_SEARCH = os.getenv('ENABLE_AMAZON_SEARCH', 'False').lower() in ('true', '1', 't')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', "")
GOOGLE_CX = os.getenv('GOOGLE_CX', "")
USE_GOOGLE_API = os.getenv('USE_GOOGLE_API', 'True').lower() in ('true', '1', 't') and GOOGLE_API_KEY and GOOGLE_CX

# Object detection configuration
CLOUD_VISION_ENABLED = os.getenv('CLOUD_VISION_ENABLED', 'False').lower() in ('true', '1', 't')
OBJECT_DETECTION_ENABLED = os.getenv('OBJECT_DETECTION_ENABLED', 'True').lower() in ('true', '1', 't')
PRODUCT_SEARCH_ENABLED = os.getenv('PRODUCT_SEARCH_ENABLED', 'True').lower() in ('true', '1', 't')

# OCR Configuration
# Determine Tesseract path based on operating system
if platform.system() == 'Windows':
    TESSERACT_PATH = os.getenv('TESSERACT_PATH', r'C:\Program Files\Tesseract-OCR\tesseract')
else:  # Linux/Mac
    TESSERACT_PATH = os.getenv('TESSERACT_PATH', '/usr/bin/tesseract')
    
# OCR configuration
TESSERACT_CONFIG = r'--oem 3 -l eng --psm 4'  # OCR Engine Mode 3, Page Segmentation Mode 4

# LLM-based search query generation
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', "")
OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', "anthropic/claude-3-opus-20240229")
OPENROUTER_ENABLED = os.getenv('OPENROUTER_ENABLED', 'False').lower() in ('true', '1', 't') and OPENROUTER_API_KEY
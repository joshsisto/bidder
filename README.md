# Auction Bot

A modular web scraping bot for finding profitable auction items.

## Project Structure

```
auction_bot/
│
├── main.py                  # Entry point script
├── config.py                # Configuration settings
│
├── utils/
│   ├── __init__.py
│   ├── logger.py            # Logging configuration
│   └── file_utils.py        # File handling utilities
│
├── scraper/
│   ├── __init__.py
│   ├── auction_bot.py       # Main AuctionBot class
│   ├── item_extractor.py    # Item detail extraction
│   ├── image_processor.py   # Image processing and OCR
│   └── price_finder.py      # Price research (Google, Amazon)
│
└── analyzer/
    ├── __init__.py
    └── report_generator.py  # Excel report generation
```

## Features

- Scrapes auction websites to extract item details
- Processes images with OCR to enhance item descriptions
- Searches Google and Amazon for market prices
- Calculates potential profit margins
- Generates detailed Excel reports
- VPN protection to hide your real IP address

## Requirements

- Python 3.8+
- Playwright for browser automation
- Tesseract OCR for image processing
- Google Custom Search API credentials

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/auction-bot.git
cd auction-bot
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install playwright pandas pytesseract pillow aiohttp fake-useragent google-api-python-client beautifulsoup4 requests
```

4. Install Playwright browsers:
```bash
python -m playwright install
```

5. Install Tesseract OCR:
   - Windows: Download and install from https://github.com/UB-Mannheim/tesseract/wiki
   - macOS: `brew install tesseract`
   - Linux: `sudo apt install tesseract-ocr`

## Configuration

Edit `config.py` to set your preferences:

- `HOME_IP`: Your home IP address to verify VPN is active
- `MAX_ITEMS`: Maximum number of items to process
- `AUCTION_URL`: URL of the auction to scrape
- `ENABLE_AMAZON_SEARCH`: Enable/disable Amazon price searches
- `GOOGLE_API_KEY`: Your Google API key
- `GOOGLE_CX`: Your Google Custom Search Engine ID
- `TESSERACT_PATH`: Path to Tesseract OCR executable

## Usage

Run the main script:

```bash
python main.py
```

The script will:
1. Verify your VPN is active
2. Scrape auction items
3. Process images with OCR
4. Research market prices
5. Generate an Excel report of profitable items

## Output

All output files are saved in the `data/` directory:
- `data/logs/`: Log files
- `data/images/`: Downloaded and processed images
- `data/html/`: Saved HTML content
- `data/progress/`: Progress JSON files
- `data/output/`: Final Excel reports

## Customization

To adapt this bot for different auction sites:
1. Modify the selectors in `scraper/auction_bot.py`
2. Update the item extraction logic in `scraper/item_extractor.py`
3. Adjust OCR settings in `config.py` for optimal text recognition

## License

MIT
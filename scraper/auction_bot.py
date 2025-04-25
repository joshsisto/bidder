"""
Main AuctionBot class that coordinates the auction scraping process
"""

import os
import re
import time
import random
import asyncio
import traceback
import requests

from config import MAX_ITEMS, HOME_IP, AUCTION_URL
from utils.logger import setup_logger
from utils.file_utils import save_json, save_html
from scraper.item_extractor import ItemExtractor
from scraper.image_processor import ImageProcessor
from scraper.price_finder import PriceFinder

# Set up logger
logger = setup_logger("AuctionBot")

class AuctionBot:
    """Main class to scrape auction sites for profitable items"""
    
    def __init__(self):
        """Initialize the AuctionBot with required components"""
        self.items = []
        self.ua = self._get_user_agent()
        self.session = None
        self.page = None
        self.playwright = None
        self.browser = None
        self.context = None
        self.price_finder = PriceFinder()
        
        # Define fallback selectors for different elements
        self.selectors = {
            'items': [
                '.aucbox',  # Main container for each auction item
                '.bidgridbox',  # Alternative container
                '.bid-gallery-item', 
                '.auction-item',
                '.item-card',
                '.lot-item',
                'div[data-lot-id]'
            ],
            'lot_number': [
                'b:contains("Lot #")',  # Looks for text that contains "Lot #"
                '.lot-number',
                '.item-lot-number',
                '.lot-id'
            ],
            'description': [
                '.gridbox-item-title b',  # Title/description element
                'li.gridbox-item-title b',  # Alternative title element
                '.title',
                '.item-title',
                '.description',
                '.item-description'
            ],
            'bid': [
                'span.float-right[data-currency]',  # Current bid amount
                'li:contains("Current Bid:") span.float-right',  # Alternative bid element
                '.amount',
                '.current-bid',
                '.price',
                '.bid-amount'
            ],
            'time': [
                'li:contains("Time Remaining:") span.float-right span',  # Time remaining element
                'span:contains("H, "):contains("M, "):contains("S")',  # Time in H, M, S format
                '.time-left',
                '.countdown',
                '.auction-end-time',
                '.time-remaining'
            ],
            'images': [
                '.itemlist-image-slider img',  # Image elements
                'a.pic img',  # Alternative image element
                'light-gallery li[data-src]',  # Light gallery images
                'light-gallery img[data-src]',  # Alternative light gallery images
                'img[src*="auctionimages"]'  # Images from auctionimages domain
            ],
            'link': [
                '.gridbox-item-title a',  # Link to item detail
                'a.pic',  # Alternative link element
                'a',
                '.item-link',
                '.view-details'
            ]
        }
    
    def _get_user_agent(self):
        """Get a random user agent"""
        try:
            from fake_useragent import UserAgent
            return UserAgent()
        except ImportError:
            logger.warning("fake_useragent not installed. Using fallback user agent.")
            # Fallback to a static user agent
            return type('UserAgent', (), {'random': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'})
    
    def check_ip_safe(self):
        """Verify VPN is active by checking current IP is not the home IP"""
        try:
            current_ip = requests.get('https://api.ipify.org').text
            if current_ip == HOME_IP:
                logger.error("USING HOME IP! VPN is not active or not working properly. Please activate your VPN before running this script.")
                return False
            logger.info(f"VPN CHECK PASSED! Using IP: {current_ip} (not your home IP)")
            return True
        except Exception as e:
            logger.error(f"Could not check IP: {e}")
            return False
    
    async def setup_browser(self):
        """Set up browser using Playwright with extensive error logging"""
        try:
            # Import here to avoid requiring it if not needed
            from playwright.async_api import async_playwright
            
            logger.info("Setting up browser with Playwright")
            self.playwright = await async_playwright().start()
            
            # Launch with chromium (Playwright will download if needed)
            logger.debug("Launching chromium browser")
            self.browser = await self.playwright.chromium.launch(
                headless=False,  # Set to True in production
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ]
            )
            
            # Create a new context with random user agent
            logger.debug(f"Creating new browser context with user agent: {self.ua.random}")
            self.context = await self.browser.new_context(
                user_agent=self.ua.random,
                viewport={"width": 1920, "height": 1080}
            )
            
            # Create a new page
            logger.debug("Creating new page")
            self.page = await self.context.new_page()
            
            logger.info("Successfully set up browser with Playwright")
            return self.page
        except ImportError as e:
            logger.error(f"Playwright not installed: {e}")
            logger.error("Please install Playwright with: pip install playwright")
            logger.error("And then install the browsers with: python -m playwright install")
            return None
        except Exception as e:
            logger.error(f"Error setting up browser with Playwright: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    async def cleanup_browser(self):
        """Clean up browser resources"""
        try:
            if self.browser:
                logger.debug("Closing browser")
                await self.browser.close()
            if self.playwright:
                logger.debug("Stopping playwright")
                await self.playwright.stop()
        except Exception as e:
            logger.error(f"Error cleaning up browser: {e}")
    
    async def analyze_page_structure(self, url):
        """Analyze page structure and log element counts for debugging"""
        if not self.page:
            logger.error("No page available to analyze")
            return
        
        logger.info(f"Analyzing page structure for: {url}")
        
        try:
            # Navigate to the URL
            logger.debug(f"Navigating to {url}")
            await self.page.goto(url, wait_until="networkidle")
            
            # Wait for content to load - bidrl.com might need more time
            await asyncio.sleep(5)  # Increased wait time
            
            # Get the page HTML and save it for analysis
            html_content = await self.page.content()
            html_filepath = save_html(html_content, "page_structure")
            logger.debug(f"Saved HTML content to {html_filepath}")
            
            # Find working selectors
            working_selectors = await ItemExtractor.find_working_selectors(self.page, self.selectors)
            
            return working_selectors
        except Exception as e:
            logger.error(f"Error analyzing page structure: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    async def process_all_items(self):
        """Process all items in the auction, one by one"""
        # Verify VPN is active before proceeding
        if not self.check_ip_safe():
            logger.error("VPN check failed. Please ensure your VPN is active and working.")
            return False
        
        logger.info(f"Starting to process auction at {AUCTION_URL} with VPN protection")
        
        try:
            # Set up browser
            page = await self.setup_browser()
            if not page:
                logger.error("Failed to set up browser")
                return False
            
            # Analyze page structure to find working selectors
            logger.info("Analyzing auction page structure")
            working_selectors = await self.analyze_page_structure(AUCTION_URL)
            
            if not working_selectors:
                logger.error("Could not find working selectors for elements")
                return False
            
            # Get item URLs
            logger.info("Getting item URLs")
            item_urls = await ItemExtractor.get_item_urls(self.page, working_selectors)
            
            if not item_urls:
                logger.error("No item URLs found")
                return False
            
            # Limit to MAX_ITEMS
            if len(item_urls) > MAX_ITEMS:
                logger.info(f"Limiting to {MAX_ITEMS} items")
                item_urls = item_urls[:MAX_ITEMS]
            
            # Process each item one by one
            self.items = []
            for i, url in enumerate(item_urls):
                try:
                    logger.info(f"Processing item {i+1}/{len(item_urls)}: {url}")
                    
                    # Extract item details
                    item = await ItemExtractor.extract_item_details(self.page, url)
                    
                    if not item:
                        logger.warning(f"Failed to extract details for item at {url}, skipping")
                        continue
                    
                    # Process item images
                    item = await ImageProcessor.process_images(item)
                    
                    # Add to items list
                    self.items.append(item)
                    
                    # Save progress after each item
                    save_json(self.items, f"progress_{i+1}_of_{len(item_urls)}.json")
                    
                    # Add delay to avoid overloading
                    await asyncio.sleep(random.uniform(1, 3))
                    
                except Exception as e:
                    logger.error(f"Error processing item {i+1}: {e}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
            
            logger.info(f"Successfully processed {len(self.items)} items")
            return True
        
        except Exception as e:
            logger.error(f"Error processing auction items: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
        
        finally:
            # Clean up browser resources
            await self.cleanup_browser()
    
    def determine_market_prices(self):
        """Determine market prices for all items"""
        logger.info("Starting market price research")
        
        for i, item in enumerate(self.items):
            logger.info(f"Researching price for item {i+1}/{len(self.items)}: {item.get('lotNumber', 'Unknown')}")
            
            # Get current bid as float
            current_bid_str = item.get('currentBid', '').replace('$', '').replace(',', '')
            try:
                current_bid = float(current_bid_str)
                logger.debug(f"Current bid: ${current_bid}")
            except ValueError:
                logger.warning(f"Could not parse current bid: {item.get('currentBid', '')}")
                current_bid = 0.0
                
            item['current_bid_float'] = current_bid
            
            # Get market price
            market_price = self.price_finder.get_best_market_price(item)
            item['market_price'] = market_price
            
            # Calculate potential profit
            item['potential_profit'] = market_price - current_bid if market_price > 0 else 0
            logger.info(f"Potential profit: ${item['potential_profit']:.2f}")
            
            # Add delay to avoid overloading APIs or getting blocked
            time.sleep(random.uniform(1, 3))
            
            # Save progress after each item
            save_json(self.items, f"price_progress_{i+1}_of_{len(self.items)}.json")
        
        logger.info("Market price research completed")
        return True

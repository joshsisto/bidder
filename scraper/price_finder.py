"""
Price research functionality for auction items
"""

import re
import time
import random
import requests
import traceback
from bs4 import BeautifulSoup
from googleapiclient.discovery import build

from config import GOOGLE_API_KEY, GOOGLE_CX, ENABLE_AMAZON_SEARCH, HTML_DIR
from utils.logger import setup_logger
from utils.file_utils import save_html

# Set up logger
logger = setup_logger("PriceFinder")

class PriceFinder:
    """Find market prices for auction items using various sources"""
    
    def __init__(self):
        """Initialize the price finder with a User-Agent generator"""
        self.ua = self._get_user_agent()
    
    def _get_user_agent(self):
        """Get a random user agent"""
        try:
            from fake_useragent import UserAgent
            return UserAgent()
        except ImportError:
            logger.warning("fake_useragent not installed. Using fallback user agent.")
            # Fallback to a static user agent
            return type('UserAgent', (), {'random': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'})
    
    def clean_price_string(self, price_str):
        """Clean price string to extract numerical value"""
        if not price_str:
            return 0.0
                
        # Remove currency symbols and other non-numeric characters
        clean_str = re.sub(r'[^\d.]', '', price_str)
            
        try:
            return float(clean_str)
        except ValueError:
            return 0.0
    
    def search_google_for_price(self, query):
        """Search Google for prices of the item"""
        try:
            # Clean up the query to remove lot numbers and irrelevant information
            clean_query = query
            
            # Remove lot numbers from query
            clean_query = re.sub(r'Lot #.*?:', '', clean_query)
            clean_query = re.sub(r'OAD\d+', '', clean_query)  # Remove specific lot number formats
            
            # Filter to only allow alphanumeric characters for the search query
            clean_query = re.sub(r'[^a-zA-Z0-9\s]', ' ', clean_query)
            clean_query = re.sub(r'\s+', ' ', clean_query).strip()
            
            # Limit query length to avoid overly specific searches
            if len(clean_query) > 100:
                clean_query = clean_query[:100]
            
            logger.info(f"Searching Google for price of: {clean_query}")
            
            # Check if API keys are provided
            if not GOOGLE_API_KEY or not GOOGLE_CX:
                logger.warning("Google API key or CX ID not provided. Skipping Google search.")
                return None
            
            # Build the search service with proper cache settings
            service = build("customsearch", "v1", 
                           developerKey=GOOGLE_API_KEY,
                           cache_discovery=False)  # Avoid file_cache warning
            
            # Execute the search with proper error handling
            try:
                result = service.cse().list(
                    q=f"{clean_query} price", 
                    cx=GOOGLE_CX, 
                    num=5
                ).execute()
            except Exception as api_error:
                logger.error(f"Google API request failed: {api_error}")
                return None
            
            if "items" not in result:
                logger.warning("No items found in Google search results")
                return None
                
            prices = []
            for item in result["items"]:
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                
                # Log the search results for debugging
                logger.debug(f"Search result: {title} - {snippet[:100]}")
                
                # Look for price patterns in title and snippet
                price_patterns = [
                    r'\$\s?(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)',  # $123,456.78
                    r'(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)(?:\s?USD|\s?dollars|\s?\$)',  # 123,456.78 USD
                    r'Price[:;]\s*\$?(\d+(?:\.\d{1,2})?)',  # Price: $123.45 or Price: 123.45
                    r'(\d+(?:\.\d{1,2})?)(?:\s?USD|\s?dollars|\s?\$)',  # Simple price like 123.45 USD
                ]
                
                for pattern in price_patterns:
                    for text in [title, snippet]:
                        matches = re.findall(pattern, text)
                        for match in matches:
                            # If match is a tuple (from regex groups), use the first item
                            if isinstance(match, tuple) and match:
                                match = match[0]
                                
                            price = self.clean_price_string(match)
                            if price > 0:
                                prices.append(price)
                                logger.debug(f"Found price in {title[:30]}: ${price}")
            
            if prices:
                # Filter out extreme values (removes outliers)
                if len(prices) > 3:
                    prices.sort()
                    # Remove the highest and lowest prices
                    prices = prices[1:-1]
                
                # Return median price
                prices.sort()
                median_price = prices[len(prices) // 2]
                logger.info(f"Found median price from Google: ${median_price}")
                return median_price
            else:
                logger.warning("No prices found in Google search results")
                return None
        except Exception as e:
            logger.error(f"Error searching Google for price: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Fall back to Amazon search
            logger.info("Falling back to Amazon search...")
            return None
    
    def search_amazon_for_price(self, query):
        """Search Amazon for price using direct HTTP requests"""
        try:
            # Clean up the query to remove lot numbers and irrelevant information
            clean_query = query
            
            # Remove lot numbers from query
            clean_query = re.sub(r'Lot #.*?:', '', clean_query)
            clean_query = re.sub(r'OAD\d+', '', clean_query)  # Remove specific lot number formats
            
            # Remove non-English characters - only keep a-z, A-Z, 0-9, and spaces
            clean_query = re.sub(r'[^a-zA-Z0-9\s]', ' ', clean_query)
            clean_query = re.sub(r'\s+', ' ', clean_query).strip()
            
            # Limit query length for better search results
            if len(clean_query) > 100:
                clean_query = clean_query[:100]
            
            logger.info(f"Searching Amazon for price of: {clean_query}")
            
            # Add random delay to avoid rate limiting
            time.sleep(random.uniform(1, 3))
            
            headers = {
                'User-Agent': self.ua.random,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://www.google.com/',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Cache-Control': 'no-cache',
            }
            
            # Format the search URL
            url = f"https://www.amazon.com/s?k={clean_query.replace(' ', '+')}"
            logger.debug(f"Amazon search URL: {url}")
            
            # Make the request with timeout
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"Amazon search failed: HTTP {response.status_code}")
                return None
                
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Save Amazon response for debugging
            save_html(response.text, f"amazon_search_{clean_query[:20]}")
            
            # Look for price elements
            prices = []
            
            # Try different price selectors (Amazon structure)
            price_selectors = [
                '.a-price .a-offscreen',  # Primary price selector
                '.a-price-whole',         # Whole number part
                '.a-color-price',         # Generic price class
                '.a-size-base .a-color-price',  # Another common format
                '.a-price'                # Container element
            ]
            
            for selector in price_selectors:
                price_elements = soup.select(selector)
                logger.debug(f"Found {len(price_elements)} elements with selector '{selector}'")
                
                for elem in price_elements[:10]:  # Get first 10 prices (more data)
                    try:
                        price_text = elem.text.strip()
                        logger.debug(f"Found price text: {price_text}")
                        
                        price = self.clean_price_string(price_text)
                        if price > 0 and price < 10000:  # Filter out unreasonably high prices
                            prices.append(price)
                            logger.debug(f"Extracted price: ${price}")
                    except Exception as e:
                        logger.error(f"Error parsing Amazon price: {e}")
            
            if prices:
                # Filter out extreme values
                if len(prices) > 3:
                    prices.sort()
                    # Remove the highest and lowest prices if we have enough data
                    prices = prices[1:-1]
                
                # Return median price
                prices.sort()
                median_price = prices[len(prices) // 2]
                logger.info(f"Found median price from Amazon: ${median_price}")
                return median_price
            else:
                logger.warning("No prices found in Amazon search results")
                
                # Try a generic price range as fallback
                return self.estimate_price_from_description(clean_query)
        except Exception as e:
            logger.error(f"Error searching Amazon for price: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
            
    def estimate_price_from_description(self, description):
        """Estimate a price based on keywords in the description as last resort"""
        try:
            # Look for clues in the description
            lower_desc = description.lower()
            
            # Define price tiers based on keywords
            high_value_keywords = ['premium', 'professional', 'high-end', 'luxury', 'gold', 'platinum', 'diamond']
            mid_value_keywords = ['quality', 'leather', 'wireless', 'bluetooth', 'digital', 'stainless']
            low_value_keywords = ['basic', 'simple', 'mini', 'small', 'plastic']
            
            # Default base price
            base_price = 25.0
            
            # Adjust based on keywords
            for keyword in high_value_keywords:
                if keyword in lower_desc:
                    base_price += 50.0
                    logger.debug(f"Added high-value keyword bonus for: {keyword}")
            
            for keyword in mid_value_keywords:
                if keyword in lower_desc:
                    base_price += 15.0
                    logger.debug(f"Added mid-value keyword bonus for: {keyword}")
            
            for keyword in low_value_keywords:
                if keyword in lower_desc:
                    base_price -= 5.0
                    logger.debug(f"Subtracted low-value keyword penalty for: {keyword}")
            
            # Ensure minimum reasonable price
            estimated_price = max(base_price, 10.0)
            
            logger.info(f"Estimated fallback price from description: ${estimated_price:.2f}")
            return estimated_price
            
        except Exception as e:
            logger.error(f"Error estimating price from description: {e}")
            return 25.0  # Default fallback price
    
    def get_best_market_price(self, item):
        """Get the best market price from multiple sources"""
        search_query = item.get('enhanced_description', '') or item.get('description', '')
        if not search_query:
            logger.warning(f"No search query available for item: {item.get('lotNumber', 'Unknown')}")
            return 0.0
                
        logger.info(f"Researching market price for item: {item.get('lotNumber', 'Unknown')}")
            
        # Try Google first
        google_price = self.search_google_for_price(search_query)
            
        # Try Amazon as fallback if enabled
        amazon_price = None
        if (not google_price or google_price == 0) and ENABLE_AMAZON_SEARCH:
            logger.info("Google search yielded no results, trying Amazon...")
            amazon_price = self.search_amazon_for_price(search_query)
        elif not ENABLE_AMAZON_SEARCH:
            logger.info("Amazon search is disabled, skipping")
            
        # Use the best available price
        if google_price and google_price > 0:
            logger.info(f"Using Google price: ${google_price}")
            return google_price
        elif amazon_price and amazon_price > 0:
            logger.info(f"Using Amazon price: ${amazon_price}")
            return amazon_price
        else:
            logger.warning(f"No price found for: {search_query[:50]}...")
            # Use fallback price estimation
            return self.estimate_price_from_description(search_query)
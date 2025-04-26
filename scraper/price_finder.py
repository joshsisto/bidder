"""
Price research functionality for auction items
"""

import re
import time
import random
import json
import requests
import traceback
import aiohttp
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

from config import GOOGLE_API_KEY, GOOGLE_CX, ENABLE_AMAZON_SEARCH, HTML_DIR, USE_GOOGLE_API, OPENROUTER_ENABLED
from utils.logger import setup_logger
from utils.file_utils import save_html
from scraper.llm_query_generator import LLMQueryGenerator

# Set up logger
logger = setup_logger("PriceFinder")

class PriceFinder:
    """Find market prices for auction items using various sources"""
    
    def __init__(self):
        """Initialize the price finder with a User-Agent generator"""
        self.ua = self._get_user_agent()
        self.search_session = None
    
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
    
    async def _fallback_google_search(self, query):
        """
        Simpler fallback approach for Google search when the API fails
        Uses a direct search URL and scrapes results
        """
        try:
            logger.info(f"Using fallback Google search for: {query}")
            
            # Simplify the query
            simple_query = query.split()[:5]  # Use only first 5 words
            simple_query = ' '.join(simple_query) + " price"
            
            # Create a search URL
            search_url = f"https://www.google.com/search?q={quote_plus(simple_query)}"
            
            # Set up headers to look like a browser
            headers = {
                'User-Agent': self.ua.random,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://www.google.com/',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            # Initialize a session if needed
            if not self.search_session:
                self.search_session = aiohttp.ClientSession()
            
            async with self.search_session.get(search_url, headers=headers, timeout=30) as response:
                if response.status != 200:
                    logger.warning(f"Fallback Google search failed: HTTP {response.status}")
                    return None
                
                html_content = await response.text()
            
            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Look for price patterns in the page
            # Common price patterns
            price_patterns = [
                r'\$\s?(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)',  # $123,456.78
                r'(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)(?:\s?USD|\s?dollars|\s?\$)',  # 123,456.78 USD
                r'Price[:;]\s*\$?(\d+(?:\.\d{1,2})?)',  # Price: $123.45 or Price: 123.45
                r'(\d+(?:\.\d{1,2})?)(?:\s?USD|\s?dollars|\s?\$)',  # Simple price like 123.45 USD
            ]
            
            prices = []
            page_text = soup.get_text()
            
            # Extract all prices from the page
            for pattern in price_patterns:
                matches = re.findall(pattern, page_text)
                for match in matches:
                    # If match is a tuple (from regex groups), use the first item
                    if isinstance(match, tuple) and match:
                        match = match[0]
                        
                    price = self.clean_price_string(match)
                    if price > 0 and price < 10000:  # Filter unrealistic prices
                        prices.append(price)
            
            if prices:
                # Filter outliers
                if len(prices) > 3:
                    prices.sort()
                    prices = prices[1:-1]  # Remove highest and lowest
                
                # Calculate median
                prices.sort()
                median_price = prices[len(prices) // 2]
                logger.info(f"Found median price from fallback Google search: ${median_price}")
                return median_price
            else:
                logger.warning("No prices found in fallback Google search")
                return None
                
        except Exception as e:
            logger.error(f"Error in fallback Google search: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    async def search_google_for_price(self, query):
        """Search Google for prices of the item - using custom search API or fallback"""
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
            
            # Check if we should use the Google API
            if not USE_GOOGLE_API:
                logger.info("Google API not enabled or missing credentials. Using fallback search.")
                return await self._fallback_google_search(clean_query)
            
            # Build the URL - using direct API to avoid problems with the SDK
            # Make sure query is not too long (Google has length limits)
            if len(clean_query) > 100:
                clean_query = clean_query[:100]
            
            search_query = f"{clean_query} price"
            
            # Properly encode parameters to avoid invalid argument errors
            params = {
                'key': GOOGLE_API_KEY,
                'cx': GOOGLE_CX,
                'q': search_query,
                'num': 5
            }
            
            # Construct the URL with proper URL encoding
            url = "https://www.googleapis.com/customsearch/v1?" + "&".join(f"{k}={quote_plus(str(v))}" for k, v in params.items())
            
            # Initialize a session if needed
            if not self.search_session:
                self.search_session = aiohttp.ClientSession()
            
            # Log the URL for debugging (remove in production)
            logger.debug(f"Google API request URL: {url}")
            
            try:
                async with self.search_session.get(url, timeout=30) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Google API request failed: Status {response.status}")
                        logger.error(f"Error response: {error_text}")
                        logger.error(f"Search query was: {search_query}")
                        # Try a simpler approach as fallback
                        return await self._fallback_google_search(clean_query)
                    
                    result = await response.json()
            except Exception as e:
                logger.error(f"Exception during Google API request: {e}")
                return await self._fallback_google_search(clean_query)
            
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
            return None
    
    async def search_amazon_for_price(self, query):
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
            await asyncio.sleep(random.uniform(1, 3))
            
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
            
            # Initialize a session if needed
            if not self.search_session:
                self.search_session = aiohttp.ClientSession()
            
            async with self.search_session.get(url, headers=headers, timeout=30) as response:
                if response.status != 200:
                    logger.error(f"Amazon search failed: HTTP {response.status}")
                    return None
                
                html_content = await response.text()
            
            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Save Amazon response for debugging
            save_html(html_content, f"amazon_search_{clean_query[:20]}")
            
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
            
            # Use detected category and brands to improve estimation
            category_base_prices = {
                'electronics': 100.0,
                'furniture': 120.0,
                'appliances': 150.0,
                'tools': 80.0,
                'jewelry': 200.0,
                'art': 150.0,
                'clothing': 40.0,
                'sports': 75.0,
                '': 50.0  # Default
            }
            
            # Brand value modifiers
            premium_brands = ['sony', 'samsung', 'apple', 'dyson', 'bose', 'microsoft']
            budget_brands = ['rca', 'onn', 'bestbuy', 'insignia']
            
            # Default base price (fallback)
            base_price = 50.0
            
            # Adjust based on keywords and complexity of description
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
            
            # Size/quantity adjustments
            if re.search(r'set of \d+', lower_desc) or re.search(r'\d+ piece', lower_desc):
                base_price *= 1.5
                logger.debug("Added multi-piece bonus")
            
            # Number modifiers
            number_match = re.search(r'(\d+)(?:"|inch|in)', lower_desc)
            if number_match:
                # Adjust price based on size (e.g., TV inches)
                size = int(number_match.group(1))
                if size > 32:  # If something is over 32 inches, it's likely valuable
                    base_price += (size - 32) * 5
                    logger.debug(f"Added size bonus for {size} inches")
            
            # Ensure minimum reasonable price
            estimated_price = max(base_price, 10.0)
            
            logger.info(f"Estimated fallback price from description: ${estimated_price:.2f}")
            return estimated_price
            
        except Exception as e:
            logger.error(f"Error estimating price from description: {e}")
            return 25.0  # Default fallback price
    
    async def get_best_market_price(self, item):
        """Get the best market price from multiple sources"""
        try:
            search_query = None
            amazon_query = None
            google_query = None
            
            # First, try to use LLM-generated queries if available and enabled
            if OPENROUTER_ENABLED:
                logger.info(f"Trying LLM-based search query generation for item: {item.get('lotNumber', 'Unknown')}")
                try:
                    llm_results = await LLMQueryGenerator.generate_search_query(item)
                    
                    if llm_results and "error" not in llm_results:
                        # Store the identified product information
                        item['llm_product_info'] = {
                            'product_type': llm_results.get('product_type', 'Unknown'),
                            'brand': llm_results.get('brand', 'Unknown'),
                            'model': llm_results.get('model', 'Unknown'),
                            'attributes': llm_results.get('attributes', 'N/A')
                        }
                        
                        # Check if the item should be skipped due to insufficient identification
                        if llm_results.get('insufficient_identification', False):
                            logger.warning(f"Item {item.get('lotNumber', 'Unknown')} has insufficient LLM identification, marking to skip")
                            item['skip_for_processing'] = True
                            # Skip the rest of price finding for this item
                            return 0.0
                        
                        # Get the generated search queries
                        google_query = llm_results.get('google_query')
                        amazon_query = llm_results.get('amazon_query')
                        
                        if google_query:
                            search_query = google_query
                            logger.info(f"Using LLM-generated Google query: {search_query}")
                        
                        # Log the identified product info
                        logger.info(f"LLM identified: {llm_results.get('brand')} {llm_results.get('model')} ({llm_results.get('product_type')})")
                    else:
                        if "error" in llm_results:
                            logger.warning(f"LLM query generation error: {llm_results['error']}")
                except Exception as e:
                    logger.error(f"Error during LLM query generation: {e}")
            
            # If LLM didn't produce a query, fall back to traditional methods
            if not search_query:
                # Try various existing query options in order of preference
                if item.get('final_search_query'):
                    search_query = item['final_search_query']
                    logger.info(f"Using final search query: {search_query}")
                elif item.get('rich_search_query'):
                    search_query = item['rich_search_query']
                    logger.info(f"Using rich search query: {search_query}")
                else:
                    search_query = item.get('enhanced_description', '') or item.get('description', '')
                    logger.info(f"Using enhanced description as search query")
            
            if not search_query:
                logger.warning(f"No search query available for item: {item.get('lotNumber', 'Unknown')}")
                return 0.0
                    
            logger.info(f"Researching market price for item: {item.get('lotNumber', 'Unknown')}")
            
            # Try to use product info to improve pricing if not using LLM query
            if not OPENROUTER_ENABLED or "error" in item.get('llm_product_info', {}):
                product_info = item.get('product_info', {})
                category = product_info.get('category', '')
                confidence = product_info.get('confidence', 0.0)
                
                # If we have high confidence product info, add category to search
                if confidence > 0.6 and category and category not in search_query.lower():
                    search_query = f"{search_query} {category}"
                    logger.info(f"Enhanced search query with category: {search_query}")
            
            # Store the final search query used
            item['used_search_query'] = search_query
                
            # Try Google first
            google_price = await self.search_google_for_price(search_query)
                
            # Try Amazon as fallback if enabled
            amazon_price = None
            if (not google_price or google_price == 0) and ENABLE_AMAZON_SEARCH:
                logger.info("Google search yielded no results, trying Amazon...")
                # Use the Amazon-specific query if available from LLM
                amazon_search_query = amazon_query if amazon_query else search_query
                amazon_price = await self.search_amazon_for_price(amazon_search_query)
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
        except Exception as e:
            logger.error(f"Error in get_best_market_price: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return 25.0  # Default fallback price
    
    async def close(self):
        """Close the search session"""
        if self.search_session:
            await self.search_session.close()
            self.search_session = None
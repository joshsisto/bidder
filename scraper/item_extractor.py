"""
Extract auction item details from web pages
"""

import re
import traceback
from bs4 import BeautifulSoup

from utils.logger import setup_logger
from utils.file_utils import save_html

# Set up logger
logger = setup_logger("ItemExtractor")

class ItemExtractor:
    """Extract auction item details from web pages"""
    
    @staticmethod
    async def extract_item_details(page, url):
        """Extract details for a single item"""
        if not page:
            logger.error("No page available to extract item details")
            return None
        
        logger.info(f"Extracting details for item at: {url}")
        
        try:
            # Navigate to the item page
            logger.debug(f"Navigating to {url}")
            await page.goto(url, wait_until="networkidle")
            
            # Wait for content to load
            await page.wait_for_timeout(5000)  # Wait 5 seconds
            
            # Get the page HTML for analysis with BeautifulSoup
            html = await page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # Log the item page HTML structure for analysis if needed
            html_filepath = save_html(html, f"item_page_{url.split('/')[-1]}")
            logger.debug(f"Saved HTML content to {html_filepath}")
            
            # Extract lot number and description - specific for bidrl.com format
            lot_number = ""
            description = ""
            
            # Look for the item head section which contains both lot number and description
            item_head = soup.select_one('div.item-head')
            if item_head:
                # Find the h4 element containing both lot number and description
                h4_element = item_head.select_one('h4')
                if h4_element:
                    # Extract the full text which includes both lot number and title
                    full_title_text = h4_element.text.strip()
                    logger.debug(f"Found title text: {full_title_text}")
                    
                    # Try to parse lot number and description from the full text
                    if 'Lot #' in full_title_text and ':' in full_title_text:
                        parts = full_title_text.split(':', 1)
                        lot_number = parts[0].strip()
                        description = parts[1].strip() if len(parts) > 1 else ""
                    else:
                        # Alternate approach: look for specific spans
                        lot_span = h4_element.select_one('span[ng-if*="lot_number"]')
                        if lot_span:
                            lot_number = lot_span.text.strip()
                        
                        desc_span = h4_element.select_one('span[ng-bind-html="item.title"]')
                        if desc_span:
                            description = desc_span.text.strip()
            
            if not lot_number:
                # Fallback: Look for any element containing "Lot #"
                for element in soup.find_all(['h4', 'span', 'b']):
                    if 'Lot #' in element.text:
                        lot_number = element.text.strip()
                        logger.debug(f"Found lot number with fallback: {lot_number}")
                        break
            
            logger.info(f"Extracted lot number: {lot_number}")
            logger.info(f"Extracted description: {description}")
            
            # Extract current bid - updated for bidrl.com
            current_bid = ""
            
            # First, look for the specific structure from the HTML example
            current_bid_header = soup.find('b', text='Current Bid:')
            if current_bid_header and current_bid_header.parent:
                # Look for the span with data-currency attribute near the header
                bid_span = current_bid_header.find_next('span', attrs={'data-currency': True})
                if bid_span:
                    current_bid = bid_span.text.strip()
                    logger.debug(f"Found current bid: {current_bid}")
            
            # If not found with the above approach, try alternative selectors
            if not current_bid:
                bid_spans = soup.select('span[data-currency]')
                if bid_spans:
                    current_bid = bid_spans[0].text.strip()
                    logger.debug(f"Found current bid with alternative selector: {current_bid}")
            
            # Extract time remaining - updated for bidrl.com
            time_remaining = ""
            
            # First, look for the specific structure from the HTML example
            time_remaining_header = soup.find('b', text='Time Remaining:')
            if time_remaining_header and time_remaining_header.parent:
                # Find the next div which contains the time
                time_div = time_remaining_header.find_next('div')
                if time_div:
                    time_text = time_div.get_text(strip=True)
                    # Check if it matches the expected format
                    if 'H,' in time_text and 'M,' in time_text and 'S' in time_text:
                        time_remaining = time_text
                        logger.debug(f"Found time remaining: {time_remaining}")
            
            # Fallback approach if the above didn't work
            if not time_remaining:
                # Look for any div containing the time format
                for div in soup.find_all('div'):
                    div_text = div.get_text(strip=True)
                    if re.search(r'\d+H,\s*\d+M,\s*\d+S', div_text):
                        time_remaining = div_text
                        logger.debug(f"Found time remaining with fallback: {time_remaining}")
                        break
            
            # Extract images - updated for bidrl.com's light-gallery structure
            images = []
            
            # Look for the light-gallery structure as in the HTML example
            light_gallery_items = soup.select('light-gallery li[data-src]')
            if light_gallery_items:
                for item in light_gallery_items:
                    src = item.get('data-src')
                    if src:
                        images.append(src)
                        logger.debug(f"Found image from light-gallery: {src}")
            
            # Fallback approaches if the above didn't work
            if not images:
                # Try the img tags inside the light-gallery
                img_elements = soup.select('light-gallery img[data-src]')
                if img_elements:
                    for img in img_elements:
                        src = img.get('data-src')
                        if src:
                            images.append(src)
                            logger.debug(f"Found image from light-gallery img: {src}")
            
            if not images:
                # Try other common image selectors
                for selector in ['.item-image-slider img', 'a.pic img', 'img[src*="auctionimages"]']:
                    img_elements = soup.select(selector)
                    if img_elements:
                        for img in img_elements:
                            src = img.get('src') or img.get('data-src')
                            if src:
                                if src.startswith('/'):
                                    src = f"https://www.bidrl.com{src}"
                                if not src.startswith('/images/imgloading'):  # Skip loading placeholder images
                                    images.append(src)
                        
                        if images:
                            logger.debug(f"Found {len(images)} images with selector: {selector}")
                            break
            
            # Create item dictionary
            item = {
                'lotNumber': lot_number,
                'description': description,
                'currentBid': current_bid,
                'timeRemaining': time_remaining,
                'images': images,
                'itemUrl': url
            }
            
            logger.info(f"Successfully extracted details for item: {lot_number or url}")
            logger.debug(f"Item details extracted")
            
            return item
        except Exception as e:
            logger.error(f"Error extracting item details: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    @staticmethod
    async def find_working_selectors(page, selectors):
        """Find which selectors actually work on this page"""
        if not page:
            logger.error("No page available to find working selectors")
            return {}
        
        working_selectors = {}
        html_content = await page.content()
        soup = BeautifulSoup(html_content, 'html.parser')
        
        for element_type, selector_list in selectors.items():
            for selector in selector_list:
                try:
                    # For complex CSS selectors with :contains(), we need custom handling
                    if ':contains' in selector:
                        # Extract the tag and the text to search for
                        tag = selector.split(':contains')[0].strip()
                        search_text = selector.split(':contains(')[1].split(')')[0].strip('"\'')
                        
                        # Find elements containing the text
                        elements = []
                        for el in soup.find_all(tag):
                            if search_text in el.text:
                                elements.append(el)
                        
                        count = len(elements)
                    else:
                        # Regular CSS selector
                        elements = soup.select(selector)
                        count = len(elements)
                    
                    if count > 0:
                        working_selectors[element_type] = selector
                        logger.info(f"Found working selector for {element_type}: {selector} ({count} elements)")
                        break
                except Exception as e:
                    logger.debug(f"Selector '{selector}' for {element_type} failed: {e}")
            
            if element_type not in working_selectors:
                logger.warning(f"No working selector found for {element_type}")
        
        return working_selectors

    @staticmethod
    async def get_item_urls(page, working_selectors):
        """Get the URLs for all items on the page"""
        if not page or not working_selectors:
            logger.error("No page or working selectors available")
            return []
        
        try:
            items_selector = working_selectors.get('items')
            link_selector = working_selectors.get('link')
            
            if not items_selector or not link_selector:
                logger.error("Missing required selectors for items or links")
                return []
            
            html_content = await page.content()
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find all items
            item_elements = soup.select(items_selector)
            logger.info(f"Found {len(item_elements)} item elements using selector '{items_selector}'")
            
            item_urls = []
            base_url = "https://www.bidrl.com"  # Base URL to prepend to relative URLs
            
            # Process each item to find its URL
            for item in item_elements:
                # Find links within this item
                link_elements = item.select(link_selector)
                
                for link in link_elements:
                    href = link.get('href')
                    if href:
                        # Make sure it's an absolute URL
                        if href.startswith('/'):
                            href = base_url + href
                        
                        item_urls.append(href)
                        logger.debug(f"Found item URL: {href}")
                        break  # Only take the first link per item
            
            # Remove duplicates
            item_urls = list(set(item_urls))
            logger.info(f"Found {len(item_urls)} unique item URLs")
            
            return item_urls
        except Exception as e:
            logger.error(f"Error getting item URLs: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []

"""
Product identification and matching using various APIs and techniques
"""

import re
import time
import random
import json
import aiohttp
import asyncio
import requests
import traceback
from urllib.parse import quote_plus

from config import GOOGLE_API_KEY, PRODUCT_SEARCH_ENABLED
from utils.logger import setup_logger

# Set up logger
logger = setup_logger("ProductIdentifier")

class ProductIdentifier:
    """
    Identifies products using various APIs and techniques to provide
    accurate data for price matching
    """
    
    def __init__(self):
        """Initialize the product identifier"""
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
    
    async def identify_product(self, item):
        """
        Main method to identify a product using multiple methods
        
        Returns enhanced item with product identification info
        """
        try:
            if not item:
                logger.warning("No item provided for product identification")
                return item
                
            logger.info(f"Identifying product for item: {item.get('lotNumber', 'Unknown')}")
            
            # Get the best search query
            search_query = self._get_best_search_query(item)
            if not search_query:
                logger.warning("No search query available for product identification")
                return item
            
            # Create product identification results container
            product_info = {
                'name': '',
                'brand': '',
                'model': '',
                'category': '',
                'specifications': {},
                'identifiers': {},
                'confidence': 0.0
            }
            
            # Method 1: Check if we already have brand/model from object detection
            detection_info = item.get('object_detection', {})
            if detection_info:
                if detection_info.get('detected_brands'):
                    product_info['brand'] = detection_info['detected_brands'][0] 
                if detection_info.get('model_numbers'):
                    product_info['model'] = detection_info['model_numbers'][0]
                
                # Try to determine a category from detected objects
                if detection_info.get('detected_objects'):
                    category = self._determine_category(detection_info['detected_objects'])
                    if category:
                        product_info['category'] = category
            
            # Method 2: Use semantic search to identify product
            if PRODUCT_SEARCH_ENABLED:
                # Use a specialized product search API or service
                product_search_results = await self._search_product_database(search_query)
                
                if product_search_results and product_search_results.get('success'):
                    # Merge product search results with our info
                    for key in product_info:
                        if key in product_search_results and product_search_results[key]:
                            product_info[key] = product_search_results[key]
                    
                    # Update confidence
                    product_info['confidence'] = max(
                        product_info.get('confidence', 0.0),
                        product_search_results.get('confidence', 0.0)
                    )
            
            # Method 3: Extract structured information from raw text data
            extracted_info = self._extract_structured_info(item)
            if extracted_info:
                # Merge extracted info
                for key in product_info:
                    if key in extracted_info and extracted_info[key] and not product_info[key]:
                        product_info[key] = extracted_info[key]
            
            # Calculate confidence based on available information
            if not product_info.get('confidence'):
                # Count how many fields we have data for
                filled_fields = sum(1 for key, value in product_info.items() 
                                   if value and key not in ['confidence', 'specifications', 'identifiers'])
                
                # More fields = higher confidence
                product_info['confidence'] = min(0.85, filled_fields / 5)
            
            # Add product info to item
            item['product_info'] = product_info
            
            # Generate final search query for pricing
            item['final_search_query'] = self._generate_pricing_query(item)
            
            return item
            
        except Exception as e:
            logger.error(f"Error identifying product: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return item
    
    def _get_best_search_query(self, item):
        """
        Get the best search query from available item data
        
        Priority:
        1. Rich search query (from object detection)
        2. Enhanced description (from OCR)
        3. Original description
        """
        if item.get('rich_search_query'):
            return item['rich_search_query']
        elif item.get('enhanced_description'):
            return item['enhanced_description']
        elif item.get('description'):
            return item['description']
        else:
            return None
    
    def _determine_category(self, detected_objects):
        """Determine product category from detected objects"""
        # Define category mappings
        category_mappings = {
            'electronics': ['tv', 'television', 'smartphone', 'phone', 'computer', 'laptop', 
                           'monitor', 'speaker', 'headphone', 'camera', 'tablet'],
            'furniture': ['chair', 'table', 'desk', 'sofa', 'couch', 'bed', 'dresser', 'cabinet'],
            'appliances': ['refrigerator', 'fridge', 'washing machine', 'washer', 'dryer', 
                          'dishwasher', 'microwave', 'oven', 'stove', 'vacuum'],
            'tools': ['drill', 'saw', 'hammer', 'screwdriver', 'wrench', 'tool'],
            'jewelry': ['ring', 'necklace', 'bracelet', 'watch', 'gold', 'silver', 'diamond'],
            'art': ['painting', 'sculpture', 'art', 'artwork', 'statue', 'canvas'],
            'clothing': ['shirt', 'pants', 'jacket', 'coat', 'dress', 'shoe', 'boots'],
            'sports': ['bicycle', 'bike', 'treadmill', 'weights', 'golf', 'ski', 'snowboard']
        }
        
        # Count matches for each category
        category_counts = {category: 0 for category in category_mappings}
        
        for obj in detected_objects:
            obj_lower = obj.lower()
            for category, keywords in category_mappings.items():
                for keyword in keywords:
                    if keyword in obj_lower:
                        category_counts[category] += 1
                        break
        
        # Find category with most matches
        best_category = max(category_counts.items(), key=lambda x: x[1])
        
        # Return category if we have at least one match
        if best_category[1] > 0:
            return best_category[0]
        else:
            return ''
    
    async def _search_product_database(self, query):
        """
        Search a product database for identification
        
        This method can be enhanced to use specialized product APIs
        """
        try:
            # In a real implementation, this would connect to a product database API
            # For demo purposes, we'll just do a simple online search
            
            # Simulate API call delay
            await asyncio.sleep(0.5)
            
            # Format the query to focus on product identification
            search_query = f"{query} product specifications"
            
            # Note: In a full implementation, you would replace this with:
            # - A product database API call
            # - A specialized e-commerce API
            # - A machine learning model trained on product data
            
            # For now, we'll return a simulated result
            # This simulates what a product database might return
            
            # Extract potential brand names from query
            brands = ['sony', 'samsung', 'apple', 'lg', 'bosch', 'dewalt', 'nike', 
                     'adidas', 'microsoft', 'dell', 'hp', 'asus', 'craftsman']
            
            query_lower = query.lower()
            found_brand = None
            
            for brand in brands:
                if brand in query_lower:
                    found_brand = brand.title()
                    break
            
            # Simple product identification (for demonstration)
            result = {
                'success': bool(found_brand),
                'name': '',
                'brand': found_brand if found_brand else '',
                'model': '',
                'category': '',
                'confidence': 0.6 if found_brand else 0.0
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error searching product database: {e}")
            return None
    
    def _extract_structured_info(self, item):
        """
        Extract structured product information from text descriptions
        
        Uses regex patterns to find common product information formats
        """
        try:
            result = {
                'brand': '',
                'model': '',
                'category': '',
                'specifications': {},
                'identifiers': {}
            }
            
            # Check if we already have OCR-detected brands and model numbers
            if item.get('ocr_brands') and len(item['ocr_brands']) > 0:
                # Use the first brand found by OCR
                result['brand'] = item['ocr_brands'][0].title()
                logger.info(f"Using OCR-detected brand: {result['brand']}")
            
            if item.get('ocr_model_numbers') and len(item['ocr_model_numbers']) > 0:
                # Use the first model number found by OCR
                result['model'] = item['ocr_model_numbers'][0].upper()
                logger.info(f"Using OCR-detected model number: {result['model']}")
            
            # If we already have a complete brand + model, we can be more confident
            if result['brand'] and result['model']:
                # Look for it in object detection results to boost confidence
                detection = item.get('object_detection', {})
                if detection.get('detected_brands') and result['brand'].lower() in [b.lower() for b in detection['detected_brands']]:
                    logger.info(f"Brand {result['brand']} confirmed by object detection")
                
                # Skip further processing if we have solid brand + model info
                if len(result['model']) >= 4:  # Only skip if it's a substantial model number
                    logger.info("Found strong brand + model match, skipping further text extraction")
                    return result
            
            # Combine all text sources for deeper analysis
            text_sources = [
                item.get('description', ''),
                item.get('enhanced_description', ''),
                item.get('ocr_text', '')
            ]
            
            # Also add any detected text from object detection
            if item.get('object_detection', {}).get('additional_text'):
                text_sources.append(' '.join(item['object_detection']['additional_text']))
            
            # Join all text
            all_text = ' '.join(text_sources).lower()
            
            # Expanded brand list (if we don't already have a brand)
            if not result['brand']:
                known_brands = [
                    'samsung', 'sony', 'apple', 'lg', 'bosch', 'dewalt', 'milwaukee',
                    'makita', 'craftsman', 'ryobi', 'stanley', 'black and decker', 'black & decker',
                    'kitchenaid', 'whirlpool', 'ge', 'general electric', 'maytag', 'kenmore',
                    'frigidaire', 'philips', 'panasonic', 'toshiba', 'sharp', 'dell', 'hp',
                    'microsoft', 'lenovo', 'asus', 'acer', 'canon', 'nikon', 'sony', 'gopro',
                    'bose', 'sennheiser', 'jbl', 'sonos', 'klipsch', 'polk', 'pioneer',
                    'yamaha', 'denon', 'vizio', 'insignia', 'nintendo', 'playstation', 'xbox',
                    'dyson', 'shark', 'hoover', 'eureka', 'bissell', 'miele', 'roomba', 'irobot',
                    'nutribullet', 'kitchenaid', 'cuisinart', 'ninja', 'breville', 'calphalon',
                    'coleman', 'weber', 'traeger', 'yeti', 'north face', 'patagonia', 'columbia',
                    'nike', 'adidas', 'under armour', 'new balance', 'puma', 'reebok',
                    'levi\'s', 'gap', 'calvin klein', 'ralph lauren', 'gucci', 'coach',
                    'rolex', 'casio', 'citizen', 'seiko', 'timex', 'fossil', 'omega',
                    'lego', 'mattel', 'hasbro', 'fisher price', 'barbie', 'nerf',
                    'ikea', 'ashley', 'la-z-boy', 'ethan allen', 'thomasville', 'bassett'
                ]
                
                for brand in known_brands:
                    # Check for brand with word boundaries to avoid false matches
                    pattern = r'\b' + re.escape(brand) + r'\b'
                    if re.search(pattern, all_text, re.IGNORECASE):
                        result['brand'] = brand.title()
                        logger.info(f"Extracted brand from text: {result['brand']}")
                        break
            
            # Extract model numbers if we don't already have one
            if not result['model']:
                # Extended model patterns for more coverage
                model_patterns = [
                    # Common labeled patterns
                    r'\bmodel[:\s]+([a-z0-9\-]{3,15})\b',    # Model: ABC123
                    r'\bpart[:\s#]+([a-z0-9\-]{3,15})\b',    # Part#: ABC123
                    r'\bsku[:\s]+([a-z0-9\-]{4,15})\b',      # SKU: ABC123
                    
                    # Standard model number patterns
                    r'\b[A-Za-z]{1,4}-\d{2,6}\b',            # ABC-123
                    r'\b[A-Za-z]{2,4}\d{2,4}[A-Za-z]?\b',    # TX550, RTX3080
                    r'\b[A-Z]{2,8}\d{4,8}\b',                # SKGJ5678 (SKU-like)
                    r'\b\d{1,4}[A-Za-z]{1,3}\d{1,4}\b',      # 55UH6150
                    
                    # Brand-specific patterns
                    r'\biphone\s*\d{1,2}(?:\s*pro)?\b',       # iPhone 12 Pro
                    r'\bgalaxy\s*s\d{1,2}(?:\s*plus)?\b',     # Galaxy S21 Plus
                    r'\bmacbook\s*(?:pro|air)?\s*\d{1,2}(?:\s*inch)?\b',  # MacBook Pro 13 inch
                    r'\bps\d\b',                              # PS5
                    r'\bxbox\s*(?:one|series\s*[xs])\b',      # Xbox Series X
                    r'\bv\d{1,2}\b',                          # V10 (like Dyson)
                    
                    # Common prefixed formats with numbers
                    r'\b([a-z]{1,3}\d{3,5}[a-z]{0,2})\b',     # WD5000, LG1500B
                ]
                
                for pattern in model_patterns:
                    matches = re.findall(pattern, all_text, re.IGNORECASE)
                    if matches:
                        # If the pattern has a capture group, use that
                        if isinstance(matches[0], tuple):
                            match = matches[0][0]
                        else:
                            match = matches[0]
                            
                        # Make sure it's a substantial model string
                        if len(match) >= 4:
                            result['model'] = match.upper()
                            logger.info(f"Extracted model from text: {result['model']}")
                            break
            
            # Try to determine product category from keywords
            category_keywords = {
                'television': ['tv', 'television', 'smart tv', 'hdtv', '4k', '8k', 'oled', 'qled', 'lcd'],
                'smartphone': ['phone', 'smartphone', 'iphone', 'galaxy', 'android', 'mobile'],
                'laptop': ['laptop', 'notebook', 'macbook', 'chromebook', 'ultrabook'],
                'tablet': ['tablet', 'ipad', 'galaxy tab', 'surface'],
                'camera': ['camera', 'dslr', 'mirrorless', 'digital camera', 'gopro'],
                'speaker': ['speaker', 'bluetooth speaker', 'sound bar', 'soundbar', 'surround sound'],
                'headphones': ['headphones', 'earbuds', 'earphones', 'headset', 'airpods'],
                'watch': ['watch', 'smartwatch', 'fitness tracker', 'apple watch', 'garmin'],
                'gaming': ['xbox', 'playstation', 'nintendo', 'ps5', 'ps4', 'switch', 'gaming console'],
                'appliance': ['refrigerator', 'fridge', 'washer', 'dryer', 'dishwasher', 'microwave', 'oven', 'stove'],
                'vacuum': ['vacuum', 'robot vacuum', 'stick vacuum', 'dyson'],
                'tool': ['drill', 'saw', 'screwdriver', 'tool set', 'power tool', 'cordless tool'],
                'furniture': ['chair', 'table', 'sofa', 'bed', 'dresser', 'desk', 'bookshelf'],
                'jewelry': ['ring', 'necklace', 'bracelet', 'earrings', 'gold', 'silver', 'diamond'],
                'clothing': ['shirt', 'pants', 'jacket', 'dress', 'shoes', 'boots', 'sneakers'],
                'toy': ['toy', 'lego', 'puzzle', 'action figure', 'doll', 'barbie', 'nerf']
            }
            
            # Find the category with the most keyword matches
            category_matches = {cat: 0 for cat in category_keywords}
            for category, keywords in category_keywords.items():
                for keyword in keywords:
                    if re.search(r'\b' + re.escape(keyword) + r'\b', all_text, re.IGNORECASE):
                        category_matches[category] += 1
            
            # Find the category with most matches
            if category_matches:
                best_category = max(category_matches.items(), key=lambda x: x[1])
                if best_category[1] > 0:
                    result['category'] = best_category[0]
                    logger.info(f"Determined product category: {result['category']}")
            
            # Extract specifications
            # Dimensions
            dimension_patterns = [
                r'(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*(?:in|inch|inches|cm)?',  # 10 x 20 x 30 in
                r'(\d+(?:\.\d+)?)\s*(?:in|inch|inches|cm)\s*(?:diagonal|screen)',  # 55 inch diagonal
            ]
            
            for pattern in dimension_patterns:
                matches = re.findall(pattern, all_text)
                if matches:
                    # Store dimensions in specifications
                    if isinstance(matches[0], tuple) and len(matches[0]) == 3:
                        result['specifications']['dimensions'] = f"{matches[0][0]}x{matches[0][1]}x{matches[0][2]}"
                    else:
                        result['specifications']['dimensions'] = matches[0]
                    break
            
            # Storage capacity
            storage_pattern = r'(\d+)\s*(?:gb|tb|gigabyte|terabyte)'
            storage_matches = re.findall(storage_pattern, all_text, re.IGNORECASE)
            if storage_matches:
                result['specifications']['storage'] = f"{storage_matches[0]} GB"
            
            # Weight
            weight_pattern = r'(\d+(?:\.\d+)?)\s*(?:lb|pound|kg|kilogram|g|gram)'
            weight_matches = re.findall(weight_pattern, all_text, re.IGNORECASE)
            if weight_matches:
                result['specifications']['weight'] = weight_matches[0]
            
            # Power/voltage
            power_pattern = r'(\d+)\s*(?:v|volt|w|watt)'
            power_matches = re.findall(power_pattern, all_text, re.IGNORECASE)
            if power_matches:
                result['specifications']['power'] = f"{power_matches[0]}V/W"
            
            return result
            
        except Exception as e:
            logger.error(f"Error extracting structured info: {e}")
            return None
    
    def _generate_pricing_query(self, item):
        """
        Generate the final search query for pricing based on all available information
        
        This creates a focused query for accurate price matching
        """
        try:
            original_description = item.get('description', '')
            # Clean up the original description
            if original_description and 'Lot #' in original_description:
                original_description = re.sub(r'Lot #.*?:', '', original_description).strip()
            
            # Start with the original item description as the base
            if not original_description:
                # Fallback if no original description
                original_description = item.get('enhanced_description', '')
                if not original_description:
                    original_description = ""
            
            # Limit description length to ensure it's not too verbose
            # But keep most of it since it's the primary information source
            description_words = original_description.split()
            if len(description_words) > 15:
                # Keep first 15 words as they are usually most important
                base_description = ' '.join(description_words[:15])
            else:
                base_description = original_description
                
            logger.info(f"Using original item description as search base: {base_description}")
            
            # Start building enhancement parts to add to the description
            enhancement_parts = []
            
            # Add OCR-detected models first (highest priority) - these are key identifiers
            ocr_models = item.get('ocr_model_numbers', [])
            if ocr_models:
                # Filter to unique models not already in the description
                unique_models = []
                for model in ocr_models:
                    model_upper = model.upper()
                    if model_upper not in base_description.upper() and model_upper not in unique_models:
                        unique_models.append(model_upper)
                
                if unique_models:
                    enhancement_parts.extend(unique_models[:2])  # Add up to 2 model numbers
                    logger.info(f"Added OCR-detected model numbers: {' '.join(unique_models[:2])}")
            
            # Add OCR-detected brands if not already in description
            ocr_brands = item.get('ocr_brands', [])
            if ocr_brands:
                for brand in ocr_brands:
                    if brand.lower() not in base_description.lower():
                        enhancement_parts.append(brand.title())
                        logger.info(f"Added OCR-detected brand: {brand.title()}")
                        break  # Just add one brand
            
            # Add detected brands from object detection if not already covered
            detection = item.get('object_detection', {})
            detected_brands = detection.get('detected_brands', [])
            if detected_brands and not enhancement_parts:  # Only if we don't have enhancements yet
                for brand in detected_brands:
                    if brand.lower() not in base_description.lower() and brand.lower() not in [p.lower() for p in enhancement_parts]:
                        enhancement_parts.append(brand.title())
                        logger.info(f"Added object-detected brand: {brand.title()}")
                        break  # Just add one brand
            
            # Add model numbers from object detection if not already covered
            model_numbers = detection.get('model_numbers', [])
            if model_numbers:
                for model in model_numbers:
                    model_upper = model.upper()
                    if model_upper not in base_description.upper() and model_upper not in [p.upper() for p in enhancement_parts]:
                        enhancement_parts.append(model_upper)
                        logger.info(f"Added object-detected model number: {model_upper}")
                        break  # Just add one model number
            
            # Extract category info from structured data
            product_info = item.get('product_info', {})
            category = product_info.get('category', '')
            
            # Add category if it provides context and isn't already covered
            if category and category.lower() not in base_description.lower() and category.lower() not in [p.lower() for p in enhancement_parts]:
                enhancement_parts.append(category)
                logger.info(f"Added category: {category}")
            
            # Check if the base description contains a brand name
            base_desc_lower = base_description.lower()
            has_brand_in_description = False
            brand_in_description = None
            
            # First, check against our common brands list
            common_brands = [
                'samsung', 'sony', 'apple', 'lg', 'bosch', 'dewalt', 'milwaukee', 
                'makita', 'craftsman', 'ryobi', 'stanley', 'black and decker', 'black & decker',
                'kitchenaid', 'whirlpool', 'ge', 'general electric', 'maytag', 'kenmore',
                'frigidaire', 'philips', 'panasonic', 'toshiba', 'sharp', 'dell', 'hp',
                'microsoft', 'lenovo', 'asus', 'acer', 'canon', 'nikon', 'gopro',
                'bose', 'sennheiser', 'jbl', 'sonos', 'klipsch', 'polk', 'pioneer',
                'yamaha', 'denon', 'vizio', 'insignia', 'nintendo', 'playstation', 'xbox',
                'dyson', 'shark', 'hoover', 'eureka', 'bissell', 'miele', 'roomba', 'irobot',
                'nutribullet', 'cuisinart', 'ninja', 'breville', 'calphalon',
                'coleman', 'weber', 'traeger', 'yeti', 'north face', 'patagonia', 'columbia',
                'nike', 'adidas', 'under armour', 'new balance', 'puma', 'reebok'
            ]
            
            for brand in common_brands:
                if re.search(r'\b' + re.escape(brand) + r'\b', base_desc_lower):
                    has_brand_in_description = True
                    brand_in_description = brand
                    logger.info(f"Found brand name in original description: {brand}")
                    break
            
            # Check if the base description contains what looks like a model number already
            # If so, we'll prioritize the original description even more
            has_model_in_description = False
            model_in_description = None
            for pattern in [
                r'\b[A-Za-z]{1,4}-\d{2,6}\b',            # ABC-123
                r'\b[A-Za-z]{2,4}\d{2,4}[A-Za-z]?\b',    # TX550, RTX3080
                r'\b[A-Z]{2,8}\d{4,8}\b',                # SKGJ5678 (SKU-like)
                r'\bmodel[:\s]+([a-z0-9\-]{3,15})\b',    # Model: ABC123
                r'\bpart[:\s#]+([a-z0-9\-]{3,15})\b',    # Part#: ABC123
                r'\b(?:serial|s/n)[:\s#]+([a-z0-9\-]{3,15})\b',    # Serial: ABC123
                r'\b(?:model|mod|mdl)[:\s#]+([a-z0-9\-]{3,15})\b', # Mod: ABC123
            ]:
                match = re.search(pattern, base_description, re.IGNORECASE)
                if match:
                    has_model_in_description = True
                    model_in_description = match.group(0)
                    logger.info(f"Found model/serial pattern in original description: {model_in_description}")
                    break
                    
            # If we have both brand and model in description, it's likely very accurate already
            if has_brand_in_description and has_model_in_description:
                logger.info("Original description contains both brand and model - very high quality")
                # Check if we can extract just the essential parts for a more focused query
                try:
                    # Try to construct a focused query with just brand + model
                    focused_query = f"{brand_in_description} {model_in_description}"
                    if len(focused_query) > 10:  # Make sure it's substantial
                        logger.info(f"Created focused brand+model query: {focused_query}")
                        base_description = focused_query
                except Exception as e:
                    logger.error(f"Error creating focused query: {e}")
                    # Continue with the full description
            
            # Combine the base description with enhancements
            if has_model_in_description:
                # If description already has model info, only add brand info if available 
                # and keep description as the main focus
                brand_parts = [p for p in enhancement_parts if p.lower() in [b.lower() for b in ocr_brands + detected_brands]]
                if brand_parts:
                    # Add just the brand before the description
                    final_query = ' '.join(brand_parts[:1]) + ' ' + base_description
                    logger.info("Original description has model number - adding only brand enhancement")
                else:
                    # Use description as is since it already has model info
                    final_query = base_description
                    logger.info("Using original description with model number as is")
            elif enhancement_parts:
                # Put enhancements first for better searching, followed by description
                final_query = ' '.join(enhancement_parts) + ' ' + base_description
                logger.info("Using enhanced search query with original description")
            else:
                # If no enhancements, just use the original description
                final_query = base_description
                logger.info("Using original description without enhancements")
            
            # Add product category for context if available and not already there
            product_info = item.get('product_info', {})
            if product_info.get('category') and product_info['category'] not in final_query.lower():
                final_query += f" {product_info['category']}"
            
            # Clean up the query
            final_query = re.sub(r'\s+', ' ', final_query).strip()
            
            # Limit query length
            if len(final_query) > 150:
                final_query = final_query[:150]
            
            logger.info(f"Generated final pricing query (quality: {query_quality}/100): {final_query}")
            return final_query
            
        except Exception as e:
            logger.error(f"Error generating pricing query: {e}")
            # Fall back to original description
            return item.get('description', '')
"""
Image processing and OCR for auction items
"""

import os
import re
import time
import pytesseract
from PIL import Image
from io import BytesIO
import aiohttp
import asyncio
import traceback

from config import TESSERACT_PATH, TESSERACT_CONFIG, IMAGES_DIR
from utils.logger import setup_logger
from utils.file_utils import generate_image_filepath

# Configure pytesseract
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

# Set up logger
logger = setup_logger("ImageProcessor")

class ImageProcessor:
    """Process images with OCR to extract text"""
    
    @staticmethod
    async def process_images(item):
        """Process all images for a single item using OCR"""
        if not item or not item.get('images'):
            logger.warning(f"No images to process for item: {item.get('lotNumber', 'Unknown')}")
            return item
        
        images = item.get('images', [])
        if not images:
            logger.warning(f"No images to process for item: {item.get('lotNumber', 'Unknown')}")
            return item
        
        # Process all images for OCR - may contain important details
        images_for_ocr = images
        
        logger.info(f"Processing {len(images_for_ocr)} images for OCR for item: {item.get('lotNumber', 'Unknown')}")
        
        enhanced_description = item.get('description', '')
        ocr_texts = []
        brands_found = []
        model_numbers_found = []
        
        lot_id = item.get('lotNumber', '').replace(' ', '_').replace('#', '').replace(':', '')
        if not lot_id:
            lot_id = f"unknown_{int(time.time())}"
        
        # Common brand names to look for
        common_brands = [
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
        
        # Pattern to identify model numbers
        model_patterns = [
            r'model[: ]?([a-z0-9\-]{3,15})',
            r'part[.: #]?([a-z0-9\-]{3,15})',
            r'series[: ]?([a-z0-9\-]{2,10})',
            r'type[: ]?([a-z0-9\-]{2,10})',
            r'\b([a-z]{1,4}[0-9]{2,6})\b',  # Like SM550 
            r'\b([a-z]{1,4}-[0-9]{2,6})\b', # Like SM-550
            r'\b([0-9]{1,4}[a-z]{1,4})\b',  # Like 55HD
            r'\b(v[0-9]{1,3})\b',           # Like V10, V8
            r'#\s?([a-z0-9]{5,12})\b',      # Like #AB12345
            r'sku[: ]?([a-z0-9\-]{4,15})',  
            r'upc[: ]?([0-9\-]{10,15})',
            r'ean[: ]?([0-9\-]{10,15})'
        ]
        
        async with aiohttp.ClientSession() as session:
            # First, download and save all images
            for i, img_url in enumerate(images):
                try:
                    logger.debug(f"Downloading image {i+1}/{len(images)}: {img_url}")
                    
                    async with session.get(img_url) as response:
                        if response.status != 200:
                            logger.warning(f"Failed to download image {i+1}: HTTP {response.status}")
                            continue
                        
                        img_data = await response.read()
                    
                    # Save the original image
                    image = Image.open(BytesIO(img_data))
                    image_filepath = generate_image_filepath(lot_id, i+1)
                    image.save(image_filepath)
                    logger.debug(f"Saved image to {image_filepath}")
                    
                    # Process image with OCR using multiple approaches for better results
                    logger.debug(f"Processing image {i+1} with OCR")
                    
                    # Approach 1: Standard processing
                    # Convert to grayscale
                    gray_image = image.convert('L')
                    
                    # Apply threshold to make text more visible
                    threshold = 150
                    binary_image = gray_image.point(lambda p: p > threshold and 255)
                    
                    # Extract text using OCR with improved configuration
                    ocr_text = pytesseract.image_to_string(binary_image, config=TESSERACT_CONFIG)
                    
                    # Approach 2: Try with different preprocessing for cases with low contrast
                    # Adjust contrast to improve text visibility
                    contrast_enhanced = Image.eval(gray_image, lambda px: min(255, max(0, px * 1.5 - 50)))
                    ocr_text2 = pytesseract.image_to_string(contrast_enhanced, config=TESSERACT_CONFIG)
                    
                    # Combine results
                    combined_ocr = ocr_text + " " + ocr_text2
                    
                    if combined_ocr.strip():
                        # Clean up OCR text - remove extra whitespace, line breaks, etc.
                        cleaned_text = ' '.join(combined_ocr.strip().split())
                        
                        # Keep more punctuation and special characters (might be part of model numbers)
                        cleaned_text = re.sub(r'[^a-zA-Z0-9\s\.,\-\$%#\/]', ' ', cleaned_text)
                        
                        # Look for brand names in OCR text
                        lower_text = cleaned_text.lower()
                        for brand in common_brands:
                            if re.search(r'\b' + re.escape(brand) + r'\b', lower_text):
                                brands_found.append(brand)
                                logger.info(f"Found brand in image {i+1}: {brand}")
                        
                        # Look for model numbers in OCR text
                        for pattern in model_patterns:
                            matches = re.findall(pattern, lower_text, re.IGNORECASE)
                            for match in matches:
                                if match and len(match) >= 3:  # Avoid very short matches
                                    model_numbers_found.append(match)
                                    logger.info(f"Found potential model number in image {i+1}: {match}")
                        
                        ocr_texts.append(cleaned_text)
                        logger.info(f"Extracted OCR text from image {i+1}: {cleaned_text[:100]}...")
                    else:
                        logger.debug(f"No text extracted from image {i+1}")
                    
                except Exception as e:
                    logger.error(f"Error processing image {i+1}: {e}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Combine OCR texts into enhanced description
        if ocr_texts:
            # Filter out very short OCR results (likely noise)
            filtered_ocr = [text for text in ocr_texts if len(text) > 10]
            
            combined_ocr = ' '.join(filtered_ocr)
            
            # Store the raw OCR text and identified information
            item['ocr_text'] = combined_ocr
            item['ocr_brands'] = list(set(brands_found))
            item['ocr_model_numbers'] = list(set(model_numbers_found))
            
            # Create an enhanced description by combining original description with OCR
            # Remove any lot numbers from the enhanced description
            clean_description = enhanced_description
            if 'Lot #' in clean_description:
                # Remove the lot number part from the description
                clean_description = re.sub(r'Lot #.*?:', '', clean_description).strip()
            
            # First, add the most important information: brands and model numbers
            important_info = []
            if brands_found:
                important_info.append(' '.join(set(brands_found)))
            if model_numbers_found:
                important_info.append(' '.join(set(model_numbers_found)))
            
            # Then add the original description and OCR text
            if important_info:
                combined_description = f"{' '.join(important_info)} {clean_description} {combined_ocr}"
            else:
                combined_description = f"{clean_description} {combined_ocr}"
            
            # Allow more characters (model numbers might have special chars)
            filtered_description = re.sub(r'[^a-zA-Z0-9\s\.,\-#]', ' ', combined_description)
            # Remove extra spaces
            filtered_description = re.sub(r'\s+', ' ', filtered_description).strip()
            
            item['enhanced_description'] = filtered_description
            logger.info(f"Enhanced description with OCR text: {filtered_description[:100]}...")
        else:
            # Just use the original description if no OCR text was found
            # Remove any lot numbers from the enhanced description
            clean_description = enhanced_description
            if 'Lot #' in clean_description:
                # Remove the lot number part from the description
                clean_description = re.sub(r'Lot #.*?:', '', clean_description).strip()
            
            # Allow more characters
            filtered_description = re.sub(r'[^a-zA-Z0-9\s\.,\-#]', ' ', clean_description)
            # Remove extra spaces
            filtered_description = re.sub(r'\s+', ' ', filtered_description).strip()
                
            item['enhanced_description'] = filtered_description
            item['ocr_brands'] = []
            item['ocr_model_numbers'] = []
            logger.warning("No OCR text extracted from any images")
        
        return item

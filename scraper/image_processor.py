"""
Image processing and OCR for auction items
"""

import os
import re
import time
import pytesseract
import cv2
import numpy as np
from PIL import Image, ImageEnhance
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
        
        # Skip the last image for OCR processing as it typically contains just an ID/auction info
        images_for_ocr = images[:-1] if len(images) > 1 else images
        
        logger.info(f"Processing {len(images_for_ocr)} images for OCR (excluding last image) for item: {item.get('lotNumber', 'Unknown')}")
        
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
                    pil_image = Image.open(BytesIO(img_data))
                    image_filepath = generate_image_filepath(lot_id, i+1)
                    pil_image.save(image_filepath)
                    logger.debug(f"Saved image to {image_filepath}")
                    
                    # Skip OCR for the last image
                    if i == len(images) - 1 and len(images) > 1:
                        logger.debug(f"Skipping OCR for last image (image {i+1})")
                        continue
                    
                    # Process image with OCR using OpenCV for better preprocessing
                    logger.debug(f"Processing image {i+1} with OCR + OpenCV")
                    
                    # Convert PIL image to OpenCV format
                    cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                    
                    # Resize image if it's too large (for better OCR performance)
                    max_dim = 1500
                    h, w = cv_image.shape[:2]
                    if max(h, w) > max_dim:
                        # Calculate new dimensions while preserving aspect ratio
                        if h > w:
                            new_h, new_w = max_dim, int(w * max_dim / h)
                        else:
                            new_h, new_w = int(h * max_dim / w), max_dim
                        cv_image = cv2.resize(cv_image, (new_w, new_h), interpolation=cv2.INTER_AREA)
                        logger.debug(f"Resized image from {w}x{h} to {new_w}x{new_h}")
                    
                    # Crop off bottom 5% of the image to remove auction info
                    h, w = cv_image.shape[:2]
                    crop_height = int(h * 0.95)  # Remove bottom 5%
                    cv_image = cv_image[0:crop_height, 0:w]
                    
                    # Save the cropped image (for debugging)
                    cropped_filepath = generate_image_filepath(lot_id, i+1, "_cropped")
                    cv2.imwrite(cropped_filepath, cv_image)
                    
                    # Use multiple preprocessing techniques for better OCR
                    ocr_results = []
                    
                    # Approach 1: Basic grayscale
                    gray_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
                    
                    # Save the grayscale image (for debugging)
                    gray_filepath = generate_image_filepath(lot_id, i+1, "_gray")
                    cv2.imwrite(gray_filepath, gray_image)
                    
                    # Run OCR on grayscale image
                    ocr_text1 = pytesseract.image_to_string(gray_image, config=TESSERACT_CONFIG)
                    if ocr_text1.strip():
                        ocr_results.append(ocr_text1)
                    
                    # Approach 2: Thresholding for better text contrast
                    # Try multiple thresholding methods and combine results
                    # Binary threshold
                    _, binary_image = cv2.threshold(gray_image, 150, 255, cv2.THRESH_BINARY)
                    ocr_text2 = pytesseract.image_to_string(binary_image, config=TESSERACT_CONFIG)
                    if ocr_text2.strip():
                        ocr_results.append(ocr_text2)
                    
                    # Adaptive threshold (good for varying lighting conditions)
                    adaptive_image = cv2.adaptiveThreshold(
                        gray_image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
                    )
                    ocr_text3 = pytesseract.image_to_string(adaptive_image, config=TESSERACT_CONFIG)
                    if ocr_text3.strip():
                        ocr_results.append(ocr_text3)
                    
                    # Approach 3: Edge enhancement
                    # Detect edges and dilate them to enhance text
                    edges = cv2.Canny(gray_image, 100, 200)
                    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
                    dilated_edges = cv2.dilate(edges, kernel, iterations=1)
                    # Invert for OCR
                    dilated_edges = cv2.bitwise_not(dilated_edges)
                    ocr_text4 = pytesseract.image_to_string(dilated_edges, config=TESSERACT_CONFIG)
                    if ocr_text4.strip():
                        ocr_results.append(ocr_text4)
                    
                    # Combine all OCR results
                    combined_ocr = " ".join(ocr_results)
                    
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
                                if isinstance(match, tuple) and match:
                                    match = match[0]
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
            
            # Check if the original description already has model numbers or SKUs
            # Try to detect model numbers in the original description
            original_model_numbers = []
            for pattern in model_patterns:
                matches = re.findall(pattern, clean_description.lower(), re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple) and match:
                        match = match[0]
                    if match and len(match) >= 3:  # Avoid very short matches
                        original_model_numbers.append(match)
                        logger.info(f"Found model number in original description: {match}")
            
            # If the original description already has model numbers, prioritize those
            # and enhance with brands if needed
            if original_model_numbers:
                logger.info("Original description already contains model numbers - prioritizing it")
                # Add brands if found and not in original description
                brand_enhancement = ""
                if brands_found:
                    unique_brands = []
                    for brand in brands_found:
                        if brand.lower() not in clean_description.lower():
                            unique_brands.append(brand)
                    if unique_brands:
                        brand_enhancement = ' '.join(set(unique_brands)) + ' '
                
                # Put original description first, then add brands and OCR text
                combined_description = f"{clean_description} {brand_enhancement}{combined_ocr}"
            else:
                # Original description doesn't have model numbers, so add them first
                important_info = []
                if brands_found:
                    important_info.append(' '.join(set(brands_found)))
                if model_numbers_found:
                    important_info.append(' '.join(set(model_numbers_found)))
                
                # Then add the original description and OCR text
                if important_info:
                    # Put model numbers first, then original description, then OCR text
                    combined_description = f"{' '.join(important_info)} {clean_description} {combined_ocr}"
                else:
                    # No model numbers found at all, keep original description first
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

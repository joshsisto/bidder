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
            
        # Skip the last image for OCR processing as it typically contains just an ID
        images_for_ocr = images[:-1] if len(images) > 1 else images
        
        logger.info(f"Processing {len(images_for_ocr)} images for OCR (excluding last image) for item: {item.get('lotNumber', 'Unknown')}")
        
        enhanced_description = item.get('description', '')
        ocr_texts = []
        lot_id = item.get('lotNumber', '').replace(' ', '_').replace('#', '').replace(':', '')
        if not lot_id:
            lot_id = f"unknown_{int(time.time())}"
        
        async with aiohttp.ClientSession() as session:
            # First, download and save all images (including the last one)
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
                    
                    # Skip OCR for the last image
                    if i == len(images) - 1 and len(images) > 1:
                        logger.debug(f"Skipping OCR for last image (image {i+1})")
                        continue
                    
                    # Process image with OCR
                    logger.debug(f"Processing image {i+1} with OCR")
                    
                    # Apply preprocessing to improve OCR results
                    # Convert to grayscale
                    image = image.convert('L')
                    
                    # Crop the bottom 3% of the image to remove standard text
                    width, height = image.size
                    crop_height = int(height * 0.97)  # Remove bottom 3%
                    cropped_image = image.crop((0, 0, width, crop_height))
                    
                    # Save the cropped image
                    cropped_filepath = generate_image_filepath(lot_id, i+1, "_cropped")
                    cropped_image.save(cropped_filepath)
                    
                    # Apply threshold to make text more visible
                    # Convert to binary image for better OCR
                    threshold = 150
                    binary_image = cropped_image.point(lambda p: p > threshold and 255)
                    
                    # Extract text using OCR with improved configuration
                    ocr_text = pytesseract.image_to_string(binary_image, config=TESSERACT_CONFIG)
                    
                    if ocr_text.strip():
                        # Clean up OCR text - remove extra whitespace, line breaks, etc.
                        cleaned_text = ' '.join(ocr_text.strip().split())
                        
                        # Filter to only keep alphanumeric characters (a-z, A-Z, 0-9) and basic punctuation
                        cleaned_text = re.sub(r'[^a-zA-Z0-9\s\.,\-\$%]', '', cleaned_text)
                        
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
            
            # Store the raw OCR text
            item['ocr_text'] = combined_ocr
            
            # Create an enhanced description by combining original description with OCR
            # Remove any lot numbers from the enhanced description
            clean_description = enhanced_description
            if 'Lot #' in clean_description:
                # Remove the lot number part from the description
                clean_description = re.sub(r'Lot #.*?:', '', clean_description).strip()
            
            # Combine clean description with OCR text
            combined_description = f"{clean_description} {combined_ocr}"
            
            # Filter to only keep alphanumeric characters (a-z, A-Z, 0-9) and spaces
            # This will make the enhanced description more searchable
            filtered_description = re.sub(r'[^a-zA-Z0-9\s]', ' ', combined_description)
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
            
            # Filter to only keep alphanumeric characters (a-z, A-Z, 0-9) and spaces
            filtered_description = re.sub(r'[^a-zA-Z0-9\s]', ' ', clean_description)
            # Remove extra spaces
            filtered_description = re.sub(r'\s+', ' ', filtered_description).strip()
                
            item['enhanced_description'] = filtered_description
            logger.warning("No OCR text extracted from any images")
        
        return item

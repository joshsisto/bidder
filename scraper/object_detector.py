"""
Object detection and product information extraction using computer vision
"""

import os
import re
import cv2
import time
import numpy as np
import asyncio
import traceback
import base64
from io import BytesIO
from PIL import Image
import aiohttp
import requests
import json

from config import IMAGES_DIR, GOOGLE_API_KEY, CLOUD_VISION_ENABLED
from utils.logger import setup_logger
from utils.file_utils import generate_image_filepath

# Set up logger
logger = setup_logger("ObjectDetector")

class ObjectDetector:
    """
    Detects objects, brands, and product information from images using
    multiple computer vision approaches
    """
    
    @staticmethod
    async def detect_objects_in_image(image_path, image_url=None):
        """
        Detect objects, text, and logos in an image using multiple detection methods
        
        Returns a dict with detected information
        """
        try:
            results = {
                'objects': [],     # List of detected objects
                'brands': [],      # List of detected brand names
                'model_info': [],  # Model numbers, SKUs, etc.
                'colors': [],      # Detected colors
                'text': [],        # Additional text found
                'confidence': 0.0  # Overall confidence score
            }
            
            # Load the image
            image = Image.open(image_path)
            cv_image = cv2.imread(image_path)
            
            # Method 1: Use Google Cloud Vision API if enabled
            if CLOUD_VISION_ENABLED and GOOGLE_API_KEY:
                try:
                    vision_results = await ObjectDetector._analyze_with_google_vision(image_path, image_url)
                    if vision_results:
                        # Merge vision API results with our results
                        for key in results:
                            if key in vision_results and vision_results[key]:
                                results[key].extend(vision_results[key])
                except Exception as e:
                    logger.error(f"Error with Google Vision API: {e}")
            
            # Method 2: Local object detection using OpenCV and pre-trained models
            opencv_results = ObjectDetector._detect_with_opencv(cv_image)
            if opencv_results:
                # Merge OpenCV results
                for key in results:
                    if key in opencv_results and opencv_results[key]:
                        results[key].extend(opencv_results[key])
            
            # Remove duplicates from all result lists
            for key in results:
                if isinstance(results[key], list):
                    results[key] = list(set(results[key]))
            
            # Calculate confidence based on number of detections
            total_detections = sum(len(results[key]) for key in ['objects', 'brands', 'model_info'])
            if total_detections > 0:
                results['confidence'] = min(0.9, (total_detections / 10) + 0.1)  # Scale confidence
            
            return results
            
        except Exception as e:
            logger.error(f"Error detecting objects in image: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    @staticmethod
    async def _analyze_with_google_vision(image_path, image_url=None):
        """
        Analyze image using Google Cloud Vision API 
        
        Can use either local image or remote URL
        """
        if not GOOGLE_API_KEY:
            logger.warning("Google API key not provided for Cloud Vision API")
            return None
            
        try:
            logger.info("Analyzing image with Google Cloud Vision API")
            
            # Prepare the request
            api_url = f"https://vision.googleapis.com/v1/images:annotate?key={GOOGLE_API_KEY}"
            
            # If we have a URL, use it directly (more efficient)
            if image_url:
                image_content = {"source": {"imageUri": image_url}}
            else:
                # Otherwise encode the image
                with open(image_path, "rb") as image_file:
                    encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
                image_content = {"content": encoded_image}
            
            # Build request with all feature types
            post_data = {
                "requests": [
                    {
                        "image": image_content,
                        "features": [
                            {"type": "OBJECT_LOCALIZATION", "maxResults": 10},
                            {"type": "LOGO_DETECTION", "maxResults": 5},
                            {"type": "TEXT_DETECTION", "maxResults": 20},
                            {"type": "LABEL_DETECTION", "maxResults": 10},
                            {"type": "IMAGE_PROPERTIES", "maxResults": 5}
                        ]
                    }
                ]
            }
            
            # Make the API request
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=post_data, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"Google Vision API request failed: {response.status}")
                        logger.error(await response.text())
                        return None
                    
                    response_data = await response.json()
            
            # Extract relevant information from the response
            results = {
                'objects': [],
                'brands': [],
                'model_info': [],
                'colors': [],
                'text': [],
                'confidence': 0.0
            }
            
            # Extract detected objects
            if 'responses' in response_data and response_data['responses']:
                response = response_data['responses'][0]
                
                # Get objects
                if 'localizedObjectAnnotations' in response:
                    for obj in response['localizedObjectAnnotations']:
                        results['objects'].append(obj['name'].lower())
                        
                # Get logos (brands)
                if 'logoAnnotations' in response:
                    for logo in response['logoAnnotations']:
                        results['brands'].append(logo['description'].lower())
                
                # Extract text
                if 'textAnnotations' in response:
                    all_text = []
                    
                    # Skip the first item, which is the entire text block
                    for text_item in response['textAnnotations'][1:] if response['textAnnotations'] else []:
                        text = text_item['description'].lower()
                        
                        # Look for model numbers and SKUs
                        if ObjectDetector._is_model_number(text):
                            results['model_info'].append(text)
                        else:
                            # Add to general text
                            all_text.append(text)
                    
                    # Combine all text
                    results['text'] = all_text
                
                # Get colors
                if 'imagePropertiesAnnotation' in response:
                    if 'dominantColors' in response['imagePropertiesAnnotation']:
                        for color in response['imagePropertiesAnnotation']['dominantColors']['colors'][:3]:
                            # Get RGB values
                            r = int(color['color']['red'])
                            g = int(color['color']['green'])
                            b = int(color['color']['blue'])
                            
                            # Convert to color name (simple approximation)
                            color_name = ObjectDetector._get_color_name(r, g, b)
                            if color_name:
                                results['colors'].append(color_name)
            
            return results
            
        except Exception as e:
            logger.error(f"Error with Google Vision API: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    @staticmethod
    def _detect_with_opencv(cv_image):
        """
        Detect objects using OpenCV and pre-trained models
        
        This is a simpler fallback when Vision API is not available
        """
        try:
            results = {
                'objects': [],
                'colors': [],
                'confidence': 0.0,
                'text': []
            }
            
            # Resize image if it's too large
            max_dim = 1500
            h, w = cv_image.shape[:2]
            if max(h, w) > max_dim:
                # Calculate new dimensions while preserving aspect ratio
                if h > w:
                    new_h, new_w = max_dim, int(w * max_dim / h)
                else:
                    new_h, new_w = int(h * max_dim / w), max_dim
                cv_image = cv2.resize(cv_image, (new_w, new_h), interpolation=cv2.INTER_AREA)
            
            # Crop off bottom 5% of the image to remove auction info
            h, w = cv_image.shape[:2]
            crop_height = int(h * 0.95)  # Remove bottom 5%
            cv_image = cv_image[0:crop_height, 0:w]
            
            # Get dominant colors using OpenCV
            # Convert to HSV for better color detection
            img_hsv = cv2.cvtColor(cv_image, cv2.COLOR_BGR2HSV)
            
            # Create color histogram - using K-means for more accurate color detection
            pixels = cv_image.reshape((-1, 3))
            pixels = np.float32(pixels)
            
            # Define criteria for K-means
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2)
            k = 5  # Number of dominant colors to extract
            
            _, labels, centers = cv2.kmeans(pixels, k, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
            
            # Get the most dominant colors - centers represent RGB colors
            # Count pixels in each cluster
            count = np.bincount(labels.flatten())
            # Sort clusters by size (most dominant first)
            color_indices = np.argsort(-count)
            
            # Get top 3 colors
            for i in range(min(3, len(color_indices))):
                center = centers[color_indices[i]]
                rgb_color = center[::-1]  # Convert BGR to RGB
                
                # Get color name
                color_name = ObjectDetector._get_color_name(rgb_color[0], rgb_color[1], rgb_color[2])
                if color_name:
                    results['colors'].append(color_name)
            
            # Get image dimensions for shape analysis
            height, width = cv_image.shape[:2]
            aspect_ratio = width / float(height) if height > 0 else 0
            
            # Categorize object shape by aspect ratio
            if aspect_ratio > 1.5:
                results['objects'].append('wide_item')
            elif aspect_ratio < 0.67:
                results['objects'].append('tall_item')
            else:
                results['objects'].append('square_item')
            
            # Detect edges and contours
            gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blurred, 50, 150)
            
            # Morphological operations to close gaps
            kernel = np.ones((3, 3), np.uint8)
            closed_edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
            
            # Find contours
            contours, hierarchy = cv2.findContours(closed_edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Analyze contours by shape
            rectangles = 0
            circles = 0
            triangles = 0
            irregular = 0
            
            for contour in contours:
                # Filter out very small contours
                area = cv2.contourArea(contour)
                if area < (width * height * 0.01):  # Less than 1% of image
                    continue
                
                # Approximate contour to get shape
                epsilon = 0.04 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                
                # Classify by number of vertices
                if len(approx) == 4:
                    # Check if it's rectangular
                    x, y, w, h = cv2.boundingRect(contour)
                    aspect_ratio = w / float(h)
                    
                    # If it's a rectangle that is not too elongated
                    if 0.5 < aspect_ratio < 2.0:
                        rectangles += 1
                    
                elif len(approx) == 3:
                    triangles += 1
                    
                elif len(approx) >= 8:
                    # Potential circle - check roundness
                    (x, y), radius = cv2.minEnclosingCircle(contour)
                    circle_area = np.pi * radius ** 2
                    if abs(area / circle_area - 1) < 0.2:  # Within 20% of perfect circle
                        circles += 1
                else:
                    irregular += 1
            
            # Add shape-based objects
            if rectangles > 2:
                results['objects'].append('electronic_device')
            if circles > 3:
                results['objects'].append('mechanical_object')
            if triangles > 2:
                results['objects'].append('structured_object')
            
            # Texture analysis - check if item is shiny/metallic
            gray_variance = np.var(gray)
            if gray_variance > 3000:  # High variance often indicates shiny objects
                results['objects'].append('reflective_object')
            
            # Check for text-rich images
            # Use simple edge density in regions as a proxy
            edge_density = np.sum(edges) / (edges.shape[0] * edges.shape[1])
            if edge_density > 0.1:  # Threshold determined empirically
                results['objects'].append('text_heavy_object')
            
            # Additional image features can be added here
            
            return results
            
        except Exception as e:
            logger.error(f"Error with OpenCV detection: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    @staticmethod
    def _get_color_name(r, g, b):
        """Convert RGB values to color name"""
        # Simple color detection by closest match
        colors = {
            'red': (255, 0, 0),
            'green': (0, 255, 0),
            'blue': (0, 0, 255),
            'black': (0, 0, 0),
            'white': (255, 255, 255),
            'yellow': (255, 255, 0),
            'purple': (128, 0, 128),
            'orange': (255, 165, 0),
            'pink': (255, 192, 203),
            'gray': (128, 128, 128),
            'brown': (165, 42, 42),
            'silver': (192, 192, 192),
            'gold': (255, 215, 0)
        }
        
        min_distance = float('inf')
        closest_color = None
        
        for color_name, color_rgb in colors.items():
            # Calculate Euclidean distance
            distance = sum((c1 - c2) ** 2 for c1, c2 in zip((r, g, b), color_rgb)) ** 0.5
            if distance < min_distance:
                min_distance = distance
                closest_color = color_name
        
        return closest_color
    
    @staticmethod
    def _is_model_number(text):
        """
        Check if the text looks like a model number or SKU
        
        Model numbers often follow patterns like:
        - Alphanumeric with hyphens (e.g., ABC-123, SM-G970F)
        - Mix of letters and numbers (e.g., TX550, RTX3080)
        - SKUs are often all caps with numbers (e.g., SKGJ5678)
        """
        # Remove spaces
        text = text.strip().replace(' ', '')
        
        if not text or len(text) < 3:
            return False
            
        # Common model number patterns
        patterns = [
            # General patterns
            r'^[A-Za-z]{1,4}-?\d{2,6}$',                # ABC-123, SM-G970
            r'^[A-Za-z]{2,4}\d{2,4}[A-Za-z]?$',         # TX550, RTX3080, TX550i
            r'^[A-Z]{2,8}\d{4,8}$',                     # SKGJ5678 (SKU-like)
            r'^\d{1,4}[A-Za-z]{1,3}\d{1,4}$',           # 55UH6150
            r'^[A-Za-z]\d{1,2}-\d{1,4}[A-Za-z]?$',      # A8-3500M
            r'^[A-Za-z]{2,4}-[A-Za-z]\d{1,4}$',         # GTX-X570
            
            # Common specific patterns for various brands
            r'^(UN|QN|LN)\d{2}[A-Z]\d{4}[A-Z]$',        # Samsung TV: UN55NU7100F
            r'^[A-Z]{2}-[A-Z]\d{4}[A-Z]$',              # Sony TV: XBR-X900H
            r'^(MH|ML|MS|MP)\d{2,4}[A-Z]?$',            # LG Appliances: MH12345A
            r'^[A-Z]{3}\d{4}[A-Z]{1,2}$',               # Whirlpool: WRF535SMBM
            r'^[A-Z]{2}\d{2,4}[A-Z]{0,2}$',             # DeWalt tools: DC725
            r'^(SM-[A-Z]\d{3,4}|Galaxy\s?S\d{1,2})$',   # Samsung phones: SM-G975, Galaxy S10
            r'^iPhone\s?\d{1,2}$',                      # iPhones: iPhone 12
            r'^[A-Z]{1,2}\d{1,3}-(BT|XT|LT)$',          # Bluetooth devices: M50-BT
            r'^[A-Z]{2,4}-\d{2,4}[A-Z]?-[A-Z]{1,2}$',   # PC Parts: ROG-570X-F
            r'^([A-Z]{2,3}-\d{3,5}|\d{2,3}-\d{3})$',    # Cameras: EOS-250D, 70-200
            
            # UPC and similar patterns
            r'^\d{12,13}$',                             # UPC/EAN: 123456789012
            r'^\d{3}-\d{3}-\d{4}$',                     # Formatted number: 123-456-7890 
        ]
        
        # Check against patterns
        for pattern in patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return True
                
        # Check if alphanumeric with a good mix of letters and numbers
        if re.match(r'^[A-Za-z0-9]+$', text):
            # Count letters and numbers
            letters = sum(c.isalpha() for c in text)
            numbers = sum(c.isdigit() for c in text)
            # Good mix has at least 2 of each and neither dominating too much
            if letters >= 2 and numbers >= 2 and (0.20 <= letters/len(text) <= 0.80):
                return True
        
        return False
    
    @staticmethod
    async def enhance_item_with_object_detection(item):
        """
        Process all images for a single item using object detection
        and enhance the item data with the detected information
        """
        if not item or not item.get('images'):
            logger.warning(f"No images to process for item: {item.get('lotNumber', 'Unknown')}")
            return item
        
        images = item.get('images', [])
        if not images:
            logger.warning(f"No images to process for item: {item.get('lotNumber', 'Unknown')}")
            return item
        
        logger.info(f"Enhancing item with object detection for: {item.get('lotNumber', 'Unknown')}")
        
        # Create detection results container
        detection_results = {
            'detected_objects': [],
            'detected_brands': [],
            'model_numbers': [],
            'colors': [],
            'additional_text': []
        }
        
        lot_id = item.get('lotNumber', '').replace(' ', '_').replace('#', '').replace(':', '')
        if not lot_id:
            lot_id = f"unknown_{int(time.time())}"
        
        # Process each image, excluding the last one
        images_for_detection = images[:-1] if len(images) > 1 else images
        
        for i, img_url in enumerate(images_for_detection):
            try:
                # Generate the local image path
                image_filepath = generate_image_filepath(lot_id, i+1)
                
                # Only analyze if file exists
                if os.path.exists(image_filepath):
                    logger.info(f"Analyzing image {i+1}/{len(images_for_detection)} for object detection")
                    
                    # Detect objects in the image
                    results = await ObjectDetector.detect_objects_in_image(image_filepath, img_url)
                    
                    if results:
                        # Merge results
                        detection_results['detected_objects'].extend(results.get('objects', []))
                        detection_results['detected_brands'].extend(results.get('brands', []))
                        detection_results['model_numbers'].extend(results.get('model_info', []))
                        detection_results['colors'].extend(results.get('colors', []))
                        detection_results['additional_text'].extend(results.get('text', []))
                        
                        logger.info(f"Detection results for image {i+1}: " + 
                                    f"{len(results.get('objects', []))} objects, " +
                                    f"{len(results.get('brands', []))} brands")
                    else:
                        logger.warning(f"No detection results for image {i+1}")
                else:
                    logger.warning(f"Image file not found at {image_filepath}")
                    
                # Add delay to avoid overloading APIs
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error processing image {i+1} for object detection: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Remove duplicates
        for key in detection_results:
            detection_results[key] = list(set(detection_results[key]))
        
        # Add detection results to item
        item['object_detection'] = detection_results
        
        # Generate enhanced search query
        brand_text = ' '.join(detection_results['detected_brands']).strip()
        model_text = ' '.join(detection_results['model_numbers']).strip()
        object_text = ' '.join(detection_results['detected_objects'][:3]).strip()  # Top 3 objects
        color_text = ' '.join(detection_results['colors'][:2]).strip()  # Top 2 colors
        
        # Create a rich search query from detected information
        rich_query_parts = []
        
        # Brand and model are most important
        if brand_text:
            rich_query_parts.append(brand_text)
        if model_text:
            rich_query_parts.append(model_text)
            
        # Object and color add context
        if object_text:
            rich_query_parts.append(object_text)
        if color_text:
            rich_query_parts.append(color_text)
        
        # Combine with original description
        original_desc = item.get('enhanced_description', '') or item.get('description', '')
        
        # Clean original description
        if 'Lot #' in original_desc:
            original_desc = re.sub(r'Lot #.*?:', '', original_desc).strip()
        
        # If we have detection results, use them as primary source
        if rich_query_parts:
            # Combine detection results with shortened original description
            max_desc_length = 30 if len(rich_query_parts) > 2 else 50
            short_desc = ' '.join(original_desc.split()[:max_desc_length])
            
            rich_query = ' '.join(rich_query_parts) + ' ' + short_desc
            
            # Remove extra whitespace and truncate if too long
            rich_query = ' '.join(rich_query.split())
            if len(rich_query) > 200:
                rich_query = rich_query[:200]
                
            item['rich_search_query'] = rich_query
            logger.info(f"Generated rich search query: {rich_query}")
        else:
            # Fallback to original description
            item['rich_search_query'] = original_desc
            logger.warning("No detection results to enhance search query")
        
        return item
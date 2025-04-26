"""
LLM-based search query generator for auction items
Uses OpenRouter API to generate optimized search queries
"""

import json
import re
import aiohttp
import asyncio
import traceback
from typing import Dict, Any, Optional

from config import OPENROUTER_API_KEY, OPENROUTER_MODEL, OPENROUTER_ENABLED
from utils.logger import setup_logger

# Set up logger
logger = setup_logger("LLMQueryGenerator")

class LLMQueryGenerator:
    """
    Uses LLM to generate optimized search queries for auction items
    based on descriptions and OCR text
    """
    
    @staticmethod
    async def generate_search_query(item: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate optimized search queries using LLM
        
        Args:
            item: Auction item data with description and OCR text
            
        Returns:
            Dictionary with generated search queries and product info
        """
        try:
            if not OPENROUTER_ENABLED or not OPENROUTER_API_KEY:
                logger.warning("OpenRouter API not enabled or missing API key")
                return {"error": "OpenRouter API not enabled"}
            
            # Get input text to analyze
            input_text = LLMQueryGenerator._prepare_input_text(item)
            if not input_text.strip():
                logger.warning("No input text available for LLM analysis")
                return {"error": "No input text available"}
                
            logger.info("Preparing to send request to LLM for query generation")
            
            # The prompt template for the LLM
            prompt_template = """You are an AI assistant specialized in analyzing noisy text from auction item descriptions to accurately identify products.

Context: You will be given raw text extracted via Optical Character Recognition (OCR) from images or descriptions on auction websites. This text is often imperfect and may contain:
- OCR errors (misspelled words, incorrect characters)
- Nonsense words or character strings
- Irrelevant information (lot numbers, auction terms like "AS IS", "Untested", location details, seller notes)
- Poor formatting

Primary Goal: Your main objective is to meticulously analyze the input text, filter out the noise, identify the core product being sold, and extract its key identifying information, particularly the brand and model/specific identifier.

Instructions:
1. Analyze Input: Carefully read the entire [Input OCR Text] provided below.
2. Filter Noise: Identify and disregard irrelevant text. This includes:
   - Obvious OCR errors and gibberish.
   - Common auction terms and conditions (e.g., "Sold As Is", "No Reserve", "Buyer's Premium", "Lot #").
   - Generic descriptions not specific to the product (e.g., "Good condition", "See photos").
   - Focus only on the words and numbers that describe the actual item.
3. Identify Product: Determine the most likely type of product being described (e.g., Laptop, Coffee Maker, Wristwatch, Collectible Figurine, Power Tool).
4. Extract Key Details: Search the filtered text for specific identifiers:
   - Brand Name: Look for known manufacturer names (e.g., Apple, Keurig, Seiko, Funko, Milwaukee). If multiple potential brands appear, choose the most likely one associated with the product type. If none is clear, you MUST state "Unknown" (not "unclear" or empty string).
   - Model Name/Number: Look for specific model names, model numbers, or series identifiers (e.g., MacBook Air M1, K-Supreme, SKX007, Pop! #54, M18 Fuel). If none is clear, you MUST state "Unknown" (not "unclear" or empty string).
   - Other Critical Attributes: Note any other highly relevant details necessary for identification (e.g., Size, Color, Year, Capacity, Part Number) but keep it concise. Omit if not clearly present or essential.
5. Generate Search Queries: Based only on the reliably identified Brand, Model, and Product Type, formulate concise and effective search query strings suitable for:
   - A general web search (like Google).
   - An e-commerce search (like Amazon). Prioritize Brand + Model + Product Type.

IMPORTANT: When you cannot confidently identify the product, brand, or model (confidence below 70%), you MUST mark it as "Unknown". DO NOT guess at specifics when uncertain. If the input is too vague, marking fields as "Unknown" is the correct response.

Input OCR Text:
{input_text}

Output Format:
Please provide your analysis STRICTLY in the following JSON format:
{{
  "identified_product_type": "Specific type of product identified or Unknown",
  "brand": "Identified Brand Name or Unknown",
  "model_name_number": "Identified Model Name/Number or Unknown",
  "other_relevant_attributes": "Concise list of other key details, or N/A",
  "google_search_query": "Optimized search string for Google Search, or empty string if too uncertain",
  "amazon_search_query": "Optimized search string for Amazon Search, or empty string if too uncertain"
}}"""

            # Use OpenRouter API to generate queries
            json_response = await LLMQueryGenerator._call_openrouter_api(
                prompt_template.format(input_text=input_text)
            )
            
            if not json_response or "error" in json_response:
                logger.error(f"Error in LLM API response: {json_response.get('error', 'Unknown error')}")
                return {"error": str(json_response.get('error', 'Unknown error'))}
                
            # Extract and process the LLM response
            return LLMQueryGenerator._process_llm_response(json_response, item)
            
        except Exception as e:
            logger.error(f"Error generating search query with LLM: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {"error": str(e)}
    
    @staticmethod
    def _prepare_input_text(item: Dict[str, Any]) -> str:
        """
        Prepare input text for the LLM by combining description and OCR text
        
        Args:
            item: Auction item data
            
        Returns:
            Combined text to send to LLM
        """
        text_parts = []
        
        # Start with the original description
        description = item.get('description', '')
        if description:
            text_parts.append(f"ITEM DESCRIPTION: {description}")
        
        # Add enhanced description if available and different
        enhanced_description = item.get('enhanced_description', '')
        if enhanced_description and enhanced_description != description:
            text_parts.append(f"ENHANCED DESCRIPTION: {enhanced_description}")
        
        # Add OCR text if available
        ocr_text = item.get('ocr_text', '')
        if ocr_text:
            text_parts.append(f"OCR TEXT: {ocr_text}")
        
        # Add any detected brands and model numbers
        if item.get('ocr_brands'):
            text_parts.append(f"DETECTED BRANDS: {', '.join(item['ocr_brands'])}")
        
        if item.get('ocr_model_numbers'):
            text_parts.append(f"DETECTED MODEL NUMBERS: {', '.join(item['ocr_model_numbers'])}")
        
        # Add object detection info
        if item.get('object_detection'):
            detection = item['object_detection']
            
            if detection.get('detected_objects'):
                objects = [obj for obj in detection['detected_objects'] 
                          if obj not in ('tall_item', 'wide_item', 'square_item', 'rectangular_object')]
                if objects:
                    text_parts.append(f"DETECTED OBJECTS: {', '.join(objects)}")
            
            if detection.get('detected_brands'):
                text_parts.append(f"CV DETECTED BRANDS: {', '.join(detection['detected_brands'])}")
            
            if detection.get('model_numbers'):
                text_parts.append(f"CV DETECTED MODEL NUMBERS: {', '.join(detection['model_numbers'])}")
            
            if detection.get('colors'):
                text_parts.append(f"DETECTED COLORS: {', '.join(detection['colors'])}")
        
        # Join all parts with double newlines for readability
        return "\n\n".join(text_parts)
    
    @staticmethod
    async def _call_openrouter_api(prompt: str) -> Dict[str, Any]:
        """
        Call the OpenRouter API to generate optimized search queries
        
        Args:
            prompt: The prompt to send to the API
            
        Returns:
            Parsed JSON response from the API
        """
        try:
            # Set up API endpoint and headers
            api_url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": "https://bidder.app"  # Replace with your domain
            }
            
            # Prepare the request payload
            payload = {
                "model": OPENROUTER_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 1024,
                "temperature": 0.3  # Lower temperature for more deterministic responses
            }
            
            # Make the API request
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, headers=headers, json=payload, timeout=60) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"OpenRouter API request failed: Status {response.status}")
                        logger.error(f"Error response: {error_text[:200]}")
                        return {"error": f"API error: {response.status}"}
                    
                    result = await response.json()
            
            # Extract the response content
            if result and "choices" in result and len(result["choices"]) > 0:
                response_text = result["choices"][0]["message"]["content"]
                return {"text": response_text}
            else:
                logger.error(f"Unexpected API response format: {result}")
                return {"error": "Invalid response format"}
                
        except Exception as e:
            logger.error(f"Error calling OpenRouter API: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {"error": str(e)}
    
    @staticmethod
    def _process_llm_response(response: Dict[str, Any], item: Dict[str, Any]) -> Dict[str, str]:
        """
        Process and extract data from the LLM response
        
        Args:
            response: API response from OpenRouter
            item: Original auction item data
            
        Returns:
            Processed search queries and product info
        """
        try:
            if "text" not in response:
                return {"error": "No text in response"}
            
            response_text = response["text"]
            
            # Extract JSON from the response
            json_pattern = r'({[\s\S]*})'
            json_matches = re.search(json_pattern, response_text)
            
            if not json_matches:
                logger.warning(f"Could not find JSON in response: {response_text[:100]}...")
                return {"error": "No JSON in response"}
            
            json_str = json_matches.group(1)
            
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                logger.warning(f"Could not parse JSON: {json_str[:100]}...")
                return {"error": "Invalid JSON in response"}
            
            # Extract the search queries and info
            product_type = data.get("identified_product_type", "Unknown")
            brand = data.get("brand", "Unknown")
            model = data.get("model_name_number", "Unknown")
            
            # Flag items where LLM couldn't confidently identify the product
            insufficient_identification = (
                product_type in ["Unknown", "unclear", ""] or 
                brand in ["Unknown", "unclear", ""] or
                model in ["Unknown", "unclear", ""]
            )
            
            # Check if the item is too generic to be properly identified
            google_query = data.get("google_search_query", "")
            amazon_query = data.get("amazon_search_query", "")
            
            # If search queries are empty or identical to product/brand, that's a bad sign
            if not google_query or not amazon_query:
                insufficient_identification = True
            
            result = {
                "product_type": product_type,
                "brand": brand,
                "model": model,
                "attributes": data.get("other_relevant_attributes", "N/A"),
                "google_query": google_query,
                "amazon_query": amazon_query,
                "insufficient_identification": insufficient_identification
            }
            
            if insufficient_identification:
                logger.warning(f"LLM couldn't confidently identify item: {brand} {model} ({product_type})")
            else:
                logger.info(f"LLM identified: {result['brand']} {result['model']} ({result['product_type']})")
                logger.info(f"Google query: {result['google_query']}")
                logger.info(f"Amazon query: {result['amazon_query']}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing LLM response: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {"error": str(e)}
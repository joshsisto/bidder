"""
File utilities for the Auction Bot
"""

import os
import json
import time
from config import PROGRESS_DIR, HTML_DIR, IMAGES_DIR

def save_json(data, filename, directory=PROGRESS_DIR):
    """Save data to a JSON file in the specified directory"""
    try:
        filepath = os.path.join(directory, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return filepath
    except Exception as e:
        print(f"Error saving JSON file {filepath}: {e}")
        return None

def load_json(filename, directory=PROGRESS_DIR):
    """Load data from a JSON file in the specified directory"""
    try:
        filepath = os.path.join(directory, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading JSON file {filepath}: {e}")
        return None

def save_html(html_content, prefix="page", directory=HTML_DIR):
    """Save HTML content to a file with timestamp"""
    try:
        timestamp = int(time.time())
        filename = f"{prefix}_{timestamp}.html"
        filepath = os.path.join(directory, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        return filepath
    except Exception as e:
        print(f"Error saving HTML file: {e}")
        return None

def generate_image_filepath(lot_id, image_number, suffix="", directory=IMAGES_DIR):
    """Generate a filepath for an image based on lot ID and image number"""
    filename = f"item_{lot_id}_image_{image_number}{suffix}.jpg"
    return os.path.join(directory, filename)

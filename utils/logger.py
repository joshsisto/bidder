"""
Logging configuration for the Auction Bot
"""

import logging
import os
from config import LOGS_DIR

def setup_logger(name="AuctionBot", level=logging.DEBUG):
    """Set up and return a logger with file and console handlers"""
    
    # Define log format
    LOG_FORMAT = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Clear any existing handlers
    if logger.handlers:
        logger.handlers = []
    
    # Create handlers
    file_handler = logging.FileHandler(os.path.join(LOGS_DIR, f"{name.lower()}.log"))
    console_handler = logging.StreamHandler()
    
    # Set level and format for handlers
    file_handler.setLevel(level)
    console_handler.setLevel(level)
    
    formatter = logging.Formatter(LOG_FORMAT)
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

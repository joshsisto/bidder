"""
Generate reports from auction item data
"""

import os
import time
import pandas as pd

from config import OUTPUT_DIR, AUCTION_URL
from utils.logger import setup_logger

# Set up logger
logger = setup_logger("ReportGenerator")

class ReportGenerator:
    """Generate reports from auction item data"""
    
    @staticmethod
    def generate_excel_report(items, output_file="auction_opportunities.xlsx"):
        """Generate Excel report with sorted opportunities"""
        logger.info("Generating Excel report")
        
        try:
            # Create full path for output file
            output_path = os.path.join(OUTPUT_DIR, output_file)
            
            # Create DataFrame
            data = []
            for item in items:
                # Calculate profit margin percentage
                current_bid = item.get('current_bid_float', 0) or 0
                market_price = item.get('market_price', 0) or 0
                potential_profit = market_price - current_bid if market_price > 0 else 0
                
                # Calculate profit margin as a percentage
                profit_margin = 0
                if market_price > 0 and current_bid > 0:
                    profit_margin = (potential_profit / current_bid) * 100
                
                # Format the image URLs as a string
                image_urls = ', '.join(item.get('images', []))
                
                data.append({
                    'Lot Number': item.get('lotNumber', ''),
                    'Description': item.get('description', ''),
                    'Enhanced Description': item.get('enhanced_description', ''),
                    'Current Bid': current_bid,
                    'Market Price': market_price,
                    'Potential Profit': potential_profit,
                    'Profit Margin %': profit_margin,
                    'ROI': profit_margin,  # Added as duplicate column with different header
                    'Time Remaining': item.get('timeRemaining', ''),
                    'Item URL': item.get('itemUrl', ''),
                    'Image URLs': image_urls,
                    'OCR Text': item.get('ocr_text', '')
                })
            
            # Create DataFrame
            df = pd.DataFrame(data)
            
            # Add metadata
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            auction_name = AUCTION_URL.split('/')[-3]  # Extract auction name from URL
            
            # Sort by potential profit (descending)
            df = df.sort_values(by='Potential Profit', ascending=False)
            
            # Format the Excel file
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                # Write the main data
                df.to_excel(writer, sheet_name='Opportunities', index=False)
                
                # Create a metadata sheet
                metadata = pd.DataFrame({
                    'Property': ['Generated On', 'Auction URL', 'Total Items', 'Top Profit Item'],
                    'Value': [
                        timestamp, 
                        AUCTION_URL, 
                        len(df),
                        df.iloc[0]['Description'] if not df.empty else 'None'
                    ]
                })
                metadata.to_excel(writer, sheet_name='Metadata', index=False)
            
            logger.info(f"Report saved to {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Error generating Excel report: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

"""
Main entry point for the Auction Bot application
"""

import os
import time
import asyncio
import traceback
import platform

from config import (
    AUCTION_URL, MAX_ITEMS, ENABLE_AMAZON_SEARCH, GOOGLE_API_KEY, GOOGLE_CX, 
    DATA_DIR, ENABLE_VPN_CHECK, HEADLESS_BROWSER, TESSERACT_PATH
)
from utils.logger import setup_logger
from scraper.auction_bot import AuctionBot
from analyzer.report_generator import ReportGenerator

# Set up logger
logger = setup_logger("Main")

async def main():
    """Main function to run the auction bot"""
    # Display start banner
    print("\n" + "="*80)
    print(f"  AUCTION BOT SCRAPER - Starting at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80 + "\n")
    
    logger.info("Starting Auction Bot Scraper")
    
    # Display configuration
    print(f"⚙️  Configuration:")
    print(f"   - Platform: {platform.system()}")
    print(f"   - Max Items: {MAX_ITEMS}")
    print(f"   - Google Search: {'Enabled' if GOOGLE_API_KEY and GOOGLE_CX else 'Disabled (missing API keys)'}")
    print(f"   - Amazon Search: {'Enabled' if ENABLE_AMAZON_SEARCH else 'Disabled'}")
    print(f"   - VPN Check: {'Enabled' if ENABLE_VPN_CHECK else 'Disabled'}")
    print(f"   - Browser Mode: {'Headless' if HEADLESS_BROWSER else 'GUI (requires X Server)'}")
    print(f"   - Tesseract Path: {TESSERACT_PATH}")
    print(f"   - Data Directory: {DATA_DIR}")
    print()
    
    # Create bot instance
    bot = AuctionBot()
    
    try:
        # Check if IP is safe (if VPN check is enabled)
        if ENABLE_VPN_CHECK:
            if not bot.check_ip_safe():
                logger.error("Aborting due to unsafe IP")
                print("\n❌ ERROR: VPN check failed. Please enable your VPN before running this script.\n")
                return
            print(f"\n✅ VPN check passed! Your IP is protected.\n")
        else:
            logger.warning("VPN check is disabled. Your IP may not be protected.")
            print("\n⚠️  WARNING: VPN check is disabled. Your IP may not be protected.\n")
        print(f"🔍 Analyzing auction at: {AUCTION_URL}\n")
        
        # Process all items
        print("⏳ Processing auction items... (this may take several minutes)")
        success = await bot.process_all_items()
        if not success:
            logger.error("Failed to process auction items. Aborting.")
            print("\n❌ ERROR: Failed to process auction items. Check logs for details.\n")
            return
        
        print(f"✅ Successfully processed {len(bot.items)} items!\n")
        
        # Research market prices
        print("💲 Researching market prices... (this may take several minutes)")
        await bot.determine_market_prices()
        
        # Generate report
        print("📊 Generating final report...")
        report_file = ReportGenerator.generate_excel_report(bot.items)
        
        if report_file:
            print("\n" + "="*80)
            print(f"✅ PROCESS COMPLETED SUCCESSFULLY!")
            print(f"📈 Report available at: {report_file}")
            print("="*80 + "\n")
            logger.info(f"Process completed successfully. Report available at: {report_file}")
        else:
            print("\n❌ ERROR: Failed to generate report. Check logs for details.\n")
            logger.error("Failed to generate report")
            
    except KeyboardInterrupt:
        print("\n\n⚠️ Process interrupted by user. Saving current progress...\n")
        logger.warning("Process interrupted by user")
        
        # Try to save partial progress
        if hasattr(bot, 'items') and bot.items:
            from utils.file_utils import save_json
            progress_file = save_json(bot.items, f"interrupted_progress_{int(time.time())}.json")
            if progress_file:
                print(f"✅ Progress saved to {progress_file}\n")
            
    except Exception as e:
        print(f"\n❌ ERROR: Unexpected error occurred: {str(e)}\n")
        logger.error(f"Unexpected error: {e}")
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    # Set up pretty printing for console
    try:
        os.system('color')  # Enable ANSI color on Windows
    except:
        pass
    
    # Run the main async function
    asyncio.run(main())

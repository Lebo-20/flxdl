import os
import asyncio
import logging
from telethon import TelegramClient
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import main and set things up
import main
from main import process_drama_full

# Configuration
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

async def test_full(book_id):
    # Setup client
    client = TelegramClient('test_session', API_ID, API_HASH)
    await client.start(bot_token=BOT_TOKEN)
    
    # Correct Monkeypatching directly in main module
    original_get_ep = main.get_all_episodes
    
    async def fast_get_ep(bid):
        eps = await original_get_ep(bid)
        print(f"DEBUG: Found {len(eps)} total, picking first 2 only.")
        return eps[:2] # FAST test
        
    main.get_all_episodes = fast_get_ep
    main.client = client # Ensure main uses this connected client
    
    print(f"🚀 Starting fast 2-episode test for ID {book_id}...")
    success = await process_drama_full(book_id, ADMIN_ID)
    
    if success:
        print("✅ FAST TEST SUCCESSFUL!")
    else:
        print("❌ FAST TEST FAILED.")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(test_full("2858"))

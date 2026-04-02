import os
import asyncio
import logging
from telethon import TelegramClient
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import main
import main
from main import process_drama_full

# Configuration
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

async def test_full(book_id):
    client = TelegramClient('test_session', API_ID, API_HASH)
    await client.start(bot_token=BOT_TOKEN)
    
    main.client = client
    
    print(f"🚀 Starting full drama test for ID {book_id} (All Episodes)...")
    success = await process_drama_full(book_id, ADMIN_ID)
    
    if success:
        print("✅ FULL DRAMA TEST SUCCESSFUL!")
    else:
        print("❌ FULL DRAMA TEST FAILED.")
    
    await client.disconnect()

if __name__ == "__main__":
    import sys
    bid = sys.argv[1] if len(sys.argv) > 1 else "5715"
    asyncio.run(test_full(bid))

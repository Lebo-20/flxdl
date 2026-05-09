import asyncio
import os
import logging
from main import process_drama_full, client, AUTO_CHANNEL

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def trigger_manual():
    book_id = "6802" # Gerbong Muat
    chat_id = AUTO_CHANNEL
    
    print(f"--- Triggering Manual Process for ID: {book_id} ---")
    
    # We need to start the client session first
    await client.connect()
    if not await client.is_user_authorized():
        print("Bot is not authorized. Please check your credentials.")
        return

    # process_drama_full(book_id, chat_id, status_msg=None, title=None, thread_id=None)
    # This will download, merge and upload.
    # I'll pass a dummy object for status_msg that just prints to console.
    
    class DummyMsg:
        async def edit(self, text, **kwargs):
            print(f"[STATUS UPDATE]: {text}")
            return self
            
    status_msg = DummyMsg()
    
    try:
        success, success_count, total_count = await process_drama_full(
            book_id, chat_id, status_msg=status_msg
        )
        print(f"Final Result: Success={success}, Count={success_count}/{total_count}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(trigger_manual())

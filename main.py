import os
import asyncio
import logging
import shutil
import tempfile
import random
from telethon import TelegramClient, events, Button
from dotenv import load_dotenv

load_dotenv()

# Local imports
from api import (
    get_drama_detail, get_all_episodes, get_latest_dramas,
    get_trending_dramas, search_dramas
)
from downloader import download_all_episodes
from merge import merge_episodes
from uploader import upload_drama

# Configuration
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
AUTO_CHANNEL = int(os.environ.get("AUTO_CHANNEL", ADMIN_ID)) # Default post to admin
PROCESSED_FILE = "processed.json"

# Initialize state
def load_processed():
    if os.path.exists(PROCESSED_FILE):
        import json
        with open(PROCESSED_FILE, "r") as f:
            try:
                return set(json.load(f))
            except:
                return set()
    return set()

def save_processed(data):
    import json
    with open(PROCESSED_FILE, "w") as f:
        json.dump(list(data), f)

processed_ids = load_processed()

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Bot State
class BotState:
    is_auto_running = True
    is_processing = False

# Initialize client
client = TelegramClient('dramabox_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

def get_panel_buttons():
    status_text = "🟢 RUNNING" if BotState.is_auto_running else "🔴 STOPPED"
    return [
        [Button.inline("▶️ Start Auto", b"start_auto"), Button.inline("⏹ Stop Auto", b"stop_auto")],
        [Button.inline(f"📊 Status: {status_text}", b"status")]
    ]

@client.on(events.NewMessage(pattern='/update'))
async def update_bot(event):
    if event.sender_id != ADMIN_ID:
        return
    import subprocess
    import sys
    
    status_msg = await event.reply("🔄 Menarik pembaruan dari GitHub...")
    try:
        # Run git pull
        result = subprocess.run(["git", "pull", "origin", "main"], capture_output=True, text=True)
        await status_msg.edit(f"✅ Repositori berhasil di-pull:\n```\n{result.stdout}\n```\n\nSedang memulai ulang sistem (Restarting)...")
        
        # Restart the script forcefully replacing the current process image
        os.execl(sys.executable, sys.executable, *sys.argv)
    except Exception as e:
        await status_msg.edit(f"❌ Gagal melakukan update: {e}")

@client.on(events.NewMessage(pattern='/panel'))
async def panel(event):
    if event.chat_id != ADMIN_ID:
        return
    await event.reply("🎛 **Dramabox (FlickReels) Control Panel**", buttons=get_panel_buttons())

@client.on(events.CallbackQuery())
async def panel_callback(event):
    if event.sender_id != ADMIN_ID:
        return
        
    data = event.data
    
    try:
        if data == b"start_auto":
            BotState.is_auto_running = True
            await event.answer("Auto-mode started!")
            await event.edit("🎛 **FlickReels Control Panel**", buttons=get_panel_buttons())
        elif data == b"stop_auto":
            BotState.is_auto_running = False
            await event.answer("Auto-mode stopped!")
            await event.edit("🎛 **FlickReels Control Panel**", buttons=get_panel_buttons())
        elif data == b"status":
            await event.answer(f"Status: {'Running' if BotState.is_auto_running else 'Stopped'}")
            await event.edit("🎛 **FlickReels Control Panel**", buttons=get_panel_buttons())
    except Exception as e:
        if "message is not modified" in str(e).lower() or "Message string and reply markup" in str(e):
            pass 
        else:
            logger.error(f"Callback error: {e}")

@client.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.reply("Welcome to FlickReels Downloader Bot! 🎉\n\nGunakan perintah `/download {bookId}` untuk mulai.")

@client.on(events.NewMessage(pattern=r'/download (\d+)'))
async def on_download(event):
    chat_id = event.chat_id
    
    # Check admin
    if chat_id != ADMIN_ID:
        await event.reply("❌ Maaf, perintah ini hanya untuk admin.")
        return
        
    if BotState.is_processing:
        await event.reply("⚠️ Sedang memproses drama lain. Tunggu hingga selesai (Anti bentrok).")
        return
        
    book_id = event.pattern_match.group(1)
    
    # 1. Fetch data
    detail = await get_drama_detail(book_id)
    if not detail:
        await event.reply(f"❌ Gagal mendapatkan detail drama `{book_id}`.")
        return
        
    episodes = await get_all_episodes(book_id)
    if not episodes:
        await event.reply(f"❌ Drama `{book_id}` tidak memiliki episode.")
        return
    
    title = detail.get("title") or detail.get("bookName") or detail.get("name") or f"Drama_{book_id}"
    
    status_msg = await event.reply(f"🎬 Drama: **{title}**\n📽 Total Episodes: {len(episodes)}\n\n⏳ Sedang mendownload dan memproses...")
    
    BotState.is_processing = True
    processed_ids.add(book_id)
    save_processed(processed_ids)
    
    await process_drama_full(book_id, chat_id, status_msg, title=title)
    BotState.is_processing = False

async def process_drama_full(book_id, chat_id, status_msg=None, title=None):
    """Downloads, merges, and uploads a drama."""
    detail = await get_drama_detail(book_id)
    episodes = await get_all_episodes(book_id)
    
    if not detail or not episodes:
        if status_msg: await status_msg.edit(f"❌ Detail atau Episode `{book_id}` tidak ditemukan.")
        return False

    # Use title from argument if provided, otherwise fallback to detail metadata
    title = title or detail.get("title") or detail.get("bookName") or detail.get("name") or f"Drama_{book_id}"
    description = detail.get("intro") or detail.get("introduction") or detail.get("description") or "No description available."
    poster = detail.get("cover") or detail.get("coverWap") or detail.get("poster") or ""
    
    # 2. Setup temp directory
    temp_dir = tempfile.mkdtemp(prefix=f"flickreels_{book_id}_")
    video_dir = os.path.join(temp_dir, "episodes")
    os.makedirs(video_dir, exist_ok=True)
    
    try:
        if status_msg: await status_msg.edit(f"🎬 Processing **{title}**...")
        
        # 3. Download (pass book_id so downloader can refresh URLs on 403)
        success = await download_all_episodes(episodes, video_dir, book_id=book_id)
        if not success:
            if status_msg: await status_msg.edit("❌ Download Gagal.")
            return False

        # 4. Merge
        output_video_path = os.path.join(temp_dir, f"{title}.mp4")
        merge_success = merge_episodes(video_dir, output_video_path)
        if not merge_success:
            if status_msg: await status_msg.edit("❌ Merge Gagal.")
            return False

        # 5. Upload
        upload_success = await upload_drama(
            client, chat_id, 
            title, description, 
            poster, output_video_path
        )
        
        if upload_success:
            if status_msg: await status_msg.delete()
            return True
        else:
            if status_msg: await status_msg.edit("❌ Upload Gagal.")
            return False
            
    except Exception as e:
        logger.error(f"Error processing {book_id}: {e}")
        if status_msg: await status_msg.edit(f"❌ Error: {e}")
        return False
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

async def auto_mode_loop():
    """Loop to find and process new dramas automatically using FlickReels API."""
    global processed_ids
    
    logger.info("🚀 FlickReels Auto-Mode Started.")
    
    is_initial_run = True
    
    while True:
        if not BotState.is_auto_running:
            await asyncio.sleep(5)
            continue
            
        try:
            interval = 5 if is_initial_run else 15
            logger.info(f"🔍 Scanning for new dramas (Next scan in {interval}m)...")
            
            # --- SOURCE 1: Latest Drams from Nexthome ---
            logger.info("🔍 Scanning Latest (Nexthome)...")
            latest_dramas = await get_latest_dramas(pages=3 if is_initial_run else 1) or []
            api1_new = [d for d in latest_dramas if str(d.get("playlet_id") or d.get("bookId") or d.get("id") or d.get("bookid", "")) not in processed_ids]
            
            # --- SOURCE 2: Trending ---
            logger.info("🔍 Scanning Trending...")
            trending_dramas = await get_trending_dramas() or []
            api2_new = [d for d in trending_dramas if str(d.get("playlet_id") or d.get("bookId") or d.get("id") or d.get("bookid", "")) not in processed_ids]
            
            # Combine and deduplicate
            new_queue = []
            seen_ids_in_batch = set()
            
            # Interleave latest and trending or just concat
            raw_queue = api1_new + api2_new
            
            for d in raw_queue:
                bid = str(d.get("playlet_id") or d.get("bookId") or d.get("id") or d.get("bookid", ""))
                if bid and bid not in processed_ids and bid not in seen_ids_in_batch:
                    new_queue.append(d)
                    seen_ids_in_batch.add(bid)
            
            if not new_queue and not is_initial_run:
                # Fallback: Search for some generic keywords to find new content
                logger.info("ℹ️ No new dramas in Latest/Trending. Checking search fallback...")
                fallbacks = ["cinta", "ceo", "istri", "suami"]
                rand_q = random.choice(fallbacks)
                search_res = await search_dramas(rand_q)
                for d in search_res:
                    bid = str(d.get("playlet_id") or d.get("bookId") or d.get("id") or d.get("bookid", ""))
                    if bid and bid not in processed_ids and bid not in seen_ids_in_batch:
                        new_queue.append(d)
                        seen_ids_in_batch.add(bid)
                        break 
            
            new_found = 0
            for drama in new_queue:
                if not BotState.is_auto_running:
                    break
                    
                book_id = str(drama.get("playlet_id") or drama.get("bookId") or drama.get("id") or drama.get("bookid", ""))
                if not book_id:
                    continue
                    
                processed_ids.add(book_id)
                save_processed(processed_ids)
                
                new_found += 1
                title = drama.get("title") or drama.get("bookName") or drama.get("name") or "Unknown"
                logger.info(f"✨ New FlickReels drama: {title} ({book_id}). Starting process...")
                
                try:
                    await client.send_message(ADMIN_ID, f"🆕 **FlickReels Detection!**\n🎬 `{title}`\n🆔 `{book_id}`\n⏳ Processing...")
                except: pass
                
                BotState.is_processing = True
                success = await process_drama_full(book_id, AUTO_CHANNEL, title=title)
                BotState.is_processing = False
                
                if success:
                    logger.info(f"✅ Finished {title}")
                    try:
                        await client.send_message(ADMIN_ID, f"✅ Sukses Auto-Post: **{title}**")
                    except: pass
                else:
                    logger.error(f"❌ Failed to process {title}")
                
                await asyncio.sleep(10)
            
            if new_found == 0:
                logger.info("😴 No new dramas found.")
            
            is_initial_run = False
            for _ in range(interval * 60):
                if not BotState.is_auto_running:
                    break
                await asyncio.sleep(1)
            
        except Exception as e:
            logger.error(f"⚠️ Error in auto_mode_loop: {e}")
            await asyncio.sleep(60)

if __name__ == '__main__':
    logger.info("Initializing FlickReels Auto-Bot...")
    client.loop.create_task(auto_mode_loop())
    logger.info("Bot is active and monitoring FlickReels API.")
    client.run_until_disconnected()

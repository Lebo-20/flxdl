import os
import asyncio
import logging
import shutil
import tempfile
import random
import psycopg2
from telethon import TelegramClient, events, Button
from dotenv import load_dotenv

load_dotenv()

# Local imports
from api import (
    get_drama_detail, get_all_episodes, get_latest_dramas,
    get_trending_dramas, get_home_dramas, search_dramas, get_list_dramas
)
from downloader import download_all_episodes
from merge import merge_episodes
from uploader import upload_drama

# Configuration
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
# Handle multiple admins if provided in ADMIN_ID env (e.g. "ID1,ID2")
ADMIN_VAL = os.environ.get("ADMIN_ID", "0")
if "," in ADMIN_VAL:
    ADMIN_IDS = [int(x.strip()) for x in ADMIN_VAL.split(",") if x.strip()]
else:
    ADMIN_IDS = [int(ADMIN_VAL)]

ADMIN_ID = ADMIN_IDS[0] # Primary admin for fallbacks
AUTO_CHANNEL = int(os.environ.get("AUTO_CHANNEL", ADMIN_ID)) # Default post to admin
AUTO_THREAD_ID = int(os.environ.get("AUTO_THREAD_ID", "0")) or None # Topic ID for the group
# Database Configuration
DATABASE_URL = os.environ.get("DATABASE_URL")

class Database:
    def __init__(self, db_url):
        self.db_url = db_url
        self.create_tables()
        
    def get_conn(self):
        return psycopg2.connect(self.db_url)
        
    def create_tables(self):
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_dramas (
                book_id TEXT PRIMARY KEY,
                title TEXT,
                status TEXT, -- 'success', 'failed'
                attempts INTEGER DEFAULT 0
            )
        ''')
        conn.commit()
        cursor.close()
        conn.close()
        
    def is_processed(self, book_id, title=None):
        conn = self.get_conn()
        cursor = conn.cursor()
        # Check by book_id
        cursor.execute("SELECT status, attempts FROM processed_dramas WHERE book_id = %s", (str(book_id),))
        row = cursor.fetchone()
        
        # Also check by title if provided (as requested by user to store/check titles)
        if not row and title:
            cursor.execute("SELECT status, attempts FROM processed_dramas WHERE title = %s AND status = 'success'", (title,))
            row = cursor.fetchone()
            
        cursor.close()
        conn.close()
        
        if not row:
            return False
            
        status, attempts = row
        # Skip if success OR if failed after 2 attempts
        if status == 'success' or attempts >= 2:
            return True
        return False
        
    def mark_success(self, book_id, title):
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO processed_dramas (book_id, title, status, attempts) 
            VALUES (%s, %s, 'success', 1)
            ON CONFLICT(book_id) DO UPDATE SET status = 'success', attempts = processed_dramas.attempts + 1
        """, (str(book_id), title))
        conn.commit()
        cursor.close()
        conn.close()
        
    def mark_failed(self, book_id, title):
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO processed_dramas (book_id, title, status, attempts) 
            VALUES (%s, %s, 'failed', 1)
            ON CONFLICT(book_id) DO UPDATE SET attempts = processed_dramas.attempts + 1
        """, (str(book_id), title))
        conn.commit()
        cursor.close()
        conn.close()

db = Database(DATABASE_URL)

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Bot State
class BotState:
    is_auto_running = True
    is_processing = False

async def safe_edit(msg_or_msgs, text, **kwargs):
    """Edits a single message or a list of messages."""
    if not msg_or_msgs:
        return
    if isinstance(msg_or_msgs, list):
        for m in msg_or_msgs:
            try: await m.edit(text, **kwargs)
            except: pass
    else:
        try: await msg_or_msgs.edit(text, **kwargs)
        except: pass

# Initialize client
client = TelegramClient('dramabox_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

def get_panel_buttons():
    status_text = "🟢 RUNNING" if BotState.is_auto_running else "🔴 STOPPED"
    return [
        [Button.inline("▶️ Start Auto", b"start_auto"), Button.inline("⏹ Stop Auto", b"stop_auto")],
        [Button.inline(f"📊 Status: {status_text}", b"status")]
    ]

@client.on(events.NewMessage(pattern='/flickreels update'))
async def update_bot(event):
    if event.sender_id not in ADMIN_IDS:
        return
    import subprocess
    import sys
    
    status_msg = await event.reply("🔄 Menarik pembaruan dari GitHub...")
    try:
        # Run git pull
        result = subprocess.run(["git", "pull", "origin", "main"], capture_output=True, text=True)
        
        # Auto delete session files if requested for fresh start
        for file in os.listdir("."):
            if file.endswith(".session") or file.endswith(".session-journal"):
                try:
                    os.remove(file)
                    logger.info(f"Deleted session file: {file}")
                except:
                    pass
                    
        await status_msg.edit(f"✅ Repositori berhasil di-pull:\n```\n{result.stdout}\n```\n\nSedang memulai ulang sistem (Restarting)...")
        
        # Restart the script forcefully replacing the current process image
        os.execl(sys.executable, sys.executable, *sys.argv)
    except Exception as e:
        await status_msg.edit(f"❌ Gagal melakukan update: {e}")

@client.on(events.NewMessage(pattern='/flickreels panel'))
async def panel(event):
    if event.sender_id not in ADMIN_IDS:
        return
    await event.reply("🎛 **FlickReels Control Panel**", buttons=get_panel_buttons())

@client.on(events.CallbackQuery())
async def panel_callback(event):
    if event.sender_id not in ADMIN_IDS:
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

@client.on(events.NewMessage(pattern='/flickreels status'))
async def on_status_cmd(event):
    if event.sender_id not in ADMIN_IDS:
        return
    
    # Get database count
    try:
        conn = db.get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM processed_dramas WHERE status = 'success'")
        success_count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
    except:
        success_count = "N/A"
    
    status_text = "🟢 RUNNING (Auto)" if BotState.is_auto_running else "🔴 STOPPED (Auto)"
    process_text = "🔄 PROCESSING" if BotState.is_processing else "✅ IDLE"
    
    text = (
        "🎬 **FlickReels Bot Status**\n\n"
        f"📡 **Mode Auto:** {status_text}\n"
        f"⚙️ **Status Proses:** {process_text}\n"
        f"📊 **Database:** `{success_count}` Drama Berhasil\n\n"
        "⚡ **Prioritas:** Manual command diutamakan!"
    )
    await event.reply(text)

@client.on(events.NewMessage(pattern='/flickreels start'))
async def start(event):
    await event.reply("Welcome to FlickReels Downloader Bot! 🎉\n\nGunakan:\n- `/flickreels download {ID}` untuk download drama.\n- `/flickreels cari {judul}` untuk mencari drama.\n- `/flickreels status` untuk cek proses.\n- `/flickreels panel` untuk kontrol.")

@client.on(events.NewMessage(pattern=r'/flickreels list'))
async def on_list(event):
    if event.sender_id not in ADMIN_IDS:
        return
        
    status_msg = await event.reply("🔍 Mengambil daftar drama terbaru dari API...")
    
    try:
        latest = await get_latest_dramas(pages=1)
        if not latest:
            await status_msg.edit("❌ Gagal mengambil daftar drama.")
            return
            
        text = "🎬 **Daftar Drama Terbaru:**\n\n"
        for i, d in enumerate(latest[:20], 1):
            title = d.get("title") or d.get("bookName") or d.get("name") or "Unknown"
            bid = str(d.get("playlet_id") or d.get("bookId") or d.get("id") or "")
            if bid:
                text += f"{i}. **{title}**\n   ID: `/download {bid}`\n"
                
        await status_msg.edit(text)
    except Exception as e:
        logger.error(f"List error: {e}")
        await status_msg.edit(f"❌ Terjadi kesalahan: {e}")

@client.on(events.NewMessage(pattern=r'/flickreels cari (.+)'))
async def on_search(event):
    if event.sender_id not in ADMIN_IDS:
        return
        
    chat_id = event.chat_id
    query = event.pattern_match.group(1)
    status_msg = await event.reply(f"🔍 Mencari drama untuk: **{query}**...")
    
    try:
        results = await search_dramas(query)
        if not results:
            await status_msg.edit(f"❌ Tidak ditemukan hasil untuk `{query}`.")
            return
            
        text = f"🔍 **Hasil Pencarian ({len(results)}):**\n\n"
        for i, res in enumerate(results[:15], 1): # Limit to 15 results
            title = res.get("title") or res.get("bookName") or "Unknown"
            bid = str(res.get("playlet_id") or res.get("bookId") or res.get("id") or "")
            if bid:
                text += f"{i}. **{title}**\n   ID: `/download {bid}`\n\n"
        
        if len(results) > 15:
            text += "*(Hasil dibatasi 15 teratas)*"
            
        await status_msg.edit(text)
    except Exception as e:
        logger.error(f"Search error: {e}")
        await status_msg.edit(f"❌ Terjadi kesalahan saat mencari: {e}")

@client.on(events.NewMessage(pattern=r'/flickreels download (\d+)'))
async def on_download(event):
    # Check admin by sender_id (allows command in groups)
    if event.sender_id not in ADMIN_IDS:
        await event.reply("❌ Maaf, perintah ini hanya untuk admin.")
        return
        
    chat_id = event.chat_id
        
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
    
    success = await process_drama_full(book_id, chat_id, status_msg, title=title)
    
    BotState.is_processing = False

async def process_drama_full(book_id, chat_id, status_msg=None, title=None, thread_id=None):
    """Downloads, merges, and uploads a drama."""
    # 1. Fetch data
    detail = await get_drama_detail(book_id)
    if not detail:
        if status_msg: await safe_edit(status_msg, f"❌ Detail `{book_id}` tidak ditemukan.")
        logger.error(f"❌ Failed to fetch detail for {book_id}")
        return False
        
    episodes = await get_all_episodes(book_id, detail=detail)
    
    if not episodes:
        if status_msg: await safe_edit(status_msg, f"❌ Episode `{book_id}` tidak ditemukan atau kosong.")
        logger.error(f"❌ No episodes found for {book_id} ('{detail.get('title')}')")
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
        if status_msg: await safe_edit(status_msg, f"🎬 Processing **{title}**...")
        
        # 3. Download (pass book_id so downloader can refresh URLs on 403)
        success = await download_all_episodes(episodes, video_dir, book_id=book_id, status_msg=status_msg, title=title)
        if not success:
            if status_msg: await safe_edit(status_msg, "❌ Download Gagal.")
            return False

        # 4. Merge
        output_video_path = os.path.join(temp_dir, f"{title}.mp4")
        merge_success = await merge_episodes(video_dir, output_video_path)
        if not merge_success:
            if status_msg: await safe_edit(status_msg, "❌ Merge Gagal.")
            return False

        # 5. Upload
        upload_success = await upload_drama(
            client, chat_id, 
            title, description, 
            poster, output_video_path,
            thread_id=thread_id,
            status_msg=status_msg
        )
        
        if upload_success:
            return True
        else:
            if status_msg: await safe_edit(status_msg, "❌ Upload Gagal.")
            return False
            
    except Exception as e:
        logger.error(f"Error processing {book_id}: {e}")
        if status_msg: await safe_edit(status_msg, f"❌ Error: {e}")
        return False
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

async def auto_mode_loop():
    """Loop to find and process new dramas automatically using FlickReels API."""
    
    logger.info("🚀 FlickReels Auto-Mode Started.")
    
    is_initial_run = True
    
    while True:
        if not BotState.is_auto_running:
            await asyncio.sleep(5)
            continue
            
        try:
            interval = 5 if is_initial_run else 15
            logger.info(f"🔍 Scanning for new dramas (Next scan in {interval}m)...")
            
            # --- SOURCE 1: Home (/api/home) ---
            logger.info("🔍 Scanning Home (/api/home)...")
            home_dramas = await get_home_dramas() or []
            api1_new = [d for d in home_dramas if not db.is_processed(
                str(d.get("playlet_id") or d.get("bookId") or d.get("id") or d.get("bookid", "")),
                title=d.get("title") or d.get("bookName") or d.get("name")
            )]
            
            # --- SOURCE 2: List (/api/list) ---
            logger.info("🔍 Scanning List (/api/list)...")
            list_dramas = await get_list_dramas() or []
            api2_new = [d for d in list_dramas if not db.is_processed(
                str(d.get("playlet_id") or d.get("bookId") or d.get("id") or d.get("bookid", "")),
                title=d.get("title") or d.get("bookName") or d.get("name")
            )]

            # --- SOURCE 3: Trending ---
            logger.info("🔍 Scanning Trending...")
            trending_dramas = await get_trending_dramas() or []
            api3_new = [d for d in trending_dramas if not db.is_processed(
                str(d.get("playlet_id") or d.get("bookId") or d.get("id") or d.get("bookid", "")),
                title=d.get("title") or d.get("bookName") or d.get("name")
            )]
            
            # Combine and Rotate (Interleave)
            new_queue = []
            seen_ids_in_batch = set()
            
            # Interleave sources
            max_len = max(len(api1_new), len(api2_new), len(api3_new))
            raw_queue = []
            for i in range(max_len):
                if i < len(api1_new): raw_queue.append(api1_new[i])
                if i < len(api2_new): raw_queue.append(api2_new[i])
                if i < len(api3_new): raw_queue.append(api3_new[i])
            
            for d in raw_queue:
                bid = str(d.get("playlet_id") or d.get("bookId") or d.get("id") or d.get("bookid", ""))
                title = d.get("title") or d.get("bookName") or d.get("name")
                if bid and not db.is_processed(bid, title=title) and bid not in seen_ids_in_batch:
                    new_queue.append(d)
                    seen_ids_in_batch.add(bid)
            
            if not new_queue and not is_initial_run:
                # Fallback: Search for some generic keywords to find new content
                logger.info("ℹ️ No new dramas in main sources. Checking search fallback...")
                fallbacks = ["cinta", "ceo", "istri", "suami"]
                rand_q = random.choice(fallbacks)
                search_res = await search_dramas(rand_q)
                for d in search_res:
                    bid = str(d.get("playlet_id") or d.get("bookId") or d.get("id") or d.get("bookid", ""))
                    title = d.get("title") or d.get("bookName") or d.get("name")
                    if bid and not db.is_processed(bid, title=title) and bid not in seen_ids_in_batch:
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
                    
                new_found += 1
                title = drama.get("title") or drama.get("bookName") or drama.get("name") or "Unknown"
                logger.info(f"✨ New FlickReels drama: {title} ({book_id}). Starting process...")
                
                try:
                    status_msgs = []
                    for admin in ADMIN_IDS:
                        m = await client.send_message(admin, f"🆕 **FlickReels Detection!**\n🎬 `{title}`\n🆔 `{book_id}`\n⏳ Processing...")
                        status_msgs.append(m)
                except: 
                    status_msgs = None

                BotState.is_processing = True
                success = await process_drama_full(book_id, AUTO_CHANNEL, status_msg=status_msgs, title=title, thread_id=AUTO_THREAD_ID)
                BotState.is_processing = False
                
                if success:
                    db.mark_success(book_id, title)
                    logger.info(f"✅ Finished {title}")
                    try:
                        await safe_edit(status_msgs, f"✅ Sukses Auto-Post: **{title}**\n\n💤 Bot istirahat 30 menit (Auto-Mode).")
                    except: pass
                    
                    # 30-minute rest after successful auto-upload
                    logger.info("💤 Resting for 30 minutes after successful auto-upload...")
                    for _ in range(30 * 60):
                        if not BotState.is_auto_running:
                            break
                        await asyncio.sleep(1)
                else:
                    db.mark_failed(book_id, title)
                    logger.error(f"❌ Failed to process {title} ({book_id})")
                    try:
                        await safe_edit(status_msgs, f"❌ Gagal memproses: **{title}** ({book_id})")
                    except: pass
                
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

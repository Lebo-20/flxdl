import os
import asyncio
from telethon import TelegramClient, events
from telethon.tl.types import DocumentAttributeVideo
import logging

logger = logging.getLogger(__name__)

from utils import get_progress_bar

async def upload_progress(current, total, event, msg_text="Uploading..."):
    """Callback function for upload progress."""
    try:
        bar = get_progress_bar(current, total)
        # Avoid flood by updating every few percentages
        last_percent = getattr(event, '_last_percent', -1) if not isinstance(event, list) else getattr(event[0], '_last_percent', -1)
        current_percent = int((current / total) * 100)
        
        if current_percent >= last_percent + 5 or current == total:
            if isinstance(event, list):
                for e in event: e._last_percent = current_percent
            else:
                event._last_percent = current_percent
                
            text = f"**{msg_text}**\n`{bar}`\n{current / (1024*1024):.1f} MB / {total / (1024*1024):.1f} MB ({current_percent}%)"
            
            if isinstance(event, list):
                for m in event:
                    try: await m.edit(text)
                    except: pass
            else:
                try: await event.edit(text)
                except: pass
    except Exception as e:
        logger.debug(f"Progress edit failed: {e}")

async def upload_drama(client: TelegramClient, chat_id: int, 
                       title: str, description: str, 
                       poster_url: str, video_path: str,
                       thread_id: int = None,
                       status_msg = None):
    """
    Uploads the drama information and merged video to Telegram.
    Ensures video is uploaded BEFORE sending poster/details to the channel.
    """
    import subprocess
    import tempfile
    import httpx
    
    # 1. Prepare Metadata & Thumbnail
    msg_text = "📤 Menyiapkan metadata & thumbnail..."
    if status_msg:
        if isinstance(status_msg, list):
            for m in status_msg:
                try: await m.edit(msg_text)
                except: pass
        else:
            try: await status_msg.edit(msg_text)
            except: pass

    duration = 0
    width = 0
    height = 0
    try:
        ffprobe_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height", "-of", "default=noprint_wrappers=1:nokey=1", video_path]
        process = await asyncio.create_subprocess_exec(
            *ffprobe_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await process.communicate()
        output = stdout.decode().strip().split('\n')
        if len(output) >= 3:
            width = int(output[0])
            height = int(output[1])
            duration = int(float(output[2]))
    except Exception as e:
        logger.warning(f"Failed to extract video info: {e}")

    thumb_path = os.path.join(tempfile.gettempdir(), f"thumb_{os.path.basename(video_path)}.jpg")
    try:
        cmd = ["ffmpeg", "-y", "-i", video_path, "-ss", "00:00:01.000", "-vframes", "1", thumb_path]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.wait()
        if not os.path.exists(thumb_path):
            thumb_path = None
    except Exception as e:
        logger.warning(f"Failed to generate thumbnail: {e}")
        thumb_path = None

    # 2. Upload video file to Telegram servers (without sending yet)
    msg_text = f"📤 Sedang mengupload video: **{title}**..."
    
    # Create a status message in the target channel to show progress as requested
    channel_progress_msg = await client.send_message(chat_id, msg_text, reply_to=thread_id)
    
    # Combine status messages for combined progress updates
    all_status_msgs = []
    if status_msg:
        if isinstance(status_msg, list): all_status_msgs.extend(status_msg)
        else: all_status_msgs.append(status_msg)
    all_status_msgs.append(channel_progress_msg)

    try:
        uploaded_file = await client.upload_file(
            video_path,
            progress_callback=lambda c, t: upload_progress(c, t, all_status_msgs, f"Upload Video: {title}")
        )
        
        # 3. Now that upload succeeded, send Poster + Details
        if description and description != "No description available.":
            caption = f"🎬 **{title}**\n\n📝 **Sinopsis:**\n{description[:800]}..."
        else:
            caption = f"🎬 **{title}**\n\n"
        
        poster_path = None
        try:
            async with httpx.AsyncClient(timeout=30) as http_client:
                resp = await http_client.get(poster_url)
                if resp.status_code == 200:
                    poster_path = os.path.join(tempfile.gettempdir(), f"poster_{title[:20].replace(' ','_')}.jpg")
                    with open(poster_path, "wb") as pf:
                        pf.write(resp.content)
        except Exception as e:
            logger.warning(f"Failed to download poster: {e}")

        # Send Poster
        await client.send_file(
            chat_id,
            poster_path or poster_url,
            caption=caption,
            parse_mode='md',
            reply_to=thread_id,
            force_document=False
        )
        
        if poster_path and os.path.exists(poster_path):
            os.remove(poster_path)

        # 4. Send the Video (Instant because it's already uploaded)
        video_attributes = [
            DocumentAttributeVideo(
                duration=duration,
                w=width,
                h=height,
                supports_streaming=True
            )
        ]
        
        await client.send_file(
            chat_id,
            uploaded_file,
            caption=f"🎥 Full Episode: {title}",
            force_document=False,
            thumb=thumb_path,
            reply_to=thread_id,
            attributes=video_attributes,
            supports_streaming=True
        )

        # Finalize status messages
        final_msg = f"✅ Sukses Terunggah: **{title}**"
        for m in all_status_msgs:
            try: await m.edit(final_msg)
            except: pass
            
        if thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path)
            
        return True

    except Exception as e:
        logger.error(f"Failed during upload/send: {e}")
        error_msg = f"❌ Gagal Upload: **{title}**\nError: {str(e)[:100]}"
        for m in all_status_msgs:
            try: await m.edit(error_msg)
            except: pass
        return False

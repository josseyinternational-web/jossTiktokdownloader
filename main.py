import os
import logging
import tempfile
import yt_dlp
import subprocess
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise RuntimeError("❌ Missing TELEGRAM_TOKEN")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Yo, I'm *Joss*! 🎵\n\n"
        "📥 Drop a TikTok link — I'll send:\n"
        "✅ HD video (with sound)\n"
        "🎵 Separate MP3 (extracted from video)\n"
        "🖼️ All images (if it's a carousel post)\n"
        "🚀 Instantly — no limits!",
        parse_mode='Markdown'
    )

async def handle_tiktok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if "tiktok.com" not in text:
        return await update.message.reply_text("⚠️ Please send a valid TikTok link")

    msg = await update.message.reply_text("⏳ Downloading...")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Step 1: Get metadata to detect carousel/slideshow
            ydl_opts_meta = {'quiet': True, 'no_warnings': True, 'extract_flat': True}
            with yt_dlp.YoutubeDL(ydl_opts_meta) as ydl:
                info = ydl.extract_info(text, download=False)

            # Step 2: Extract high-res images from thumbnails (TikTok carousel)
            image_urls = []
            for thumb in info.get('thumbnails', []):
                url = thumb.get('url', '')
                # Filter for likely original images (not previews)
                if any(kw in url for kw in [
                    '/xl/', 'ratio=1080', 'quality=100', 'size=l',
                    'width=1080', 'height=1920', 'format=jpg'
                ]) and url.endswith(('.jpg', '.jpeg', '.png')):
                    image_urls.append(url)

            if image_urls:
                await msg.edit_text(f"🖼️ Downloading {len(image_urls)} images + audio...")
                sent_count = 0
                for i, img_url in enumerate(image_urls[:10]):  # max 10 images
                    try:
                        resp = requests.get(img_url, timeout=10)
                        resp.raise_for_status()
                        await update.message.reply_photo(resp.content)
                        sent_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to download image {i+1}: {e}")
                        continue

                # Download audio
                ydl_opts_audio = {
                    'format': 'ba[ext=m4a]',
                    'outtmpl': os.path.join(tmpdir, 'audio.m4a'),
                    'quiet': True
                }
                with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl:
                    ydl.download([text])
                await update.message.reply_audio(
                    open(os.path.join(tmpdir, 'audio.m4a'), 'rb'),
                    title=info.get('title', 'Audio')
                )
                await msg.edit_text(f"🎉 Done! {sent_count} images + MP3 sent")
                return

            # Step 3: Normal video flow (your original logic)
            ydl_opts = {
                'outtmpl': os.path.join(tmpdir, '%(id)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'format': 'bv[height<=1080]+ba/b',
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(text, download=True)
                video_path = ydl.prepare_filename(info)

            # Fix .webm → .mp4
            if video_path.endswith('.webm'):
                mp4_path = video_path.replace('.webm', '.mp4')
                os.rename(video_path, mp4_path)
                video_path = mp4_path

            # Send video
            await msg.edit_text("📤 Sending video...")
            await update.message.reply_video(
                open(video_path, 'rb'),
                caption=f"🎬 {info.get('title', 'TikTok Video')}",
                supports_streaming=True
            )

            # Extract MP3
            mp3_path = video_path.replace('.mp4', '.mp3')
            try:
                subprocess.run([
                    'ffmpeg', '-i', video_path, '-vn',
                    '-acodec', 'libmp3lame', '-ab', '128k', mp3_path
                ], check=True, capture_output=True)
                await msg.edit_text("🎵 Sending MP3...")
                await update.message.reply_audio(
                    open(mp3_path, 'rb'),
                    title=info.get('title', 'Audio')
                )
            except Exception as e:
                logger.warning(f"MP3 extraction failed: {e}")
                await update.message.reply_audio(
                    open(video_path, 'rb'),
                    title=info.get('title', 'Audio (from video)')
                )

        await msg.edit_text("🎉 Done! Video + MP3 sent ✅")

    except Exception as e:
        await msg.edit_text(f"❌ Failed: {str(e)[:80]}")

if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_tiktok))
    app.run_polling()

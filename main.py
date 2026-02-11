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
            # Fetch metadata to check for slideshow
            ydl_opts_meta = {'quiet': True, 'no_warnings': True, 'extract_flat': True}
            with yt_dlp.YoutubeDL(ydl_opts_meta) as ydl:
                info = ydl.extract_info(text, download=False)

            # Handle slideshow: short duration + multiple thumbnails
            if info.get('thumbnails') and info.get('duration', 0) < 5 and len(info.get('thumbnails', [])) >= 2:
                await msg.edit_text("🖼️ Downloading slideshow images + audio...")
                
                # Download all images
                for i, thumb in enumerate(info['thumbnails'][:10]):
                    if 'url' in thumb:
                        img_data = requests.get(thumb['url']).content
                        await update.message.reply_photo(img_data)

                # Download audio
                ydl_opts_audio = {'format': 'ba[ext=m4a]', 'outtmpl': os.path.join(tmpdir, 'audio.m4a'), 'quiet': True}
                with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl:
                    ydl.download([text])
                await update.message.reply_audio(open(os.path.join(tmpdir, 'audio.m4a'), 'rb'), title=info.get('title', 'Audio'))
                await msg.edit_text("🎉 Done! Slideshow images + MP3 sent")
                return

            # Normal video flow
            ydl_opts = {
                'outtmpl': os.path.join(tmpdir, '%(id)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'format': 'bv[height<=1080]+ba/b',
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(text, download=True)
                video_path = ydl.prepare_filename(info)

            if video_path.endswith('.webm'):
                mp4_path = video_path.replace('.webm', '.mp4')
                os.rename(video_path, mp4_path)
                video_path = mp4_path

            await msg.edit_text("📤 Sending video...")
            await update.message.reply_video(
                open(video_path, 'rb'),
                caption=f"🎬 {info.get('title', 'TikTok Video')}",
                supports_streaming=True
            )

            mp3_path = video_path.replace('.mp4', '.mp3')
            try:
                subprocess.run([
                    'ffmpeg', '-i', video_path, '-vn',
                    '-acodec', 'libmp3lame', '-ab', '128k', mp3_path
                ], check=True, capture_output=True)
                await msg.edit_text("🎵 Sending MP3...")
                await update.message.reply_audio(open(mp3_path, 'rb'), title=info.get('title', 'Audio'))
            except Exception as e:
                logger.warning(f"MP3 extraction failed: {e}")
                await update.message.reply_audio(open(video_path, 'rb'), title=info.get('title', 'Audio (from video)'))

        await msg.edit_text("🎉 Done! Video + MP3 sent ✅")

    except Exception as e:
        await msg.edit_text(f"❌ Failed: {str(e)[:80]}")

if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_tiktok))
    app.run_polling()

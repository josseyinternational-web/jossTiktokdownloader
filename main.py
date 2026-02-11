import os
import logging
import tempfile
import yt_dlp
import subprocess
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

    msg = await update.message.reply_text("⏳ Downloading video...")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Step 1: Download video (with embedded audio)
            ydl_opts = {
                'outtmpl': os.path.join(tmpdir, '%(id)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'format': 'bv[height<=1080]+ba/b',  # best video + audio
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(text, download=True)
                video_path = ydl.prepare_filename(info)

            # Fix .webm → .mp4
            if video_path.endswith('.webm'):
                mp4_path = video_path.replace('.webm', '.mp4')
                os.rename(video_path, mp4_path)
                video_path = mp4_path

            # Step 2: Send video first
            await msg.edit_text("📤 Sending video...")
            await update.message.reply_video(
                open(video_path, 'rb'),
                caption=f"🎬 {info.get('title', 'TikTok Video')}",
                supports_streaming=True
            )

            # Step 3: Extract MP3 using ffmpeg (Railway has it)
            mp3_path = video_path.replace('.mp4', '.mp3')
            try:
                subprocess.run([
                    'ffmpeg',
                    '-i', video_path,
                    '-vn',                 # no video
                    '-acodec', 'libmp3lame',
                    '-ab', '128k',
                    mp3_path
                ], check=True, capture_output=True)
                await msg.edit_text("🎵 Sending MP3...")
                await update.message.reply_audio(
                    open(mp3_path, 'rb'),
                    title=info.get('title', 'Audio')
                )
            except Exception as e:
                logger.warning(f"MP3 extraction failed: {e}")
                await msg.edit_text("⚠️ MP3 extraction failed (using video audio instead)")
                # Fallback: send same file as audio (Telegram accepts it)
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

import os
import logging
import tempfile
import yt_dlp
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise RuntimeError("❌ Missing TELEGRAM_TOKEN")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "👋 Yo, I'm *Joss*! 🎵\n\n"
        "📥 You want to download TikTok videos — *unlimited*, no watermark?\n"
        "👉 Just drop the link — I’ll give you the **HD video + MP3** instantly! 🚀",
        parse_mode='Markdown'
    )

def handle_tiktok(update: Update, context: CallbackContext):
    text = update.message.text.strip()
    if "tiktok.com" not in text:
        return update.message.reply_text("⚠️ Please send a valid TikTok link")

    msg = update.message.reply_text("⏳ Downloading... (This may take 20-40 seconds)")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            ydl_opts = {
                'outtmpl': os.path.join(tmpdir, '%(id)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'noplaylist': True,
                'socket_timeout': 45,
                'format': 'bv[height<=1080]+ba/b[height<=1080]',  # Best video up to 1080p + audio
                'progress_hooks': [lambda d: (
                    msg.edit_text(f"⏳ Downloading...\n{d.get('_percent_str', '0%')} • {d.get('_speed_str', '—')}")
                    if d['status'] == 'downloading' else None
                )]
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(text, download=True)
                file_path = ydl.prepare_filename(info)

            # Fix .webm → .mp4
            if file_path.endswith('.webm'):
                new_path = file_path.replace('.webm', '.mp4')
                os.rename(file_path, new_path)
                file_path = new_path

            msg.edit_text("📤 Uploading video...")
            update.message.reply_video(
                open(file_path, 'rb'),
                caption=f"🎬 {info.get('title', 'TikTok Video')}",
                supports_streaming=True
            )

            # Send MP3
            msg.edit_text("🎵 Extracting audio...")
            ydl_opts_mp3 = {
                'format': 'ba[ext=m4a]',
                'outtmpl': os.path.join(tmpdir, '%(id)s.mp3'),
                'quiet': True,
                'no_warnings': True
            }
            with yt_dlp.YoutubeDL(ydl_opts_mp3) as ydl:
                ydl.download([text])
                mp3_path = os.path.join(tmpdir, f"{info['id']}.mp3")

            update.message.reply_audio(
                open(mp3_path, 'rb'),
                title=info.get('title', 'Audio')
            )

        msg.edit_text("🎉 Done! Video + MP3 sent ✅")

    except Exception as e:
        msg.edit_text(f"❌ Failed: {str(e)[:80]}")

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_tiktok))
    logger.info("✅ Joss TikTok Bot ready")
    updater.start_polling(drop_pending_updates=True)
    updater.idle()

if __name__ == '__main__':
    main()
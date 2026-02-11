import os
import logging
import tempfile
import yt_dlp
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
        "📥 Drop a TikTok link — I'll send HD video + MP3 instantly! 🚀",
        parse_mode='Markdown'
    )

async def handle_tiktok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if "tiktok.com" not in text:
        return await update.message.reply_text("⚠️ Send TikTok link")

    msg = await update.message.reply_text("⏳ Downloading...")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            ydl_opts = {
                'outtmpl': os.path.join(tmpdir, '%(id)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'format': 'bv[height<=1080]+ba/b',
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(text, download=True)
                file_path = ydl.prepare_filename(info)

            if file_path.endswith('.webm'):
                new_path = file_path.replace('.webm', '.mp4')
                os.rename(file_path, new_path)
                file_path = new_path

            await msg.edit_text("📤 Sending video...")
            await update.message.reply_video(
                open(file_path, 'rb'),
                caption=f"🎬 {info.get('title', 'Video')}",
                supports_streaming=True
            )

            # MP3
            ydl_opts_mp3 = {
                'format': 'ba[ext=m4a]',
                'outtmpl': os.path.join(tmpdir, '%(id)s.mp3'),
                'quiet': True
            }
            with yt_dlp.YoutubeDL(ydl_opts_mp3) as ydl:
                ydl.download([text])
                mp3_path = os.path.join(tmpdir, f"{info['id']}.mp3")
            await update.message.reply_audio(open(mp3_path, 'rb'), title=info.get('title', 'Audio'))

        await msg.edit_text("🎉 Done!")

    except Exception as e:
        await msg.edit_text(f"❌ {str(e)[:80]}")

if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_tiktok))
    app.run_polling()

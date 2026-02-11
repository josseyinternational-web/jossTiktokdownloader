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
        "✅ HD video (with sound) *or*\n"
        "🖼️ Slideshow images + 🎵 MP3\n"
        "🚀 Instantly — no limits!",
        parse_mode='Markdown'
    )

async def handle_tiktok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if "tiktok.com" not in text:
        return await update.message.reply_text("⚠️ Please send a valid TikTok link")

    msg = await update.message.reply_text("⏳ Analyzing...")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Step 1: Fetch metadata
            ydl_opts_meta = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'skip_download': True
            }
            with yt_dlp.YoutubeDL(ydl_opts_meta) as ydl:
                info = ydl.extract_info(text, download=False)

            title = info.get('title', 'TikTok Post')
            duration = info.get('duration', 0)
            has_thumbnails = bool(info.get('thumbnails'))

            # Detect slideshow: short duration + thumbnails
            is_slideshow = (
                has_thumbnails and 
                (duration < 5 or duration is None) and
                len(info.get('thumbnails', [])) >= 2
            )

            if is_slideshow:
                await msg.edit_text("🖼️ Downloading slideshow images + audio...")
                
                # Download images
                image_paths = []
                for i, thumb in enumerate(info.get('thumbnails', [])[:10]):
                    if 'url' in thumb:
                        img_url = thumb['url']
                        img_path = os.path.join(tmpdir, f"slide_{i+1}.jpg")
                        try:
                            r = requests.get(img_url, timeout=10)
                            r.raise_for_status()
                            with open(img_path, 'wb') as f:
                                f.write(r.content)
                            image_paths.append(img_path)
                        except Exception as e:
                            logger.warning(f"Failed to download image {i}: {e}")

                # Download audio
                ydl_opts_audio = {
                    'format': 'ba[ext=m4a]',
                    'outtmpl': os.path.join(tmpdir, 'audio.m4a'),
                    'quiet': True,
                    'no_warnings': True
                }
                with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl:
                    ydl.download([text])
                audio_path = os.path.join(tmpdir, 'audio.m4a')

                # Send all images
                for img_path in image_paths:
                    await update.message.reply_photo(open(img_path, 'rb'))

                # Send audio
                await update.message.reply_audio(open(audio_path, 'rb'), title=title)

                await msg.edit_text(f"🎉 Done! {len(image_paths)} images + MP3 sent")

            else:
                # Normal video
                await msg.edit_text("🎥 Downloading video...")
                ydl_opts_video = {
                    'outtmpl': os.path.join(tmpdir, '%(id)s.%(ext)s'),
                    'quiet': True,
                    'no_warnings': True,
                    'format': 'bv[height<=1080]+ba/b',
                }
                with yt_dlp.YoutubeDL(ydl_opts_video) as ydl:
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
                    caption=f"🎬 {title}",
                    supports_streaming=True
                )

                # Extract MP3
                mp3_path = video_path.replace('.mp4', '.mp3')
                try:
                    subprocess.run([
                        'ffmpeg', '-i', video_path, '-vn',
                        '-acodec', 'libmp3lame', '-ab', '128k', mp3_path
                    ], check=True, capture_output=True)
                    await update.message.reply_audio(open(mp3_path, 'rb'), title=title)
                except Exception as e:
                    logger.warning(f"MP3 extraction failed: {e}")
                    await update.message.reply_audio(open(video_path, 'rb'), title=f"{title} (audio)")

                await msg.edit_text("🎉 Done! Video + MP3 sent")

    except Exception as e:
        await msg.edit_text(f"❌ Failed: {str(e)[:80]}")

if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_tiktok))
    app.run_polling()

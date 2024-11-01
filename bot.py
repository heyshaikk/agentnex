# Install required libraries
# Make sure to run this command separately in your terminal first:
# pip install python-telegram-bot yt-dlp instaloader nest_asyncio

# Import required libraries
import nest_asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp
import instaloader
import os

# Allow nested event loops
nest_asyncio.apply()

# Your bot token from BotFather
API_TOKEN = '8106206035:AAFuxH835P0tPzLcXIuBq7Yvl5GxRYdCgag'

# Function to send welcome message
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Hi! 👋 Send me an Instagram or YouTube link, and I'll download the video for you."
    )

# Function to handle incoming links
async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    url = update.message.text
    await update.message.reply_text("Processing... Please wait.")

    if "instagram.com" in url:
        await download_instagram_video(update, url)
    elif "youtube.com" in url or "youtu.be" in url:
        await download_youtube_video(update, url)
    else:
        await update.message.reply_text("⚠️ Please send a valid Instagram or YouTube link.")

# Function to download Instagram videos using Instaloader
async def download_instagram_video(update: Update, url: str) -> None:
    loader = instaloader.Instaloader(save_metadata=False, download_video_thumbnails=False)

    try:
        shortcode = url.split("/")[-2]
        post = instaloader.Post.from_shortcode(loader.context, shortcode)
        file_path = f"{shortcode}.mp4"
        loader.download_post(post, target=file_path)

        # Sending the video back to the user
        with open(file_path, 'rb') as video:
            await update.message.reply_video(video=video)

        os.remove(file_path)  # Clean up the file afterward
    except Exception as e:
        await update.message.reply_text("Failed to download Instagram video. Please ensure the link is public.")
        print(e)

# Function to download YouTube videos using yt-dlp
async def download_youtube_video(update: Update, url: str) -> None:
    ydl_opts = {
        'format': 'best',
        'outtmpl': 'youtube_video.%(ext)s',
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

            # Sending the video back to the user
            with open(file_path, 'rb') as video:
                await update.message.reply_video(video=video)

            os.remove(file_path)  # Clean up the file afterward
    except Exception as e:
        await update.message.reply_text("Failed to download YouTube video. Please check the link.")
        print(e)

# Main function to run the bot
async def run_bot() -> None:
    application = ApplicationBuilder().token(API_TOKEN).build()

    # Add command and message handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))

    # Start the bot
    await application.run_polling()

# Run the bot in the event loop
if __name__ == "__main__":
    import asyncio
    asyncio.run(run_bot())

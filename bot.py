import nest_asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp
import instaloader
import os
import logging
from datetime import datetime
import re
import asyncio
from typing import Optional

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class VideoDownloaderBot:
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.download_path = "downloads"
        self.ensure_download_directory()

    def ensure_download_directory(self) -> None:
        """Create downloads directory if it doesn't exist"""
        if not os.path.exists(self.download_path):
            os.makedirs(self.download_path)

    def get_unique_filename(self, prefix: str, ext: str) -> str:
        """Generate a unique filename"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join(self.download_path, f"{prefix}_{timestamp}.{ext}")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /start command"""
        await update.message.reply_text(
            "👋 Welcome! Send me a YouTube or Instagram link to download the video."
        )

    def extract_url(self, text: str) -> Optional[str]:
        """Extract URL from text"""
        if "youtube.com" in text or "youtu.be" in text:
            return text.strip()
        elif "instagram.com" in text:
            return text.strip()
        return None

    async def download_instagram_video(self, update: Update, url: str) -> None:
        """Download Instagram video"""
        try:
            # First reply to show processing
            processing_message = await update.message.reply_text("⏳ Processing Instagram video...")
            
            # Configure Instaloader
            L = instaloader.Instaloader(
                download_videos=True,
                download_video_thumbnails=False,
                download_geotags=False,
                download_comments=False,
                save_metadata=False,
                compress_json=False
            )

            # Extract post shortcode from URL
            match = re.search(r'instagram\.com/(?:p|reel)/([^/?]+)', url)
            if not match:
                await processing_message.edit_text("❌ Invalid Instagram URL")
                return

            shortcode = match.group(1)
            file_path = self.get_unique_filename('instagram', 'mp4')
            
            # Download the post
            try:
                await processing_message.edit_text("⏳ Downloading video...")
                post = instaloader.Post.from_shortcode(L.context, shortcode)
                
                # Check if post contains video
                if not post.is_video:
                    await processing_message.edit_text("⚠️ This post does not contain a video.")
                    return
                
                # Download the video
                L.download_post(post, target=os.path.splitext(file_path)[0])
                
                # Find the downloaded video file
                downloaded_files = [f for f in os.listdir(self.download_path) if f.endswith('.mp4')]
                if not downloaded_files:
                    raise Exception("Video file not found after download")
                
                video_path = os.path.join(self.download_path, downloaded_files[0])
                
                # Send the video
                await processing_message.edit_text("📤 Uploading to Telegram...")
                with open(video_path, 'rb') as video:
                    await update.message.reply_video(
                        video=video,
                        caption="📥 Downloaded from Instagram"
                    )
                await processing_message.delete()
                
            finally:
                # Cleanup
                for file in os.listdir(self.download_path):
                    try:
                        os.remove(os.path.join(self.download_path, file))
                    except Exception as e:
                        logger.error(f"Error cleaning up file {file}: {e}")
                        
        except instaloader.exceptions.InstaloaderException as e:
            logger.error(f"Instaloader error: {e}")
            await processing_message.edit_text(f"❌ Error: {str(e)}")
        except Exception as e:
            logger.error(f"Error downloading Instagram video: {e}")
            await processing_message.edit_text("❌ Failed to process Instagram video")

    async def download_youtube_video(self, update: Update, url: str) -> None:
        """Download YouTube video"""
        try:
            # First reply to show processing
            processing_message = await update.message.reply_text("⏳ Processing YouTube video...")
            
            file_path = self.get_unique_filename('youtube', 'mp4')
            
            ydl_opts = {
                'format': 'best[filesize<50M]',  # Limit to 50MB for Telegram
                'outtmpl': file_path,
                'noplaylist': True,
                'logger': logger,
                'progress_hooks': [],
            }
            
            try:
                await processing_message.edit_text("⏳ Downloading video...")
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    video_title = info.get('title', 'video')
                
                # Check if file exists and is not empty
                if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                    raise Exception("Video file not downloaded correctly")
                
                # Send the video
                await processing_message.edit_text("📤 Uploading to Telegram...")
                with open(file_path, 'rb') as video:
                    await update.message.reply_video(
                        video=video,
                        caption=f"📥 {video_title}",
                    )
                await processing_message.delete()
                
            finally:
                # Cleanup
                if os.path.exists(file_path):
                    os.remove(file_path)
                    
        except Exception as e:
            logger.error(f"Error downloading YouTube video: {e}")
            await processing_message.edit_text(
                f"❌ Failed to download video: {str(e) if 'error' in str(e).lower() else 'Video might be too large or unavailable'}"
            )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming messages"""
        url = self.extract_url(update.message.text)
        if not url:
            await update.message.reply_text("⚠️ Please send a valid YouTube or Instagram video link")
            return

        try:
            if "instagram.com" in url:
                await self.download_instagram_video(update, url)
            elif "youtube.com" in url or "youtu.be" in url:
                await self.download_youtube_video(update, url)
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await update.message.reply_text("❌ An error occurred while processing your request")

    async def run(self) -> None:
        """Start the bot"""
        # Allow nested event loops
        nest_asyncio.apply()
        
        application = ApplicationBuilder().token(self.api_token).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Start the bot
        logger.info("Bot is running...")
        await application.run_polling(allowed_updates=Update.ALL_TYPES)

# Main execution
if __name__ == "__main__":
    API_TOKEN = '8106206035:AAFuxH835P0tPzLcXIuBq7Yvl5GxRYdCgag'  # Your bot token
    bot = VideoDownloaderBot(API_TOKEN)
    
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")

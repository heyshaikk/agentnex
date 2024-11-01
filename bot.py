import nest_asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp
import instaloader
import os
import asyncio
import re
from typing import Optional
from datetime import datetime

# Allow nested event loops
nest_asyncio.apply()

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
        """Generate a unique filename based on timestamp"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join(self.download_path, f"{prefix}_{timestamp}.{ext}")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /start command"""
        welcome_message = (
            "👋 Welcome to Video Downloader Bot!\n\n"
            "I can help you download videos from:\n"
            "▫️ Instagram\n"
            "▫️ YouTube\n\n"
            "Just send me a link, and I'll do the rest!\n\n"
            "📝 Commands:\n"
            "/start - Show this message\n"
            "/help - Show help information"
        )
        await update.message.reply_text(welcome_message)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /help command"""
        help_message = (
            "ℹ️ How to use this bot:\n\n"
            "1. For YouTube videos:\n"
            "   - Send any YouTube video link\n"
            "   - Supports both full URLs and short URLs\n\n"
            "2. For Instagram videos:\n"
            "   - Send any public Instagram post link\n"
            "   - Only public posts are supported\n\n"
            "⚠️ Note: Large videos may take longer to process"
        )
        await update.message.reply_text(help_message)

    def extract_url(self, text: str) -> Optional[str]:
        """Extract URL from text using regex"""
        url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+'
        urls = re.findall(url_pattern, text)
        return urls[0] if urls else None

    async def handle_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming messages containing links"""
        url = self.extract_url(update.message.text)
        if not url:
            await update.message.reply_text("⚠️ Please send a valid video link.")
            return

        status_message = await update.message.reply_text("⏳ Processing your request...")
        
        try:
            if "instagram.com" in url:
                await self.download_instagram_video(update, url, status_message)
            elif "youtube.com" in url or "youtu.be" in url:
                await self.download_youtube_video(update, url, status_message)
            else:
                await status_message.edit_text("⚠️ Unsupported platform. Please send a YouTube or Instagram link.")
        except Exception as e:
            await status_message.edit_text(f"❌ Error: {str(e)}")
            print(f"Error processing {url}: {str(e)}")

    async def download_instagram_video(self, update: Update, url: str, status_message) -> None:
        """Download and send Instagram videos"""
        try:
            await status_message.edit_text("⏳ Downloading Instagram video...")
            loader = instaloader.Instaloader(
                save_metadata=False,
                download_video_thumbnails=False,
                download_geotags=False,
                download_comments=False
            )
            
            shortcode = url.split("/p/")[1].split("/")[0]
            post = instaloader.Post.from_shortcode(loader.context, shortcode)
            
            if not post.is_video:
                await status_message.edit_text("⚠️ This Instagram post doesn't contain a video.")
                return

            file_path = self.get_unique_filename("instagram", "mp4")
            loader.download_post(post, target=os.path.splitext(file_path)[0])
            
            await status_message.edit_text("📤 Uploading video...")
            with open(file_path, 'rb') as video:
                await update.message.reply_video(
                    video=video,
                    caption="🎥 Downloaded using @VideoDownloaderBot"
                )
            await status_message.delete()
            
        except instaloader.exceptions.InvalidArgumentException:
            await status_message.edit_text("⚠️ Invalid Instagram link.")
        except instaloader.exceptions.PrivateProfileNotFollowedException:
            await status_message.edit_text("⚠️ This post is from a private account.")
        except Exception as e:
            await status_message.edit_text("❌ Failed to download Instagram video.")
            print(f"Instagram download error: {str(e)}")
        finally:
            if 'file_path' in locals() and os.path.exists(file_path):
                os.remove(file_path)

    async def download_youtube_video(self, update: Update, url: str, status_message) -> None:
        """Download and send YouTube videos"""
        file_path = self.get_unique_filename("youtube", "mp4")
        
        ydl_opts = {
            'format': 'best[filesize<50M]',  # Limit filesize for Telegram
            'outtmpl': file_path,
            'noplaylist': True,
            'quiet': True,
        }
        
        try:
            await status_message.edit_text("⏳ Downloading YouTube video...")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get('title', 'video')
                
                await status_message.edit_text("📤 Uploading video...")
                with open(file_path, 'rb') as video:
                    await update.message.reply_video(
                        video=video,
                        caption=f"🎥 {title}\nDownloaded using @VideoDownloaderBot"
                    )
                await status_message.delete()
                
        except yt_dlp.utils.DownloadError as e:
            if "File is larger than max-filesize" in str(e):
                await status_message.edit_text("⚠️ Video is too large. Please try a shorter video.")
            else:
                await status_message.edit_text("❌ Failed to download YouTube video. Please check the link.")
        except Exception as e:
            await status_message.edit_text("❌ An error occurred while processing the video.")
            print(f"YouTube download error: {str(e)}")
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

    async def run(self) -> None:
        """Start the bot"""
        application = ApplicationBuilder().token(self.api_token).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_link))
        
        # Start the bot
        print("Bot is running...")
        await application.run_polling()

# Main execution
if __name__ == "__main__":
    API_TOKEN = '8106206035:AAFuxH835P0tPzLcXIuBq7Yvl5GxRYdCgag'  # Replace with your actual token
    bot = VideoDownloaderBot(API_TOKEN)
    asyncio.run(bot.run())

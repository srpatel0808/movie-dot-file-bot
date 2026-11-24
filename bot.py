"""
Telegram Thumbnail & Watermark Bot - Main Application.
Features:
- Automatic thumbnail watermarking with 100% original quality preservation
- Video Thumbnail Changer: extract, replace, watermark, and send back MP4 videos with ZERO re-encoding
- Registered Telegram Command Menu (/start, /help, /thumbnail, /watermark, /settings, /cancel)
- Interactive Admin Panel with 9-position placement, scale, opacity, live preview, and broadcast
- Multi-upload support for photos, uncompressed documents, and videos
"""

import io
import os
import sys
import shutil
import tempfile
import logging
from pathlib import Path
from typing import Optional

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
    BotCommand,
    BotCommandScopeDefault
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

from config import (
    BOT_TOKEN,
    ADMIN_IDS,
    SUPPORTED_EXTENSIONS,
    MAX_FILE_SIZE_MB,
    DEFAULT_SETTINGS
)
from database import db
from watermark_engine import watermark_engine
from video_engine import video_engine
import admin

# Clean logging setup
logging.basicConfig(
    format="%(asctime)s - [%(levelname)s] - %(name)s: %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("WatermarkBot")


# ==================== STARTUP & COMMAND REGISTRATION ====================

async def post_init(application: Application):
    """Registers bot commands with Telegram's Bot API so they appear in the / menu."""
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Show instructions"),
        BotCommand("thumbnail", "Upload or change thumbnail"),
        BotCommand("watermark", "Apply custom watermark (Admin only)"),
        BotCommand("settings", "Bot settings"),
        BotCommand("cancel", "Cancel current operation")
    ]
    try:
        await application.bot.set_my_commands(commands, scope=BotCommandScopeDefault())
        logger.info("Bot commands successfully registered with Telegram Bot API.")
    except Exception as e:
        logger.error(f"Failed to register bot commands: {e}", exc_info=True)


# ==================== COMMAND HANDLERS ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command."""
    user = update.effective_user
    db.register_or_update_user(user.id, user.username, user.first_name)

    is_user_admin = admin.is_admin(user.id)

    keyboard = [
        [
            InlineKeyboardButton("📸 Upload Thumbnail", callback_data="user_cmd_thumbnail"),
            InlineKeyboardButton("🎬 Video Changer", callback_data="user_cmd_video_info")
        ],
        [
            InlineKeyboardButton("ℹ️ How to Use", callback_data="user_help"),
            InlineKeyboardButton("👁️ Watermark Preview", callback_data="user_preview")
        ]
    ]
    if is_user_admin:
        keyboard.append([InlineKeyboardButton("🛠️ Admin Control Panel", callback_data="adm_main")])

    welcome_text = (
        f"👋 *Welcome, {user.first_name}!* 🎯\n\n"
        "I am your automated **Telegram Thumbnail & Watermark Bot**.\n\n"
        "✨ *Core Capabilities:*\n"
        " • 📸 *Image Watermarking:* Send any image/thumbnail to instantly apply your brand watermark.\n"
        " • 🎬 *Video Thumbnail Changer:* Send any MP4 video to extract, replace, or watermark its thumbnail with **zero video re-encoding**.\n"
        " • 💎 *Original Quality:* 100% video and image resolution preserved.\n"
        " • 📁 *Multi-Upload:* Send single files or albums without quality degradation.\n\n"
        "👉 *Ready?* Simply send an **image** or **video** to get started!"
    )

    await update.message.reply_text(
        welcome_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /help command."""
    user = update.effective_user
    db.register_or_update_user(user.id, user.username, user.first_name)

    help_text = (
        "📖 *THUMBNAIL WATERMARK BOT - USER GUIDE*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📸 *1. Watermarking Image Thumbnails:*\n"
        " • Send your image directly as a **Photo** or as a **Document / File**.\n"
        " • *Pro Tip:* Sending as **File (Uncompressed)** keeps 100% of the original HD/4K resolution.\n"
        " • The bot automatically applies your watermark and sends it back.\n\n"
        "🎬 *2. Changing Video Thumbnails:*\n"
        " • Send an **MP4 video** (up to 20MB).\n"
        " • The bot extracts the current thumbnail and presents action buttons:\n"
        "   - *Watermark Existing Thumbnail*: Applies watermark to the video's current thumbnail.\n"
        "   - *Upload New Thumbnail*: Upload any custom image to become the new thumbnail.\n"
        "   - *Use Saved Thumbnail*: Apply your profile's saved custom thumbnail.\n"
        " • Original video streams are copied directly (**no re-encoding**, zero quality loss).\n\n"
        "📂 *3. Stored Custom Thumbnail:* Use `/thumbnail` to save a custom image you can reuse anytime.\n\n"
        "⚙️ *4. Commands Menu:*\n"
        " • `/start` - Start or restart the bot\n"
        " • `/help` - View this help manual\n"
        " • `/thumbnail` - Upload or change custom thumbnail\n"
        " • `/watermark` - View or manage watermark (Admin)\n"
        " • `/settings` - Bot preferences and admin controls\n"
        " • `/cancel` - Cancel active operation\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )

    keyboard = [
        [
            InlineKeyboardButton("📸 Set Thumbnail", callback_data="user_cmd_thumbnail"),
            InlineKeyboardButton("👁️ Preview Watermark", callback_data="user_preview")
        ]
    ]
    if admin.is_admin(user.id):
        keyboard.append([InlineKeyboardButton("🛠️ Admin Panel", callback_data="adm_main")])

    await update.message.reply_text(
        help_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def thumbnail_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /thumbnail command (upload, view, or change user custom thumbnail)."""
    user = update.effective_user
    db.register_or_update_user(user.id, user.username, user.first_name)

    stored_thumb = db.get_user_thumbnail(user.id)

    if stored_thumb:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Upload New Thumbnail", callback_data="user_set_new_thumb")],
            [InlineKeyboardButton("❌ Remove Saved Thumbnail", callback_data="user_del_thumb")],
            [InlineKeyboardButton("👁️ Preview Watermark", callback_data="user_preview")]
        ])
        caption = (
            "🖼️ *Your Active Saved Thumbnail*\n\n"
            "This thumbnail is saved to your profile and can be automatically applied to your videos with one click!"
        )
        await update.message.reply_photo(
            photo=stored_thumb,
            caption=caption,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    else:
        db.set_user_state(user.id, "waiting_for_user_thumbnail")
        cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="user_cancel")]])
        await update.message.reply_text(
            "📸 *Upload Custom Thumbnail*\n\n"
            "Please send your **thumbnail image** now (Photo or Document).\n\n"
            "Once saved, you can attach it to any video or apply your watermark automatically!",
            reply_markup=cancel_kb,
            parse_mode="Markdown"
        )

async def preview_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /preview command."""
    status_msg = await update.message.reply_text("⏳ Generating watermark preview...")
    try:
        preview_bytes = watermark_engine.generate_preview_thumbnail()
        settings = db.get_all_settings()
        pos = settings.get("position", DEFAULT_SETTINGS["position"]).replace("_", " ").title()
        scale = settings.get("scale", DEFAULT_SETTINGS["scale"])
        opacity = settings.get("opacity", DEFAULT_SETTINGS["opacity"])

        caption = (
            "👁️ *Current Watermark Placement Preview (1280x720 Canvas)*\n"
            f"• Position: *{pos}*\n"
            f"• Scale: *{scale}%*\n"
            f"• Opacity: *{opacity}%*\n\n"
            "Send any image or video to apply this watermark!"
        )
        await update.message.reply_photo(photo=preview_bytes, caption=caption, parse_mode="Markdown")
        await status_msg.delete()
    except Exception as e:
        await status_msg.edit_text(f"❌ Could not generate preview: {e}")

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels any pending input or operation."""
    user = update.effective_user
    db.set_user_state(user.id, None)
    db.clear_pending_video(user.id)
    await update.message.reply_text("✅ Active operation cancelled. Send an image or video anytime!")


# ==================== VIDEO THUMBNAIL CHANGER ====================

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles uploaded videos.
    Extracts existing thumbnail, checks size limits, and displays options for custom thumbnail replacement.
    """
    user = update.effective_user
    db.register_or_update_user(user.id, user.username, user.first_name)

    # Determine message object (video directly or sent as document)
    msg = update.message
    video = msg.video
    doc = msg.document

    if not video and doc:
        # User sent video as document
        mime = (doc.mime_type or "").lower()
        ext = Path(doc.file_name or "").suffix.lower()
        if not mime.startswith("video/") and ext not in [".mp4", ".mkv", ".mov", ".webm"]:
            return  # Handled by document handler
        # Treat as video
        file_id = doc.file_id
        file_name = doc.file_name or "video.mp4"
        file_size = doc.file_size or 0
        width = 0
        height = 0
        duration = 0
        tg_thumb_obj = doc.thumbnail
    else:
        file_id = video.file_id
        file_name = video.file_name or "video.mp4"
        file_size = video.file_size or 0
        width = video.width
        height = video.height
        duration = video.duration
        tg_thumb_obj = video.thumbnail

    # Check file size against Telegram Bot API 20MB download limit
    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    if file_size > max_bytes:
        size_mb = file_size / (1024 * 1024)
        await msg.reply_text(
            f"⚠️ *Video File Too Large*\n\n"
            f"The Telegram Bot API limits bot file downloads to **{MAX_FILE_SIZE_MB}MB**.\n"
            f"Your uploaded video is **{size_mb:.1f}MB**.\n\n"
            "💡 *Solution:* Please compress or trim your video to under 20MB so the bot can download and process its thumbnail.",
            parse_mode="Markdown"
        )
        return

    status_msg = await msg.reply_text("🎬 *Analyzing video and extracting thumbnail...*", parse_mode="Markdown")

    extracted_thumb_bytes = None
    try:
        # Extract thumbnail from Telegram thumbnail if available
        if tg_thumb_obj:
            thumb_file = await tg_thumb_obj.get_file()
            extracted_thumb_bytes = bytes(await thumb_file.download_as_bytearray())

        # If no Telegram thumbnail, extract using video_engine
        if not extracted_thumb_bytes:
            # Download small segment / full video to extract frame
            vid_file = await context.bot.get_file(file_id)
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_vid:
                tmp_vid_path = Path(tmp_vid.name)
            await vid_file.download_to_drive(custom_path=tmp_vid_path)
            extracted_thumb_bytes = video_engine.extract_thumbnail_from_video(tmp_vid_path, timestamp=1.0)
            tmp_vid_path.unlink(missing_ok=True)

        # Store pending video in database
        db.set_pending_video(
            user_id=user.id,
            file_id=file_id,
            file_name=file_name,
            width=width,
            height=height,
            duration=duration,
            file_size=file_size,
            extracted_thumb=extracted_thumb_bytes
        )

        has_stored_thumb = db.has_user_thumbnail(user.id)
        keyboard = []

        if has_stored_thumb:
            keyboard.append([InlineKeyboardButton("✨ Apply My Saved Thumbnail (Watermarked)", callback_data="vid_apply_stored")])

        if extracted_thumb_bytes:
            keyboard.append([InlineKeyboardButton("🏷️ Watermark Current Thumbnail & Update", callback_data="vid_watermark_current")])

        keyboard.append([InlineKeyboardButton("📤 Upload New Custom Thumbnail", callback_data="vid_upload_new")])
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="user_cancel")])

        info_caption = (
            "🎬 *Video Received & Thumbnail Extracted!*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📁 *File:* `{file_name}`\n"
            f"📐 *Resolution:* `{width} x {height}` px\n"
            f"⏱️ *Duration:* `{duration}`s\n"
            f"📦 *Size:* `{file_size / (1024*1024):.1f} MB`\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Choose an action below to update this video's thumbnail:"
        )

        if extracted_thumb_bytes:
            await msg.reply_photo(
                photo=extracted_thumb_bytes,
                caption=info_caption,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        else:
            await msg.reply_text(
                info_caption,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )

        await status_msg.delete()

    except Exception as e:
        logger.error(f"Error handling video: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ *Error processing video:*\n`{str(e)}`", parse_mode="Markdown")

async def process_and_send_video(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    user_id: int,
    raw_thumbnail_bytes: bytes,
    original_message = None
):
    """
    Applies watermark to the thumbnail, attaches it to the MP4 video using stream-copy (no re-encoding),
    and sends the updated video and high-resolution thumbnail back to the user.
    """
    pending = db.get_pending_video(user_id)
    if not pending:
        await context.bot.send_message(chat_id=chat_id, text="⚠️ No pending video found. Please upload your video again.")
        return

    status_msg = await context.bot.send_message(
        chat_id=chat_id,
        text="⚡ *Applying watermark and replacing video thumbnail without re-encoding...*",
        parse_mode="Markdown"
    )

    temp_dir = Path(tempfile.mkdtemp(prefix="tg_video_"))
    try:
        # 1. Apply watermark to the chosen thumbnail
        watermarked_bytes, out_fmt, thumb_dims = watermark_engine.apply_watermark(raw_thumbnail_bytes)

        # 2. Download original video
        input_vid_path = temp_dir / "input_video.mp4"
        file_obj = await context.bot.get_file(pending["file_id"])
        await file_obj.download_to_drive(custom_path=input_vid_path)

        # 3. Save watermarked thumbnail to disk
        thumb_path = temp_dir / f"watermarked_thumb.{out_fmt.lower()}"
        thumb_path.write_bytes(watermarked_bytes)

        # 4. Replace thumbnail inside MP4 container without re-encoding
        output_vid_path = temp_dir / f"{Path(pending['file_name'] or 'video').stem}_watermarked.mp4"
        success = video_engine.replace_video_thumbnail(input_vid_path, thumb_path, output_vid_path)

        if not success or not output_vid_path.exists():
            # Fallback to input video if container replacement failed
            output_vid_path = input_vid_path

        # 5. Create Telegram-optimized preview thumbnail (JPEG, <200KB, <=320px)
        tg_preview_thumb = video_engine.create_telegram_thumbnail_preview(watermarked_bytes)

        # 6. Send updated video back
        video_caption = (
            "✅ *Video Thumbnail Successfully Updated!*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💎 *100% Original Video Quality Preserved* (Zero re-encoding)\n"
            f"📐 *Resolution:* `{pending['width']} x {pending['height']}` px\n"
            f"⏱️ *Duration:* `{pending['duration']}`s\n"
            "🏷️ Custom watermark applied."
        )

        with open(output_vid_path, "rb") as vid_fh:
            await context.bot.send_video(
                chat_id=chat_id,
                video=vid_fh,
                thumbnail=tg_preview_thumb,
                caption=video_caption,
                supports_streaming=True,
                width=pending["width"] if pending["width"] > 0 else None,
                height=pending["height"] if pending["height"] > 0 else None,
                duration=pending["duration"] if pending["duration"] > 0 else None,
                parse_mode="Markdown"
            )

        # 7. Also deliver the standalone high-res watermarked thumbnail document
        doc_name = f"{Path(pending['file_name'] or 'thumbnail').stem}_watermarked_thumb.{out_fmt.lower()}"
        doc_file = InputFile(io.BytesIO(watermarked_bytes), filename=doc_name)
        await context.bot.send_document(
            chat_id=chat_id,
            document=doc_file,
            caption="🖼️ *Standalone Watermarked Thumbnail* (Full HD file for YouTube / Web)",
            parse_mode="Markdown"
        )

        # Update stats and cleanup
        db.increment_processed(user_id)
        db.clear_pending_video(user_id)
        db.set_user_state(user_id, None)

        await status_msg.delete()

    except Exception as e:
        logger.error(f"Error in process_and_send_video: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ *Failed to update video thumbnail:*\n`{str(e)}`", parse_mode="Markdown")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ==================== IMAGE PROCESSING HANDLERS ====================

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes incoming photo messages."""
    user = update.effective_user
    db.register_or_update_user(user.id, user.username, user.first_name)
    user_state = db.get_user_state(user.id)

    # 1. Admin uploading new default watermark
    if admin.is_admin(user.id) and user_state == "waiting_for_watermark":
        await save_watermark_from_message(update, context, is_document=False)
        return

    # 2. User uploading image specifically for a pending video
    if user_state == "waiting_for_video_thumbnail":
        photo = update.message.photo[-1]
        file_obj = await photo.get_file()
        raw_bytes = await file_obj.download_as_bytearray()
        await process_and_send_video(context, update.effective_chat.id, user.id, bytes(raw_bytes))
        return

    # 3. User uploading custom thumbnail via /thumbnail command
    if user_state == "waiting_for_user_thumbnail":
        photo = update.message.photo[-1]
        file_obj = await photo.get_file()
        raw_bytes = await file_obj.download_as_bytearray()
        db.set_user_thumbnail(user.id, bytes(raw_bytes))
        db.set_user_state(user.id, None)

        # If user also had a pending video, ask if they want to apply it now!
        pending = db.get_pending_video(user.id)
        if pending:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🎬 Apply to My Pending Video", callback_data="vid_apply_stored")],
                [InlineKeyboardButton("✅ Just Keep as Saved Thumbnail", callback_data="user_cancel")]
            ])
            await update.message.reply_photo(
                photo=bytes(raw_bytes),
                caption="✅ *Custom Thumbnail Saved!*\nWould you like to attach this to your uploaded video now?",
                reply_markup=kb,
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_photo(
                photo=bytes(raw_bytes),
                caption="✅ *Custom Thumbnail Saved to Your Profile!*\nWhenever you send an MP4 video, you can apply this thumbnail instantly.",
                parse_mode="Markdown"
            )
        return

    # 4. Standard thumbnail watermarking
    status_msg = await update.message.reply_text("⚡ *Applying watermark to your thumbnail...*", parse_mode="Markdown")

    try:
        photo = update.message.photo[-1]
        file_obj = await photo.get_file()
        file_bytes = await file_obj.download_as_bytearray()

        output_bytes, out_fmt, dims = watermark_engine.apply_watermark(bytes(file_bytes))
        db.increment_processed(user.id)

        settings = db.get_all_settings()
        output_mode = settings.get("output_mode", DEFAULT_SETTINGS["output_mode"])

        filename = f"watermarked_thumbnail_{dims[0]}x{dims[1]}.{out_fmt.lower()}"
        caption = (
            "✅ *Watermark Applied Successfully!*\n"
            f"📐 *Resolution:* `{dims[0]} x {dims[1]}` px\n"
            "⚡ Original quality preserved."
        )

        if output_mode in ["photo", "both"]:
            await update.message.reply_photo(
                photo=output_bytes,
                caption=caption if output_mode == "photo" else None,
                parse_mode="Markdown"
            )

        if output_mode in ["document", "both"]:
            doc_file = InputFile(io.BytesIO(output_bytes), filename=filename)
            await update.message.reply_document(
                document=doc_file,
                caption=caption,
                parse_mode="Markdown"
            )

        await status_msg.delete()

    except Exception as e:
        logger.error(f"Error processing photo: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ *Error watermarking image:*\n`{str(e)}`", parse_mode="Markdown")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes uncompressed image files and video documents."""
    user = update.effective_user
    db.register_or_update_user(user.id, user.username, user.first_name)
    user_state = db.get_user_state(user.id)

    doc = update.message.document
    mime = (doc.mime_type or "").lower()
    ext = Path(doc.file_name or "").suffix.lower()

    # Route video sent as document to handle_video
    if mime.startswith("video/") or ext in [".mp4", ".mkv", ".mov", ".webm"]:
        await handle_video(update, context)
        return

    # Validate image document
    is_image = ext in SUPPORTED_EXTENSIONS or mime.startswith("image/")
    if not is_image:
        await update.message.reply_text(
            "⚠️ *Unsupported File Type*\n"
            f"Please send an image (`{', '.join(sorted(SUPPORTED_EXTENSIONS))}`) or an MP4 video.",
            parse_mode="Markdown"
        )
        return

    # Check file size
    if doc.file_size and doc.file_size > (MAX_FILE_SIZE_MB * 1024 * 1024):
        await update.message.reply_text(
            f"⚠️ *File too large!* Maximum allowed size is {MAX_FILE_SIZE_MB}MB.",
            parse_mode="Markdown"
        )
        return

    # 1. Admin uploading new watermark
    if admin.is_admin(user.id) and user_state == "waiting_for_watermark":
        await save_watermark_from_message(update, context, is_document=True)
        return

    # 2. User uploading image specifically for a pending video
    if user_state == "waiting_for_video_thumbnail":
        file_obj = await doc.get_file()
        raw_bytes = await file_obj.download_as_bytearray()
        await process_and_send_video(context, update.effective_chat.id, user.id, bytes(raw_bytes))
        return

    # 3. User uploading custom thumbnail via /thumbnail
    if user_state == "waiting_for_user_thumbnail":
        file_obj = await doc.get_file()
        raw_bytes = await file_obj.download_as_bytearray()
        db.set_user_thumbnail(user.id, bytes(raw_bytes))
        db.set_user_state(user.id, None)

        pending = db.get_pending_video(user.id)
        if pending:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🎬 Apply to My Pending Video", callback_data="vid_apply_stored")],
                [InlineKeyboardButton("✅ Just Keep as Saved Thumbnail", callback_data="user_cancel")]
            ])
            await update.message.reply_photo(
                photo=bytes(raw_bytes),
                caption="✅ *Custom Thumbnail Saved!*\nWould you like to attach this to your uploaded video now?",
                reply_markup=kb,
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                "✅ *Custom Thumbnail Saved to Your Profile!*\nWhenever you send an MP4 video, you can apply this thumbnail instantly.",
                parse_mode="Markdown"
            )
        return

    # 4. Standard uncompressed thumbnail watermarking
    status_msg = await update.message.reply_text("⚡ *Processing uncompressed thumbnail...*", parse_mode="Markdown")

    try:
        file_obj = await doc.get_file()
        file_bytes = await file_obj.download_as_bytearray()

        output_bytes, out_fmt, dims = watermark_engine.apply_watermark(bytes(file_bytes))
        db.increment_processed(user.id)

        settings = db.get_all_settings()
        output_mode = settings.get("output_mode", DEFAULT_SETTINGS["output_mode"])

        orig_stem = Path(doc.file_name or "thumbnail").stem
        out_filename = f"{orig_stem}_watermarked.{out_fmt.lower()}"

        caption = (
            "✅ *Watermark Applied (Uncompressed HD)!*\n"
            f"📐 *Resolution:* `{dims[0]} x {dims[1]}` px\n"
            "💎 100% original quality preserved without compression."
        )

        if output_mode == "both":
            await update.message.reply_photo(photo=output_bytes)

        doc_file = InputFile(io.BytesIO(output_bytes), filename=out_filename)
        await update.message.reply_document(
            document=doc_file,
            caption=caption,
            parse_mode="Markdown"
        )

        await status_msg.delete()

    except Exception as e:
        logger.error(f"Error processing document: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ *Error watermarking document:*\n`{str(e)}`", parse_mode="Markdown")

async def save_watermark_from_message(update: Update, context: ContextTypes.DEFAULT_TYPE, is_document: bool):
    """Saves user-uploaded image as the new exact watermark (Admin only)."""
    user = update.effective_user
    status_msg = await update.message.reply_text("⏳ *Saving your exact watermark image...*", parse_mode="Markdown")

    try:
        if is_document:
            file_obj = await update.message.document.get_file()
        else:
            file_obj = await update.message.photo[-1].get_file()

        raw_bytes = await file_obj.download_as_bytearray()
        result = watermark_engine.save_new_watermark(bytes(raw_bytes))

        db.set_user_state(user.id, None)

        if result.get("success"):
            w = result.get("width")
            h = result.get("height")
            text = (
                "🎉 *New Default Watermark Successfully Saved!*\n\n"
                f"• Dimensions: `{w} x {h}` px\n"
                "• Exact custom watermark preserved.\n"
                "• All subsequent thumbnails and videos will automatically use this watermark!"
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("👁️ Preview Placement", callback_data="adm_preview")],
                [InlineKeyboardButton("🛠️ Back to Admin Panel", callback_data="adm_main")]
            ])
            await status_msg.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        else:
            await status_msg.edit_text(f"❌ Failed to save watermark: {result.get('error')}")

    except Exception as e:
        logger.error(f"Error saving watermark: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Failed to process watermark: {e}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles text messages and admin broadcast inputs."""
    user = update.effective_user
    text = update.message.text.strip()
    user_state = db.get_user_state(user.id)

    # Admin broadcast state
    if admin.is_admin(user.id) and user_state == "waiting_for_broadcast":
        db.set_user_state(user.id, None)
        status_msg = await update.message.reply_text("📢 *Broadcasting announcement to all users...*", parse_mode="Markdown")

        user_ids = db.get_all_user_ids()
        success = 0
        failed = 0

        for target_id in user_ids:
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=f"📢 *ANNOUNCEMENT*\n━━━━━━━━━━━━━━━━━━━━━━\n{text}",
                    parse_mode="Markdown"
                )
                success += 1
            except Exception:
                failed += 1

        await status_msg.edit_text(
            f"✅ *Broadcast Finished!*\n\n"
            f"• Successfully sent: `{success}`\n"
            f"• Failed/Blocked: `{failed}`\n"
            f"• Total registered: `{len(user_ids)}`",
            parse_mode="Markdown"
        )
        return

    # Regular conversational guidance
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📸 Upload Thumbnail", callback_data="user_cmd_thumbnail")],
        [InlineKeyboardButton("ℹ️ Help Manual", callback_data="user_help")]
    ])
    await update.message.reply_text(
        "👋 Please send an **image** or an **MP4 video** to apply or replace thumbnails!\n\n"
        "You can send photos, files, or videos up to 20MB.",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

async def handle_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Routes callback queries between admin actions, video actions, and general user actions."""
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id

    # Route admin callbacks
    if data.startswith("adm_") or data.startswith("set_"):
        await admin.handle_admin_callback(update, context)
        return

    await query.answer()

    # Video Action: Apply stored thumbnail
    if data == "vid_apply_stored":
        stored_thumb = db.get_user_thumbnail(user_id)
        if not stored_thumb:
            await query.message.reply_text("⚠️ No saved thumbnail found. Please use /thumbnail to set one.")
            return
        await process_and_send_video(context, query.message.chat_id, user_id, stored_thumb, original_message=query.message)

    # Video Action: Watermark current extracted thumbnail
    elif data == "vid_watermark_current":
        pending = db.get_pending_video(user_id)
        if not pending or not pending.get("extracted_thumb"):
            await query.message.reply_text("⚠️ Could not locate video thumbnail. Please upload an image.")
            return
        await process_and_send_video(context, query.message.chat_id, user_id, pending["extracted_thumb"], original_message=query.message)

    # Video Action: Upload new custom thumbnail for this video
    elif data == "vid_upload_new":
        db.set_user_state(user_id, "waiting_for_video_thumbnail")
        cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="user_cancel")]])
        await query.message.reply_text(
            "📸 *Send New Thumbnail Image*\n\n"
            "Please send the image you want to attach as this video's new thumbnail.\n"
            "Your brand watermark will be automatically applied to it!",
            reply_markup=cancel_kb,
            parse_mode="Markdown"
        )

    # User Command: Thumbnail flow
    elif data == "user_cmd_thumbnail":
        db.set_user_state(user_id, "waiting_for_user_thumbnail")
        cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="user_cancel")]])
        await query.message.reply_text(
            "📸 *Set Custom Thumbnail*\n\n"
            "Please send your **thumbnail image** now (Photo or Document).\n"
            "Once saved, it can be attached to any video or watermarked directly!",
            reply_markup=cancel_kb,
            parse_mode="Markdown"
        )

    elif data == "user_set_new_thumb":
        db.set_user_state(user_id, "waiting_for_user_thumbnail")
        cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="user_cancel")]])
        await query.message.reply_text(
            "📸 Please send the new image to replace your stored thumbnail.",
            reply_markup=cancel_kb,
            parse_mode="Markdown"
        )

    elif data == "user_del_thumb":
        db.clear_user_thumbnail(user_id)
        await query.message.reply_text("✅ Saved thumbnail removed from your profile.")

    elif data == "user_cmd_video_info":
        await query.message.reply_text(
            "🎬 *Video Thumbnail Changer*\n\n"
            "Simply send any **MP4 video** (up to 20MB) to the bot.\n"
            "The bot will extract the current thumbnail and let you:\n"
            "1. Watermark the existing thumbnail\n"
            "2. Replace it with your own custom thumbnail\n"
            "All done with **zero video re-encoding**!",
            parse_mode="Markdown"
        )

    elif data == "user_help":
        help_text = (
            "📖 *QUICK HELP GUIDE*\n\n"
            "1. **Watermark an Image:** Send any photo or document.\n"
            "2. **Change Video Thumbnail:** Send an MP4 video (under 20MB).\n"
            "3. **Store a Thumbnail:** Use `/thumbnail` to save a custom thumbnail for later.\n"
            "4. Tap `/` to see all commands in Telegram's menu!"
        )
        await query.message.reply_text(help_text, parse_mode="Markdown")

    elif data == "user_preview":
        try:
            preview_bytes = watermark_engine.generate_preview_thumbnail()
            await query.message.reply_photo(
                photo=preview_bytes,
                caption="👁️ *Current Watermark Placement Preview on 1280x720 Canvas*",
                parse_mode="Markdown"
            )
        except Exception as e:
            await query.message.reply_text(f"❌ Preview unavailable: {e}")

    elif data == "user_cancel":
        db.set_user_state(user_id, None)
        db.clear_pending_video(user_id)
        await query.message.reply_text("✅ Action cancelled.")


# ==================== GLOBAL ERROR HANDLER ====================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Global error handler for all unhandled exceptions."""
    logger.error("Exception while handling update:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ *An error occurred while processing your request.*\n"
                "Please try again or contact the administrator.",
                parse_mode="Markdown"
            )
        except Exception:
            pass


# ==================== APPLICATION BUILDER ====================

def build_application() -> Application:
    """Builds and configures the telegram bot application."""
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("\n" + "=" * 60)
        print("⚠️ ERROR: BOT_TOKEN is not set in your .env file!")
        print("=" * 60 + "\n")

    app = (
        Application.builder()
        .token(BOT_TOKEN or "DUMMY_TOKEN")
        .post_init(post_init)
        .build()
    )

    # Commands registered in menu
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("thumbnail", thumbnail_command))
    app.add_handler(CommandHandler("watermark", admin.handle_watermark_command))
    app.add_handler(CommandHandler("settings", admin.handle_settings_command))
    app.add_handler(CommandHandler("cancel", cancel_command))

    # Additional command aliases
    app.add_handler(CommandHandler("admin", admin.handle_admin_command))
    app.add_handler(CommandHandler("preview", preview_command))

    # Media handlers
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VIDEO, handle_video))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # Text messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Callback Query Router
    app.add_handler(CallbackQueryHandler(handle_callback_router))

    # Error Handler
    app.add_error_handler(error_handler)

    return app

def main():
    """Runs the bot in polling mode with automatic reconnects."""
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("Cannot start bot without BOT_TOKEN in .env. Exiting.")
        sys.exit(1)

    print("🚀 Starting Telegram Thumbnail & Watermark Bot...")
    app = build_application()
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

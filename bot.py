"""
MOVIE DOT — Dedicated Telegram Movie File Management & Delivery Bot.
Features:
- Automatic Movie Indexing from channel uploads or admin forwards (MKV, MP4)
- Automatic Quality Detection (480p, 720p, 1080p, 2160p / 4K)
- Single-Button 'GET ALL FILES' Deep Linking System
- Mandatory Channel Subscription Verification (Force Join) with instant resume
- Instant zero-bandwidth delivery using stored Telegram file_id values
- Prevention of duplicate file entries
- Multi-user concurrent async processing
"""

import logging
from pathlib import Path
from typing import Optional

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
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
    BOT_USERNAME
)
from database import db
import movie_engine
import admin

# Clean logging setup
logging.basicConfig(
    format="%(asctime)s - [%(levelname)s] - %(name)s: %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("MovieDot")


# ==================== STARTUP & COMMAND REGISTRATION ====================

async def post_init(application: Application):
    """Registers official Movie Dot bot commands with Telegram's Bot API."""
    commands = [
        BotCommand("start", "Start the bot / access movie files"),
        BotCommand("help", "How to use Movie Dot"),
        BotCommand("movies", "View all indexed movies (Admin)"),
        BotCommand("setchannel", "Set force-join subscription channel (Admin)"),
        BotCommand("admin", "Admin Control Panel (Admin)"),
        BotCommand("cancel", "Cancel active operation")
    ]
    try:
        await application.bot.set_my_commands(commands, scope=BotCommandScopeDefault())
        logger.info("Movie Dot commands registered with Telegram Bot API.")
    except Exception as e:
        logger.error(f"Failed to register bot commands: {e}", exc_info=True)


# ==================== HOME SCREEN & COMMAND HANDLERS ====================

def get_home_markup(user_id: int) -> InlineKeyboardMarkup:
    """Builds the clean MOVIE DOT home menu, displaying admin options only to the bot owner."""
    keyboard = []
    if admin.is_admin(user_id):
        keyboard.append([InlineKeyboardButton("🎬 Manage Movies", callback_data="adm_movies")])

    keyboard.append([InlineKeyboardButton("📥 GET ALL FILES", callback_data="user_get_all_files")])
    keyboard.append([InlineKeyboardButton("ℹ️ How to Use", callback_data="user_help")])

    return InlineKeyboardMarkup(keyboard)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command (including Telegram Deep Linking for movies)."""
    user = update.effective_user
    db.register_or_update_user(user.id, user.username, user.first_name)

    # 1. Telegram Deep Linking (/start get_<movie_id> or /start <movie_id>)
    if context.args and len(context.args) > 0:
        param = context.args[0].strip()
        await handle_movie_request(update, context, param, user)
        return

    # 2. Clean MOVIE DOT Home Screen
    welcome_text = (
        "🎬 *Welcome to MOVIE DOT!*\n\n"
        "Your Movie File Management Bot."
    )

    await update.message.reply_text(
        welcome_text,
        reply_markup=get_home_markup(user.id),
        parse_mode="Markdown"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /help command."""
    user = update.effective_user
    db.register_or_update_user(user.id, user.username, user.first_name)

    help_text = (
        "📖 *MOVIE DOT — USER GUIDE*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎬 *How to Download Movie Files:*\n"
        " 1. Browse movie posts in our official Telegram channel.\n"
        " 2. Tap the **📥 GET ALL FILES** button on any movie post.\n"
        " 3. If prompted, join our channel and click **✅ I'VE JOINED – VERIFY**.\n"
        " 4. Select your preferred resolution (**480p**, **720p**, **1080p**, or **4K**).\n"
        " 5. The movie file is delivered instantly directly to your chat!\n\n"
        "⚙️ *Bot Commands:*\n"
        " • `/start` – Open main menu or access movie link\n"
        " • `/help` – View this user guide\n"
        " • `/movies` – Manage movie collection (Admin)\n"
        " • `/setchannel` – Set force-join channel (Admin)\n"
        " • `/admin` – Open Admin Control Panel (Admin)\n"
        " • `/cancel` – Cancel active operation\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 GET ALL FILES", callback_data="user_get_all_files")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="user_home")]
    ])

    await update.message.reply_text(help_text, reply_markup=kb, parse_mode="Markdown")


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels any pending admin input."""
    user = update.effective_user
    db.set_user_state(user.id, None)
    await update.message.reply_text("✅ Active operation cancelled. Use /start to return home.")


# ==================== FORCE JOIN & MOVIE DELIVERY ====================

async def handle_movie_request(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    param: str,
    user
):
    """
    Handles movie access via Deep Linking.
    Enforces mandatory channel subscription before delivering files.
    """
    clean_id = param
    for prefix in ["get_", "movie_", "files_", "dl_"]:
        if clean_id.lower().startswith(prefix):
            clean_id = clean_id[len(prefix):]
            break

    movie = db.get_movie(clean_id)
    if not movie and clean_id != param:
        movie = db.get_movie(param)
    if not movie:
        movie = db.find_movie_by_title_or_year(clean_id.replace("_", " "))

    if not movie:
        logger.warning(f"Deep link requested unknown movie param: '{param}' (cleaned: '{clean_id}')")
        force_chan = db.get_force_sub_channel()
        keyboard = []
        if force_chan:
            chan_url = f"https://t.me/{force_chan.lstrip('@')}" if not force_chan.startswith("-100") else None
            if chan_url:
                keyboard.append([InlineKeyboardButton("📢 Visit Channel", url=chan_url)])
        keyboard.append([InlineKeyboardButton("🏠 Main Menu", callback_data="user_home")])

        await update.message.reply_text(
            "⚠️ *Movie Not Found*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Sorry, the requested movie files could not be found or have been removed.\n\n"
            "Please check the latest post in our channel or contact the administrator.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    # Check if movie has files
    files = db.get_movie_files(movie["movie_id"])
    if not files:
        keyboard = [[InlineKeyboardButton("🏠 Main Menu", callback_data="user_home")]]
        await update.message.reply_text(
            f"🎬 *{movie['title']}*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ *Files Currently Unavailable*\n\n"
            "No download files are currently attached to this movie.\n"
            "Please check back shortly!",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    # MANDATORY CHANNEL SUBSCRIPTION CHECK (FORCE JOIN)
    # Bot owners/admins bypass verification
    if not admin.is_admin(user.id):
        force_chan = db.get_force_sub_channel()
        if force_chan:
            is_member, status_reason, channel_url = await movie_engine.check_channel_membership(
                bot=context.bot,
                user_id=user.id,
                channel=force_chan
            )
            if not is_member:
                logger.info(f"User {user.id} denied access to {movie['movie_id']}: not in channel {force_chan} (status={status_reason})")
                force_text, force_markup = movie_engine.format_force_sub_message(channel_url, movie["movie_id"])
                await update.message.reply_text(
                    force_text,
                    reply_markup=force_markup,
                    parse_mode="Markdown"
                )
                return

    # User is subscribed (or admin): show available movie qualities
    await show_movie_qualities_screen(update.message, movie, files)


async def show_movie_qualities_screen(message, movie: dict, files: list, is_edit: bool = False):
    """
    Renders the movie quality selection screen.
    Only shows qualities that actually exist in the database.
    """
    qualities_bullet_list = "\n".join([f"- {f['quality']}" for f in files])

    caption = (
        f"🎬 *{movie['title']}*\n\n"
        f"📥 *Select Your Quality:*\n\n"
        f"{qualities_bullet_list}"
    )

    keyboard = movie_engine.format_quality_selection_keyboard(movie["movie_id"], files)

    if is_edit:
        try:
            await message.edit_text(caption, reply_markup=keyboard, parse_mode="Markdown")
            return
        except Exception:
            pass

    if movie.get("poster_file_id"):
        try:
            await message.reply_photo(
                photo=movie["poster_file_id"],
                caption=caption,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            return
        except Exception as e:
            logger.warning(f"Could not send poster: {e}")

    await message.reply_text(caption, reply_markup=keyboard, parse_mode="Markdown")


async def send_movie_file(query, context: ContextTypes.DEFAULT_TYPE, movie_id: str, quality: str):
    """Sends a single movie file using stored Telegram file_id without downloading or re-uploading."""
    user = query.from_user

    # Re-verify channel subscription before file delivery (in case user left)
    if not admin.is_admin(user.id):
        force_chan = db.get_force_sub_channel()
        if force_chan:
            is_member, _, channel_url = await movie_engine.check_channel_membership(
                bot=context.bot,
                user_id=user.id,
                channel=force_chan
            )
            if not is_member:
                await query.answer("⚠️ Subscription required!", show_alert=True)
                force_text, force_markup = movie_engine.format_force_sub_message(channel_url, movie_id)
                await query.message.reply_text(force_text, reply_markup=force_markup, parse_mode="Markdown")
                return

    await query.answer(f"Sending {quality}...")

    movie = db.get_movie(movie_id)
    movie_title = movie["title"] if movie else "Movie"

    file_record = db.get_movie_file_by_quality(movie_id, quality)
    if not file_record:
        await query.message.reply_text(
            f"⚠️ *File Unavailable*\nThe {quality} version is no longer in the database.",
            parse_mode="Markdown"
        )
        return

    file_id = file_record["file_id"]
    file_name = file_record.get("file_name", "movie.mp4")
    file_size_str = movie_engine.format_size(file_record.get("file_size", 0))

    caption = (
        f"🎬 *{movie_title}* — *{quality}*\n"
        f"📁 `{file_name}`\n"
        f"📦 Size: *{file_size_str}*\n\n"
        "⚡ Delivered instantly via MOVIE DOT."
    )

    chat_id = query.message.chat_id
    is_mkv = file_name.lower().endswith(".mkv")

    try:
        if file_record.get("is_video") and not is_mkv:
            await context.bot.send_video(
                chat_id=chat_id,
                video=file_id,
                caption=caption,
                supports_streaming=True,
                parse_mode="Markdown"
            )
        else:
            await context.bot.send_document(
                chat_id=chat_id,
                document=file_id,
                caption=caption,
                parse_mode="Markdown"
            )
        db.increment_delivered(user.id)
    except Exception as e:
        logger.warning(f"Error sending as video/doc, attempting document fallback: {e}")
        try:
            await context.bot.send_document(
                chat_id=chat_id,
                document=file_id,
                caption=caption,
                parse_mode="Markdown"
            )
            db.increment_delivered(user.id)
        except Exception as e2:
            logger.error(f"Failed to send movie file {file_id}: {e2}", exc_info=True)
            await query.message.reply_text(
                "⚠️ *Error Sending File*\n"
                "Telegram could not deliver this file. It may have been deleted on the server.",
                parse_mode="Markdown"
            )


async def send_all_movie_files(query, context: ContextTypes.DEFAULT_TYPE, movie_id: str):
    """Sends all available file qualities for a movie to the user."""
    user = query.from_user

    # Re-verify channel subscription
    if not admin.is_admin(user.id):
        force_chan = db.get_force_sub_channel()
        if force_chan:
            is_member, _, channel_url = await movie_engine.check_channel_membership(
                bot=context.bot,
                user_id=user.id,
                channel=force_chan
            )
            if not is_member:
                await query.answer("⚠️ Subscription required!", show_alert=True)
                force_text, force_markup = movie_engine.format_force_sub_message(channel_url, movie_id)
                await query.message.reply_text(force_text, reply_markup=force_markup, parse_mode="Markdown")
                return

    movie = db.get_movie(movie_id)
    movie_title = movie["title"] if movie else "Movie"
    files = db.get_movie_files(movie_id)

    if not files:
        await query.answer("No files found.", show_alert=True)
        return

    await query.answer(f"Sending all {len(files)} qualities...")
    status_msg = await query.message.reply_text(
        f"⏳ *Sending all {len(files)} versions of {movie_title}...*",
        parse_mode="Markdown"
    )

    sent = 0
    for f in files:
        try:
            caption = (
                f"🎬 *{movie_title}* — *{f['quality']}*\n"
                f"📁 `{f.get('file_name', 'movie')}`\n"
                f"📦 Size: *{movie_engine.format_size(f.get('file_size', 0))}*"
            )
            is_mkv = f.get("file_name", "").lower().endswith(".mkv")
            if f.get("is_video") and not is_mkv:
                await context.bot.send_video(
                    chat_id=query.message.chat_id,
                    video=f["file_id"],
                    caption=caption,
                    supports_streaming=True,
                    parse_mode="Markdown"
                )
            else:
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=f["file_id"],
                    caption=caption,
                    parse_mode="Markdown"
                )
            sent += 1
            db.increment_delivered(user.id)
        except Exception as e:
            logger.error(f"Failed sending quality {f['quality']}: {e}")

    await status_msg.edit_text(
        f"✅ *All Files Delivered!* Sent `{sent}` of `{len(files)}` versions of *{movie_title}*.",
        parse_mode="Markdown"
    )


# ==================== AUTOMATIC CHANNEL & MEDIA INDEXING ====================

async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Listens to posts in Telegram channels where the bot is an administrator.
    Automatically indexes video files (MKV, MP4), detects quality, associates with movie_id,
    and attaches the inline button '📥 GET ALL FILES' pointing to the bot deep link.
    """
    msg = update.channel_post
    if not msg:
        return

    bot_username = BOT_USERNAME
    if not bot_username:
        try:
            bot_user = await context.bot.get_me()
            bot_username = bot_user.username or ""
        except Exception as e:
            logger.warning(f"Could not retrieve bot username: {e}")
            bot_username = "bot"

    video = msg.video
    doc = msg.document
    caption = msg.caption or ""

    if video:
        file_id = video.file_id
        file_unique_id = video.file_unique_id
        file_name = video.file_name or "video.mp4"
        file_size = video.file_size or 0
        mime_type = video.mime_type or "video/mp4"
        width = video.width or 0
        height = video.height or 0
        is_video = True
    elif doc:
        mime = (doc.mime_type or "").lower()
        ext = Path(doc.file_name or "").suffix.lower()
        if not (mime.startswith("video/") or ext in [".mkv", ".mp4", ".mov", ".avi", ".webm"]):
            return
        file_id = doc.file_id
        file_unique_id = doc.file_unique_id
        file_name = doc.file_name or "movie.mkv"
        file_size = doc.file_size or 0
        mime_type = doc.mime_type or "video/x-matroska"
        width = doc.thumbnail.width if doc.thumbnail else 0
        height = doc.thumbnail.height if doc.thumbnail else 0
        is_video = False
    elif msg.photo:
        if caption:
            info = movie_engine.parse_movie_info(filename="", caption=caption)
            if info and info.get("year"):
                photo_file_id = msg.photo[-1].file_id
                db.add_or_update_movie(
                    movie_id=info["movie_id"],
                    title=info["clean_title"],
                    year=info["year"],
                    poster_file_id=photo_file_id,
                    channel_id=msg.chat.id,
                    channel_message_id=msg.message_id
                )
                deep_link = movie_engine.generate_deep_link(info["movie_id"], bot_username)
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("📥 GET ALL FILES", url=deep_link)]])
                try:
                    await context.bot.edit_message_reply_markup(
                        chat_id=msg.chat.id,
                        message_id=msg.message_id,
                        reply_markup=kb
                    )
                except Exception as e:
                    logger.debug(f"Could not edit photo channel post markup: {e}")
        return
    else:
        return

    quality = movie_engine.detect_quality(filename=file_name, caption=caption, width=width, height=height)
    info = movie_engine.parse_movie_info(filename=file_name, caption=caption)
    movie_id = info["movie_id"]
    clean_title = info["clean_title"]
    year = info.get("year")

    db.add_or_update_movie(
        movie_id=movie_id,
        title=clean_title,
        year=year,
        channel_id=msg.chat.id,
        channel_message_id=msg.message_id
    )

    res = db.add_movie_file(
        movie_id=movie_id,
        file_id=file_id,
        file_unique_id=file_unique_id,
        file_name=file_name,
        file_size=file_size,
        quality=quality,
        mime_type=mime_type,
        is_video=is_video
    )

    logger.info(f"Indexed movie from channel: '{clean_title}' | Quality: {quality} | Action: {res['action']}")

    deep_link = movie_engine.generate_deep_link(movie_id, bot_username)
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 GET ALL FILES", url=deep_link)]
    ])

    try:
        await context.bot.edit_message_reply_markup(
            chat_id=msg.chat.id,
            message_id=msg.message_id,
            reply_markup=reply_markup
        )
        logger.info(f"Attached '📥 GET ALL FILES' button to channel post {msg.message_id}")
    except Exception as e:
        logger.debug(f"Could not edit channel message reply markup: {e}")


async def handle_video_or_doc_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles video and document uploads sent directly to the bot in private chat.
    If sent by an Admin, automatically indexes the movie file into the database.
    """
    user = update.effective_user
    db.register_or_update_user(user.id, user.username, user.first_name)
    msg = update.message

    # Regular users sending files
    if not admin.is_admin(user.id):
        await msg.reply_text(
            "👋 *Welcome to MOVIE DOT!*\n\n"
            "To access movies, please tap the **📥 GET ALL FILES** button on any movie post in our channel.",
            reply_markup=get_home_markup(user.id),
            parse_mode="Markdown"
        )
        return

    # Admin uploaded a file: index it into movie database
    video = msg.video
    doc = msg.document
    caption = msg.caption or ""

    if video:
        file_id = video.file_id
        file_unique_id = video.file_unique_id
        file_name = video.file_name or "video.mp4"
        file_size = video.file_size or 0
        mime_type = video.mime_type or "video/mp4"
        is_video = True
    elif doc:
        mime = (doc.mime_type or "").lower()
        ext = Path(doc.file_name or "").suffix.lower()
        if not (mime.startswith("video/") or ext in [".mkv", ".mp4", ".mov", ".avi", ".webm"]):
            await msg.reply_text("⚠️ Please send an **MKV** or **MP4** video file.", parse_mode="Markdown")
            return
        file_id = doc.file_id
        file_unique_id = doc.file_unique_id
        file_name = doc.file_name or "movie.mkv"
        file_size = doc.file_size or 0
        mime_type = doc.mime_type or "video/x-matroska"
        is_video = False
    else:
        return

    info = movie_engine.parse_movie_info(filename=file_name, caption=caption)
    movie_id = info["movie_id"]
    clean_title = info["clean_title"]
    year = info.get("year")
    quality = info["quality"]

    db.add_or_update_movie(movie_id=movie_id, title=clean_title, year=year)
    res = db.add_movie_file(
        movie_id=movie_id,
        file_id=file_id,
        file_unique_id=file_unique_id,
        file_name=file_name,
        file_size=file_size,
        quality=quality,
        mime_type=mime_type,
        is_video=is_video
    )

    bot_user = await context.bot.get_me()
    bot_username = bot_user.username or BOT_USERNAME or "bot"
    deep_link = movie_engine.generate_deep_link(movie_id, bot_username)

    all_files = db.get_movie_files(movie_id)
    qualities_text = "\n".join([f" • *{f['quality']}* ({movie_engine.format_size(f.get('file_size', 0))})" for f in all_files])
    force_chan = db.get_force_sub_channel()

    text = (
        f"🎬 *Movie File Indexed Successfully!*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 *Movie:* *{clean_title}*\n"
        f"🏷️ *Quality Detected:* *{quality}*\n"
        f"📁 *Filename:* `{file_name}`\n"
        f"📦 *File Size:* `{movie_engine.format_size(file_size)}`\n"
        f"⚙️ *Action:* `{res['action']}`\n\n"
        f"🔗 *Deep Link:*\n`{deep_link}`\n\n"
        f"📥 *All Linked Qualities ({len(all_files)}):*\n"
        f"{qualities_text}\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )

    buttons = [
        [InlineKeyboardButton("📥 Test GET ALL FILES", callback_data=f"preview_movie:{movie_id}")]
    ]
    if force_chan:
        buttons.append([InlineKeyboardButton("📢 Post to Channel", callback_data=f"adm_post_chan:{movie_id}")])
    buttons.append([InlineKeyboardButton("🎬 Manage All Movies", callback_data="adm_movies")])

    await msg.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )


# ==================== TEXT & CALLBACK ROUTING ====================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles text messages and admin state inputs."""
    user = update.effective_user
    text = update.message.text.strip()
    user_state = db.get_user_state(user.id)

    # 1. Admin configuring force-sub channel
    if admin.is_admin(user.id) and user_state == "waiting_for_force_channel":
        db.set_user_state(user.id, None)
        if text.lower() in ["off", "disable", "none", "remove"]:
            db.set_force_sub_channel("")
            await update.message.reply_text("✅ Force Join has been **disabled**.", parse_mode="Markdown")
            return

        db.set_force_sub_channel(text)
        await update.message.reply_text(
            f"✅ *Force-Join Channel Saved!*\n\n"
            f"• Target Channel: `{text}`\n"
            f"• All users must subscribe to this channel before downloading movie files.",
            parse_mode="Markdown"
        )
        return

    # 2. Admin broadcasting
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
            f"• Sent: `{success}`\n"
            f"• Failed/Blocked: `{failed}`\n"
            f"• Total users: `{len(user_ids)}`",
            parse_mode="Markdown"
        )
        return

    # Regular conversational guidance
    await update.message.reply_text(
        "🎬 *Welcome to MOVIE DOT!*\n\n"
        "To get movie files, browse our Telegram channel and click **📥 GET ALL FILES** on any movie post.",
        reply_markup=get_home_markup(user.id),
        parse_mode="Markdown"
    )


async def handle_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Routes callback queries between admin actions and movie delivery."""
    query = update.callback_query
    data = query.data
    user = update.effective_user

    # Route admin panel callbacks
    if data.startswith("adm_"):
        await admin.handle_admin_callback(update, context)
        return

    # Force Join Verification Callback
    if data.startswith("verify_sub:"):
        movie_id = data.split(":", 1)[1]
        force_chan = db.get_force_sub_channel()

        # Check membership with Bot API
        is_member, status_reason, channel_url = await movie_engine.check_channel_membership(
            bot=context.bot,
            user_id=user.id,
            channel=force_chan
        )

        if not is_member:
            await query.answer(
                "❌ Verification failed! You haven't joined our channel yet. Please join and click Verify again.",
                show_alert=True
            )
            return

        # Verification succeeded! Show confirmation toast
        await query.answer("✅ Verification successful! Loading available qualities...")

        # Continue the requested movie immediately!
        movie = db.get_movie(movie_id)
        if not movie:
            await query.message.reply_text("⚠️ Movie not found.")
            return

        files = db.get_movie_files(movie_id)
        if not files:
            await query.message.reply_text("⚠️ No files attached to this movie.")
            return

        # Render quality selection screen
        await show_movie_qualities_screen(query.message, movie, files, is_edit=True)
        return

    await query.answer()

    # Deliver specific movie quality
    if data.startswith("getfile:"):
        parts = data.split(":", 2)
        if len(parts) == 3:
            _, movie_id, quality = parts
            await send_movie_file(query, context, movie_id, quality)

    # Deliver all qualities
    elif data.startswith("getall:"):
        movie_id = data.split(":", 1)[1]
        await send_all_movie_files(query, context, movie_id)

    # Preview quality screen (Admin test)
    elif data.startswith("preview_movie:"):
        movie_id = data.split(":", 1)[1]
        movie = db.get_movie(movie_id)
        if movie:
            files = db.get_movie_files(movie_id)
            if files:
                await show_movie_qualities_screen(query.message, movie, files, is_edit=False)
            else:
                await query.message.reply_text("⚠️ No files attached yet.")

    # Home Menu
    elif data == "user_home":
        welcome_text = (
            "🎬 *Welcome to MOVIE DOT!*\n\n"
            "Your Movie File Management Bot."
        )
        await query.message.reply_text(welcome_text, reply_markup=get_home_markup(user.id), parse_mode="Markdown")

    # User clicked GET ALL FILES from home menu
    elif data == "user_get_all_files":
        force_chan = db.get_force_sub_channel()
        chan_url = f"https://t.me/{force_chan.lstrip('@')}" if force_chan and not force_chan.startswith("-100") else "https://t.me/"
        text = (
            "📥 *HOW TO GET MOVIE FILES*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Every movie post in our Telegram channel has an **📥 GET ALL FILES** button.\n\n"
            "1. Visit our channel.\n"
            "2. Find any movie you want.\n"
            "3. Click **📥 GET ALL FILES** on the post.\n"
            "4. MOVIE DOT will open and show all available qualities (**480p**, **720p**, **1080p**, **4K**)!\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Open Movie Channel", url=chan_url)],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="user_home")]
        ])
        await query.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

    # Help from home menu
    elif data == "user_help":
        help_text = (
            "📖 *MOVIE DOT — USER GUIDE*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎬 *How to Download Movie Files:*\n"
            " 1. Browse movie posts in our Telegram channel.\n"
            " 2. Tap the **📥 GET ALL FILES** button on any movie post.\n"
            " 3. If prompted, join our channel and click **✅ I'VE JOINED – VERIFY**.\n"
            " 4. Select your preferred resolution (**480p**, **720p**, **1080p**, or **4K**).\n"
            " 5. The movie file is delivered instantly directly to your chat!\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📥 GET ALL FILES", callback_data="user_get_all_files")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="user_home")]
        ])
        await query.message.reply_text(help_text, reply_markup=kb, parse_mode="Markdown")


# ==================== GLOBAL ERROR HANDLER ====================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Global error handler for unhandled exceptions."""
    logger.error("Exception while handling update:", exc_info=context.error)


# ==================== APPLICATION BUILDER ====================

def build_application() -> Application:
    """Builds and configures the pure MOVIE DOT application."""
    if not BOT_TOKEN:
        print("⚠️ ERROR: BOT_TOKEN is not set in your .env file!")

    app = (
        Application.builder()
        .token(BOT_TOKEN or "DUMMY_TOKEN")
        .post_init(post_init)
        .build()
    )

    # Core commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cancel", cancel_command))

    # Admin commands
    app.add_handler(CommandHandler("movies", admin.handle_movies_command))
    app.add_handler(CommandHandler("setchannel", admin.handle_set_channel_command))
    app.add_handler(CommandHandler("admin", admin.handle_admin_command))

    # Channel Post Handler (indexes channel uploads and attaches GET ALL FILES button)
    app.add_handler(MessageHandler(filters.ChatType.CHANNEL, handle_channel_post))

    # Media handlers (for admin uploading/indexing movie files in PM)
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.ALL, handle_video_or_doc_message))

    # Text messages (broadcasts, channel setting, conversational guidance)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Callback Query Router
    app.add_handler(CallbackQueryHandler(handle_callback_router))

    # Error Handler
    app.add_error_handler(error_handler)

    return app


def main():
    """Runs the Movie Dot bot in polling mode with automatic reconnects."""
    if not BOT_TOKEN:
        print("Cannot start bot without BOT_TOKEN in .env. Exiting.")
        return

    print("🚀 Starting MOVIE DOT Bot...")
    app = build_application()
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

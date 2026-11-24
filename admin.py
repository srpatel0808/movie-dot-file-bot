"""
Admin Panel and Management Handlers for MOVIE DOT Bot.
Provides an interactive inline keyboard interface for managing movie files,
configuring the mandatory force-join subscription channel, broadcasting announcements,
and viewing real-time database statistics.
"""

import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import ContextTypes
from config import ADMIN_IDS, BOT_USERNAME
from database import db
import movie_engine

logger = logging.getLogger("AdminPanel")


def is_admin(user_id: int) -> bool:
    """Helper to check if a user is an authorized administrator."""
    if ADMIN_IDS:
        return user_id in ADMIN_IDS
    return False


def get_admin_dashboard_text() -> str:
    """Renders the clean MOVIE DOT admin dashboard text."""
    stats = db.get_stats()
    force_chan = stats.get("force_sub_channel") or "⚠️ None (No verification active)"

    text = (
        "🛠 *MOVIE DOT — ADMIN CONTROL PANEL*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 *Bot Performance:*\n"
        f" • Registered Users: `{stats['total_users']}`\n"
        f" • Movie Files Delivered: `{stats['total_delivered']}`\n\n"
        f"🎬 *Movie Library:*\n"
        f" • Indexed Movies: `{stats['total_movies']}`\n"
        f" • Total Qualities Stored: `{stats['total_files']}`\n"
        f" • Total Storage Indexed: `{movie_engine.format_size(stats['total_size_bytes'])}`\n\n"
        f"📢 *Force-Join Subscription Channel:*\n"
        f" • Target: `{force_chan}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Select an option below to manage movies or configure settings:"
    )
    return text


def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Returns the streamlined Movie Dot admin keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("🎬 Manage Movies & Files", callback_data="adm_movies")
        ],
        [
            InlineKeyboardButton("📢 Set Force-Sub Channel", callback_data="adm_set_channel"),
            InlineKeyboardButton("📊 System Statistics", callback_data="adm_stats")
        ],
        [
            InlineKeyboardButton("📢 Broadcast to Users", callback_data="adm_broadcast"),
            InlineKeyboardButton("❌ Close Panel", callback_data="adm_close")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


async def handle_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /admin command."""
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔ *Access Denied:* This command is restricted to bot administrators.", parse_mode="Markdown")
        return

    text = get_admin_dashboard_text()
    keyboard = get_admin_keyboard()
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")


async def handle_movies_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /movies command."""
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔ *Access Denied:* This command is restricted to administrators.", parse_mode="Markdown")
        return

    movies = db.get_all_movies(limit=30)
    bot_user = await context.bot.get_me()
    bot_username = bot_user.username or BOT_USERNAME or "bot"

    if not movies:
        text = (
            "🎬 *INDEXED MOVIES & FILES*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "ℹ️ *No movies currently in the database.*\n\n"
            "• Upload video files (**MKV** or **MP4**) directly to your channel, or\n"
            "• Send or forward movie files directly to this chat.\n\n"
            "Movie Dot automatically extracts titles and qualities (480p, 720p, 1080p, 4K)!"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="adm_main")]])
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    stats = db.get_stats()
    text = (
        "🎬 *INDEXED MOVIES & FILES*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• Total Movies: `{stats['total_movies']}`\n"
        f"• Total Qualities: `{stats['total_files']}`\n"
        f"• Storage Volume: `{movie_engine.format_size(stats['total_size_bytes'])}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Tap any movie below to view qualities, deep link, or post to channel:"
    )

    buttons = []
    for m in movies:
        f_count = m.get("file_count", 0)
        btn_title = f"🎬 {m['title']} ({f_count} ver)"
        buttons.append([InlineKeyboardButton(btn_title, callback_data=f"adm_minfo:{m['movie_id']}")])

    buttons.append([InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="adm_main")])
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")


async def handle_set_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /setchannel <channel> command."""
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔ *Access Denied.*", parse_mode="Markdown")
        return

    if not context.args:
        curr = db.get_force_sub_channel() or "None"
        await update.message.reply_text(
            f"📢 *Current Force-Join Channel:* `{curr}`\n\n"
            "Usage: `/setchannel @YourChannel` or `/setchannel -100xxxxxxxxxx`\n"
            "To disable force-join: `/setchannel off`",
            parse_mode="Markdown"
        )
        return

    new_channel = context.args[0].strip()
    if new_channel.lower() in ["off", "disable", "none", "remove"]:
        db.set_force_sub_channel("")
        await update.message.reply_text("✅ Mandatory channel subscription (Force Join) has been **disabled**.", parse_mode="Markdown")
        return

    db.set_force_sub_channel(new_channel)
    await update.message.reply_text(
        f"✅ *Force-Join Channel Updated!*\n\n"
        f"• New Target: `{new_channel}`\n"
        f"• Bot will now verify users belong to this channel before delivering movie files.\n\n"
        f"⚠️ *Important:* Ensure the bot is added as an **Administrator** in `{new_channel}`.",
        parse_mode="Markdown"
    )


async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Dispatches all admin panel actions and movie configuration callbacks."""
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await query.answer("Access Denied.", show_alert=True)
        return

    await query.answer()

    # 1. Main Dashboard
    if data == "adm_main":
        db.set_user_state(user_id, None)
        text = get_admin_dashboard_text()
        keyboard = get_admin_keyboard()
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")

    # 2. Movie List & Management
    elif data == "adm_movies":
        movies = db.get_all_movies(limit=30)
        bot_user = await context.bot.get_me()
        bot_username = bot_user.username or BOT_USERNAME or "bot"

        if not movies:
            text = (
                "🎬 *INDEXED MOVIES & FILES*\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "ℹ️ *No movies currently in the database.*\n\n"
                "• Upload video files (**MKV** or **MP4**) directly to your channel, or\n"
                "• Send or forward movie files directly to this chat.\n\n"
                "Movie Dot automatically extracts titles and qualities (480p, 720p, 1080p, 4K)!"
            )
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="adm_main")]])
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
            return

        stats = db.get_stats()
        text = (
            "🎬 *INDEXED MOVIES & FILES*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• Total Movies: `{stats['total_movies']}`\n"
            f"• Total Qualities: `{stats['total_files']}`\n"
            f"• Storage Volume: `{movie_engine.format_size(stats['total_size_bytes'])}`\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Tap any movie below to view qualities, deep link, or post to channel:"
        )

        buttons = []
        for m in movies:
            f_count = m.get("file_count", 0)
            btn_title = f"🎬 {m['title']} ({f_count} ver)"
            buttons.append([InlineKeyboardButton(btn_title, callback_data=f"adm_minfo:{m['movie_id']}")])

        buttons.append([InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="adm_main")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

    # 3. Individual Movie Details
    elif data.startswith("adm_minfo:"):
        movie_id = data.split(":", 1)[1]
        movie = db.get_movie(movie_id)
        if not movie:
            await query.answer("Movie not found.", show_alert=True)
            return

        files = db.get_movie_files(movie_id)
        bot_user = await context.bot.get_me()
        bot_username = bot_user.username or BOT_USERNAME or "bot"
        deep_link = movie_engine.generate_deep_link(movie_id, bot_username)

        file_lines = []
        for f in files:
            file_lines.append(f" • *{f['quality']}*: `{f['file_name']}` ({movie_engine.format_size(f['file_size'])})")

        files_text = "\n".join(file_lines) if file_lines else "_No files attached._"
        force_chan = db.get_force_sub_channel()

        text = (
            f"🎬 *{movie['title']}*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 *Movie ID:* `{movie['movie_id']}`\n"
            f"📅 *Year:* `{movie.get('year') or 'N/A'}`\n"
            f"🔗 *Deep Link:*\n`{deep_link}`\n\n"
            f"📁 *Available Qualities ({len(files)}):*\n"
            f"{files_text}\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )

        kb_rows = [
            [InlineKeyboardButton("📥 Test GET ALL FILES", callback_data=f"preview_movie:{movie_id}")]
        ]
        if force_chan:
            kb_rows.append([InlineKeyboardButton("📢 Post to Channel", callback_data=f"adm_post_chan:{movie_id}")])
        kb_rows.append([InlineKeyboardButton("🗑️ Delete Movie & Files", callback_data=f"adm_del_confirm:{movie_id}")])
        kb_rows.append([InlineKeyboardButton("🔙 Back to Movies List", callback_data="adm_movies")])

        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb_rows), parse_mode="Markdown")

    # 4. Confirm Movie Deletion
    elif data.startswith("adm_del_confirm:"):
        movie_id = data.split(":", 1)[1]
        movie = db.get_movie(movie_id)
        title = movie["title"] if movie else movie_id
        text = (
            f"⚠️ *Confirm Movie Deletion*\n\n"
            f"Are you sure you want to permanently delete:\n"
            f"🎬 *{title}*\n\n"
            "All linked quality files (Telegram file IDs) will be removed from the database."
        )
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🗑️ Yes, Delete", callback_data=f"adm_del_do:{movie_id}"),
                InlineKeyboardButton("❌ Cancel", callback_data=f"adm_minfo:{movie_id}")
            ]
        ])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    # 5. Execute Movie Deletion
    elif data.startswith("adm_del_do:"):
        movie_id = data.split(":", 1)[1]
        db.delete_movie(movie_id)
        await query.answer("Movie deleted.")
        await query.edit_message_text(
            "✅ *Movie and all associated files deleted from database.*",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Movies List", callback_data="adm_movies")]]),
            parse_mode="Markdown"
        )

    # 6. Post Movie to Channel
    elif data.startswith("adm_post_chan:"):
        movie_id = data.split(":", 1)[1]
        movie = db.get_movie(movie_id)
        files = db.get_movie_files(movie_id)
        chan = db.get_force_sub_channel()

        if not movie or not chan:
            await query.answer("Channel or movie not configured.", show_alert=True)
            return

        bot_user = await context.bot.get_me()
        bot_username = bot_user.username or BOT_USERNAME or "bot"

        post_text, reply_markup = movie_engine.format_movie_channel_post(movie, files, bot_username)

        try:
            if movie.get("poster_file_id"):
                await context.bot.send_photo(
                    chat_id=chan,
                    photo=movie["poster_file_id"],
                    caption=post_text,
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
            else:
                await context.bot.send_message(
                    chat_id=chan,
                    text=post_text,
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
            await query.answer("✅ Successfully posted to channel!", show_alert=True)
        except Exception as e:
            logger.error(f"Failed to post to channel {chan}: {e}", exc_info=True)
            await query.answer(f"Failed to post to channel: {e}", show_alert=True)

    # 7. Configure Force-Sub Channel Prompt
    elif data == "adm_set_channel":
        db.set_user_state(user_id, "waiting_for_force_channel")
        curr = db.get_force_sub_channel() or "None"
        cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="adm_main")]])
        await query.edit_message_text(
            f"📢 *MANDATORY CHANNEL (FORCE JOIN) CONFIGURATION*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• Current Target: `{curr}`\n\n"
            "Please send the channel **username** (e.g. `@MyChannel`) or **ID** (e.g. `-100xxxxxxxxxx`).\n"
            "Send `off` to disable force join.\n\n"
            "*(Make sure Movie Dot is an Administrator in this channel so it can verify subscribers!)*",
            reply_markup=cancel_kb,
            parse_mode="Markdown"
        )

    # 8. Detailed Statistics
    elif data == "adm_stats":
        stats = db.get_stats()
        text = (
            "📊 *MOVIE DOT SYSTEM STATISTICS*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 *Total Registered Users:* `{stats['total_users']}`\n"
            f"⚡ *Total Files Delivered:* `{stats['total_delivered']}`\n"
            f"🎬 *Total Movies Indexed:* `{stats['total_movies']}`\n"
            f"📁 *Total File Qualities:* `{stats['total_files']}`\n"
            f"📦 *Indexed Storage:* `{movie_engine.format_size(stats['total_size_bytes'])}`\n"
            f"📢 *Force-Join Channel:* `{stats['force_sub_channel'] or 'None'}`\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
        back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="adm_main")]])
        await query.edit_message_text(text, reply_markup=back_kb, parse_mode="Markdown")

    # 9. Broadcast
    elif data == "adm_broadcast":
        db.set_user_state(user_id, "waiting_for_broadcast")
        cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="adm_main")]])
        await query.edit_message_text(
            "📢 *Broadcast Announcement*\n\n"
            "Please send the text message you wish to broadcast to all registered bot users.",
            reply_markup=cancel_kb,
            parse_mode="Markdown"
        )

    # 10. Close
    elif data == "adm_close":
        db.set_user_state(user_id, None)
        await query.message.delete()

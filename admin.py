"""
Admin Panel and Callback Query Handlers.
Provides an interactive inline keyboard interface for managing watermark settings,
updating the watermark image, broadcasting announcements, and viewing statistics.
"""

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import ContextTypes
from config import ADMIN_IDS, DEFAULT_SETTINGS
from database import db
from watermark_engine import watermark_engine

# Helper to check if a user is an authorized admin
def is_admin(user_id: int) -> bool:
    # If ADMIN_IDS is defined, check membership
    if ADMIN_IDS:
        return user_id in ADMIN_IDS
    # If no ADMIN_IDS set yet, allow user to know they need to set it
    return False

def get_admin_dashboard_text() -> str:
    settings = db.get_all_settings()
    stats = db.get_stats()
    wm_info = watermark_engine.get_watermark_info()

    pos_display = settings.get("position", DEFAULT_SETTINGS["position"]).replace("_", " ").title()
    scale = settings.get("scale", DEFAULT_SETTINGS["scale"])
    opacity = settings.get("opacity", DEFAULT_SETTINGS["opacity"])
    padding = settings.get("padding", DEFAULT_SETTINGS["padding"])
    out_mode = settings.get("output_mode", DEFAULT_SETTINGS["output_mode"]).capitalize()

    wm_status = f"{wm_info.get('width', 0)}x{wm_info.get('height', 0)} px ({wm_info.get('format', 'PNG')})" if wm_info.get("exists") else "❌ Missing"

    text = (
        "🛠 *ADMIN CONTROL PANEL*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 *Bot Statistics:*\n"
        f" • Total Users: `{stats['total_users']}`\n"
        f" • Thumbnails Watermarked: `{stats['total_processed']}`\n\n"
        f"🖼 *Active Watermark:*\n"
        f" • Source: `{'Custom Upload' if wm_info.get('is_custom') else 'Default Sample'}`\n"
        f" • Resolution: `{wm_status}`\n\n"
        f"⚙️ *Current Placement Settings:*\n"
        f" • 📍 Position: *{pos_display}*\n"
        f" • 📐 Size: *{scale}%* of thumbnail width\n"
        f" • 💧 Opacity: *{opacity}%*\n"
        f" • 📏 Edge Margin: *{padding}px*\n"
        f" • 📤 Output Mode: *{out_mode}*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Select an option below to adjust settings or upload a new watermark:"
    )
    return text

def get_admin_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🖼️ Change Watermark", callback_data="adm_change_wm"),
            InlineKeyboardButton("👁️ Preview Current", callback_data="adm_preview")
        ],
        [
            InlineKeyboardButton("📍 Position", callback_data="adm_menu_pos"),
            InlineKeyboardButton("📐 Size", callback_data="adm_menu_size"),
            InlineKeyboardButton("💧 Opacity", callback_data="adm_menu_opacity")
        ],
        [
            InlineKeyboardButton("📏 Edge Margin", callback_data="adm_menu_pad"),
            InlineKeyboardButton("📤 Output Mode", callback_data="adm_menu_output")
        ],
        [
            InlineKeyboardButton("📊 Detailed Stats", callback_data="adm_stats"),
            InlineKeyboardButton("📢 Broadcast", callback_data="adm_broadcast")
        ],
        [
            InlineKeyboardButton("🔄 Reset to Default", callback_data="adm_confirm_reset"),
            InlineKeyboardButton("❌ Close Panel", callback_data="adm_close")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_position_keyboard() -> InlineKeyboardMarkup:
    current = db.get_setting("position", DEFAULT_SETTINGS["position"])
    
    def btn(label, code):
        mark = " ✅" if current == code else ""
        return InlineKeyboardButton(f"{label}{mark}", callback_data=f"set_pos_{code}")

    keyboard = [
        [btn("↖️ Top-Left", "top_left"), btn("⬆️ Top-Center", "top_center"), btn("↗️ Top-Right", "top_right")],
        [btn("⬅️ Mid-Left", "center_left"), btn("⏺️ Center", "center"), btn("➡️ Mid-Right", "center_right")],
        [btn("↙️ Bot-Left", "bottom_left"), btn("⬇️ Bot-Center", "bottom_center"), btn("↘️ Bot-Right", "bottom_right")],
        [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="adm_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_size_keyboard() -> InlineKeyboardMarkup:
    current = int(db.get_setting("scale", DEFAULT_SETTINGS["scale"]))
    sizes = [10, 15, 20, 25, 30, 35, 40, 50]
    buttons = []
    row = []
    for s in sizes:
        mark = " ✅" if current == s else ""
        row.append(InlineKeyboardButton(f"{s}%{mark}", callback_data=f"set_size_{s}"))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="adm_main")])
    return InlineKeyboardMarkup(buttons)

def get_opacity_keyboard() -> InlineKeyboardMarkup:
    current = int(db.get_setting("opacity", DEFAULT_SETTINGS["opacity"]))
    opacities = [20, 40, 60, 75, 85, 100]
    buttons = []
    row = []
    for op in opacities:
        mark = " ✅" if current == op else ""
        row.append(InlineKeyboardButton(f"{op}%{mark}", callback_data=f"set_opac_{op}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="adm_main")])
    return InlineKeyboardMarkup(buttons)

def get_padding_keyboard() -> InlineKeyboardMarkup:
    current = int(db.get_setting("padding", DEFAULT_SETTINGS["padding"]))
    paddings = [0, 10, 20, 30, 50]
    buttons = []
    row = []
    for p in paddings:
        mark = " ✅" if current == p else ""
        lbl = f"{p}px (Flush)" if p == 0 else f"{p}px"
        row.append(InlineKeyboardButton(f"{lbl}{mark}", callback_data=f"set_pad_{p}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="adm_main")])
    return InlineKeyboardMarkup(buttons)

def get_output_mode_keyboard() -> InlineKeyboardMarkup:
    current = db.get_setting("output_mode", DEFAULT_SETTINGS["output_mode"])
    modes = [
        ("📷 Photo + 📄 Document (Recommended)", "both"),
        ("📄 Uncompressed Document Only", "document"),
        ("📷 Compressed Photo Only", "photo")
    ]
    buttons = []
    for label, code in modes:
        mark = " ✅" if current == code else ""
        buttons.append([InlineKeyboardButton(f"{label}{mark}", callback_data=f"set_out_{code}")])
    buttons.append([InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="adm_main")])
    return InlineKeyboardMarkup(buttons)

async def handle_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /admin command."""
    user = update.effective_user
    if not is_admin(user.id):
        if not ADMIN_IDS:
            await update.message.reply_text(
                f"⚠️ *Admin Not Configured Yet*\n\n"
                f"Your Telegram User ID is: `{user.id}`\n\n"
                f"To authorize yourself as admin, add your ID to the `.env` file:\n"
                f"`ADMIN_IDS={user.id}`\n\n"
                f"Then restart the bot or run `/admin` again.",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("⛔ *Access Denied:* You are not authorized to use the admin panel.", parse_mode="Markdown")
        return

    # Clear any pending state
    db.set_user_state(user.id, None)

    await update.message.reply_text(
        get_admin_dashboard_text(),
        reply_markup=get_admin_keyboard(),
        parse_mode="Markdown"
    )

async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles all admin inline button presses."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await query.edit_message_text("⛔ *Unauthorized action.*", parse_mode="Markdown")
        return

    data = query.data

    if data == "adm_main":
        db.set_user_state(user_id, None)
        await query.edit_message_text(
            get_admin_dashboard_text(),
            reply_markup=get_admin_keyboard(),
            parse_mode="Markdown"
        )

    elif data == "adm_change_wm":
        db.set_user_state(user_id, "waiting_for_watermark")
        cancel_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel & Return", callback_data="adm_main")]
        ])
        await query.edit_message_text(
            "🖼️ *Upload New Watermark*\n\n"
            "Please send your **exact watermark image** now.\n\n"
            "📌 *Tips:*\n"
            " • Send as a **PNG file (Document)** for crisp transparent background.\n"
            " • Or send as a standard photo.\n"
            " • The exact design will be preserved without any modifications.",
            reply_markup=cancel_kb,
            parse_mode="Markdown"
        )

    elif data == "adm_preview":
        await query.message.reply_text("⏳ Generating live preview thumbnail...")
        try:
            preview_bytes = watermark_engine.generate_preview_thumbnail()
            settings = db.get_all_settings()
            pos = settings.get("position", DEFAULT_SETTINGS["position"]).replace("_", " ").title()
            scale = settings.get("scale", DEFAULT_SETTINGS["scale"])
            opacity = settings.get("opacity", DEFAULT_SETTINGS["opacity"])
            pad = settings.get("padding", DEFAULT_SETTINGS["padding"])

            caption = (
                "👁️ *Live Watermark Preview (1280x720 Canvas)*\n\n"
                f" • Position: *{pos}*\n"
                f" • Size: *{scale}%*\n"
                f" • Opacity: *{opacity}%*\n"
                f" • Margin: *{pad}px*"
            )
            await query.message.reply_photo(photo=preview_bytes, caption=caption, parse_mode="Markdown")
        except Exception as e:
            await query.message.reply_text(f"❌ Error generating preview: {e}")

    elif data == "adm_menu_pos":
        await query.edit_message_text(
            "📍 *Select Watermark Position:*\n\n"
            "Choose one of the 9 anchor positions below:",
            reply_markup=get_position_keyboard(),
            parse_mode="Markdown"
        )

    elif data.startswith("set_pos_"):
        new_pos = data.replace("set_pos_", "")
        db.set_setting("position", new_pos)
        await query.edit_message_text(
            f"✅ Position updated to: *{new_pos.replace('_', ' ').title()}*",
            reply_markup=get_position_keyboard(),
            parse_mode="Markdown"
        )

    elif data == "adm_menu_size":
        await query.edit_message_text(
            "📐 *Select Watermark Size:*\n\n"
            "Watermark width as a percentage of the thumbnail width (aspect ratio is strictly preserved):",
            reply_markup=get_size_keyboard(),
            parse_mode="Markdown"
        )

    elif data.startswith("set_size_"):
        new_size = int(data.replace("set_size_", ""))
        db.set_setting("scale", new_size)
        await query.edit_message_text(
            f"✅ Watermark scale set to: *{new_size}%*",
            reply_markup=get_size_keyboard(),
            parse_mode="Markdown"
        )

    elif data == "adm_menu_opacity":
        await query.edit_message_text(
            "💧 *Select Watermark Opacity:*\n\n"
            "Choose opacity percentage (100% is completely opaque):",
            reply_markup=get_opacity_keyboard(),
            parse_mode="Markdown"
        )

    elif data.startswith("set_opac_"):
        new_opac = int(data.replace("set_opac_", ""))
        db.set_setting("opacity", new_opac)
        await query.edit_message_text(
            f"✅ Watermark opacity set to: *{new_opac}%*",
            reply_markup=get_opacity_keyboard(),
            parse_mode="Markdown"
        )

    elif data == "adm_menu_pad":
        await query.edit_message_text(
            "📏 *Select Edge Margin (Padding):*\n\n"
            "Distance in pixels from thumbnail edges:",
            reply_markup=get_padding_keyboard(),
            parse_mode="Markdown"
        )

    elif data.startswith("set_pad_"):
        new_pad = int(data.replace("set_pad_", ""))
        db.set_setting("padding", new_pad)
        await query.edit_message_text(
            f"✅ Margin set to: *{new_pad}px*",
            reply_markup=get_padding_keyboard(),
            parse_mode="Markdown"
        )

    elif data == "adm_menu_output":
        await query.edit_message_text(
            "📤 *Select Output Format Mode:*\n\n"
            "Configure how watermarked thumbnails are delivered to users:",
            reply_markup=get_output_mode_keyboard(),
            parse_mode="Markdown"
        )

    elif data.startswith("set_out_"):
        new_out = data.replace("set_out_", "")
        db.set_setting("output_mode", new_out)
        await query.edit_message_text(
            f"✅ Output mode updated to: *{new_out.capitalize()}*",
            reply_markup=get_output_mode_keyboard(),
            parse_mode="Markdown"
        )

    elif data == "adm_stats":
        stats = db.get_stats()
        wm_info = watermark_engine.get_watermark_info()
        text = (
            "📊 *DETAILED SYSTEM STATISTICS*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 *Total Registered Users:* `{stats['total_users']}`\n"
            f"🖼️ *Total Thumbnails Processed:* `{stats['total_processed']}`\n\n"
            f"🎨 *Active Watermark Details:*\n"
            f" • File: `{wm_info.get('filename')}`\n"
            f" • Dimensions: `{wm_info.get('width')} x {wm_info.get('height')} px`\n"
            f" • Color Mode: `{wm_info.get('mode')}`\n"
            f" • Format: `{wm_info.get('format')}`\n"
            f" • Custom: `{'Yes' if wm_info.get('is_custom') else 'Default'}`\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
        back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_main")]])
        await query.edit_message_text(text, reply_markup=back_kb, parse_mode="Markdown")

    elif data == "adm_broadcast":
        db.set_user_state(user_id, "waiting_for_broadcast")
        cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="adm_main")]])
        await query.edit_message_text(
            "📢 *Broadcast Announcement*\n\n"
            "Please send the text message you wish to broadcast to all registered bot users.",
            reply_markup=cancel_kb,
            parse_mode="Markdown"
        )

    elif data == "adm_confirm_reset":
        confirm_kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⚠️ Yes, Reset Everything", callback_data="adm_do_reset"),
                InlineKeyboardButton("❌ Cancel", callback_data="adm_main")
            ]
        ])
        await query.edit_message_text(
            "⚠️ *Confirm Reset*\n\n"
            "Are you sure you want to reset all placement settings and restore the default sample watermark?",
            reply_markup=confirm_kb,
            parse_mode="Markdown"
        )

    elif data == "adm_do_reset":
        db.reset_settings()
        watermark_engine.reset_watermark_to_default()
        await query.edit_message_text(
            "✅ *All settings and watermark have been reset to default.*",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Return to Admin Panel", callback_data="adm_main")]]),
            parse_mode="Markdown"
        )

    elif data == "adm_close":
        db.set_user_state(user_id, None)
        await query.message.delete()


async def handle_watermark_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /watermark command for both admin and regular users."""
    user = update.effective_user
    if is_admin(user.id):
        wm_info = watermark_engine.get_watermark_info()
        text = (
            "🏷️ *ADMIN WATERMARK CONTROL*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• Source: `{'Custom Upload' if wm_info.get('is_custom') else 'Default Sample'}`\n"
            f"• Resolution: `{wm_info.get('width', 0)} x {wm_info.get('height', 0)} px`\n\n"
            "Only administrators can change the default watermark and placement settings."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🖼️ Change Watermark Image", callback_data="adm_change_wm")],
            [InlineKeyboardButton("📍 Placement & Position", callback_data="adm_menu_pos")],
            [InlineKeyboardButton("👁️ Preview Placement", callback_data="adm_preview")],
            [InlineKeyboardButton("🔙 Full Admin Panel", callback_data="adm_main")]
        ])
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        wm_info = watermark_engine.get_watermark_info()
        text = (
            "🏷️ *DEFAULT WATERMARK INFO*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "The global watermark applied to thumbnails is configured by administrators.\n\n"
            f"• Watermark Status: `Active ({wm_info.get('width', 0)}x{wm_info.get('height', 0)} px)`\n"
            "• Every thumbnail you send or attach to a video will automatically have this watermark applied."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👁️ Preview Watermark Placement", callback_data="user_preview")]
        ])
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def handle_settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /settings command."""
    user = update.effective_user
    if is_admin(user.id):
        await handle_admin_command(update, context)
    else:
        settings = db.get_all_settings()
        out_mode = settings.get("output_mode", DEFAULT_SETTINGS["output_mode"]).capitalize()
        text = (
            "⚙️ *BOT SETTINGS*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• Current Output Delivery: *{out_mode}*\n\n"
            "Admins manage global placement settings (position, size, opacity).\n"
            "Tap below to preview how watermarks appear on thumbnails:"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👁️ Preview Watermark", callback_data="user_preview")],
            [InlineKeyboardButton("ℹ️ Help & Instructions", callback_data="user_help")]
        ])
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

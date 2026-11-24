"""
Movie Parsing, Quality Detection, and Force Join Verification Engine.
Handles:
- Automatic movie title, year, quality parsing (480p, 720p, 1080p, 2160p / 4K)
- Safe slug and deep-link generation
- Mandatory channel subscription verification (Force Join)
- Quality selector and channel post markup builders
"""

import re
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger("MovieEngine")

# Standard quality labels in resolution order
QUALITY_480P = "480p"
QUALITY_720P = "720p"
QUALITY_1080P = "1080p"
QUALITY_4K = "2160p / 4K"

ALL_QUALITIES = [QUALITY_480P, QUALITY_720P, QUALITY_1080P, QUALITY_4K]

# Regex patterns for quality detection
RE_4K = re.compile(r'(?i)\b(?:2160p|2160i|4k|uhd|ultra[ ._-]?hd|4k-uhd)\b')
RE_1080P = re.compile(r'(?i)\b(?:1080p|1080i|fhd|full[ ._-]?hd)\b')
RE_720P = re.compile(r'(?i)\b(?:720p|720i|hdrip|hdtv)\b|(?<![a-z0-9])720(?![a-z0-9])')
RE_480P = re.compile(r'(?i)\b(?:480p|480i|576p|360p|sd|dvdrip|webrip(?!\.))')

# Noise keywords commonly found in movie release filenames
RELEASE_NOISE = re.compile(
    r'(?i)\b(?:2160p|1080p|1080i|720p|576p|480p|360p|4k|uhd|fhd|hd|sd|'
    r'bluray|blu-ray|brrip|bdrip|web-dl|webdl|webrip|dvdrip|hdtv|hdrip|'
    r'x264|x265|h264|h265|hevc|avc|10bit|8bit|hdr|hdr10|dv|dolby[ ._-]?vision|'
    r'aac|ac3|dts|ddp5\.1|dd5\.1|atmos|mp3|flac|'
    r'dual[ ._-]?audio|multi[ ._-]?audio|hindi|english|tamil|telugu|malayalam|kannada|'
    r'esub|sub|msubs|proper|repack|unrated|extended|directors[ ._-]?cut)\b'
)


def format_size(size_bytes: int) -> str:
    """Formats file size in bytes into human-readable string (e.g. 450 MB, 1.4 GB)."""
    if not size_bytes or size_bytes <= 0:
        return "Unknown size"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def detect_quality(
    filename: str = "",
    caption: str = "",
    width: int = 0,
    height: int = 0
) -> str:
    """
    Detects movie quality from filename, caption, or video stream dimensions.
    Returns: '480p', '720p', '1080p', or '2160p / 4K'.
    """
    combined = f"{filename} {caption}".strip()
    norm_text = re.sub(r'[._\-\[\]\(\)\{\}]', ' ', combined)

    # 1. Check filename & caption using regular expressions
    if RE_4K.search(norm_text):
        return QUALITY_4K
    if RE_1080P.search(norm_text):
        return QUALITY_1080P
    if RE_720P.search(norm_text):
        return QUALITY_720P
    if RE_480P.search(norm_text):
        return QUALITY_480P

    # 2. Fallback to video dimensions if available
    h = max(height, 0)
    w = max(width, 0)
    effective_res = max(h, int(w * 9 / 16)) if w > 0 else h

    if effective_res >= 1600 or w >= 3200:
        return QUALITY_4K
    elif effective_res >= 900 or w >= 1600:
        return QUALITY_1080P
    elif effective_res >= 600 or w >= 1000:
        return QUALITY_720P
    elif effective_res > 0 or w > 0:
        return QUALITY_480P

    # Default fallback
    return QUALITY_720P


def parse_movie_info(filename: str, caption: str = "") -> Dict[str, Any]:
    """
    Extracts movie title, year, clean title, movie_id, and quality from filename and caption.
    """
    quality = detect_quality(filename=filename, caption=caption)

    # Check for explicit movie line in caption (e.g. "🎬 Movie: 418 (2026)")
    caption_title = None
    if caption:
        cap_match = re.search(r'(?i)(?:🎬|🎥|Movie|Title|Film)\s*[:\-]?\s*([^\n\r]+)', caption)
        if cap_match:
            candidate = cap_match.group(1).strip()
            candidate = re.sub(r'[*_`#~]', '', candidate).strip()
            if candidate and len(candidate) > 1:
                caption_title = candidate

    path_obj = Path(filename)
    stem = path_obj.stem
    ext = path_obj.suffix.lower()

    # Extract release year (1900-2099)
    year = None
    target_text = caption_title if caption_title else stem
    year_match = re.search(r'\b(19\d{2}|20\d{2})\b', target_text)
    if year_match:
        year = int(year_match.group(1))

    # Clean stem of noise keywords
    cleaned = target_text
    if not caption_title:
        if year_match:
            pre_year = target_text[:year_match.start()].strip()
            pre_year = re.sub(r'[\(\[\{\.\_\-\s]+$', '', pre_year).strip()
            if pre_year:
                cleaned = pre_year

        cleaned = re.sub(r'[._]', ' ', cleaned)
        cleaned = re.sub(r'\[[^\]]*\]', ' ', cleaned)
        cleaned = re.sub(r'\([^\)]*\)', ' ', cleaned)
        cleaned = RELEASE_NOISE.sub(' ', cleaned)
        cleaned = re.sub(r'[\-\:\,\;\|\/\\]+', ' ', cleaned)
        cleaned = ' '.join(cleaned.split())

    if not cleaned or len(cleaned) < 2:
        cleaned = stem

    title_words = cleaned.split()
    formatted_title = ' '.join(w.capitalize() if not w.isupper() else w for w in title_words)

    if year and str(year) not in formatted_title:
        clean_title = f"{formatted_title} ({year})"
    else:
        clean_title = formatted_title

    slug = re.sub(r'[^a-zA-Z0-9]+', '_', clean_title).strip('_').lower()
    if not slug:
        slug = f"movie_{abs(hash(clean_title)) % 1000000}"
    movie_id = slug[:55]

    return {
        "title": formatted_title,
        "year": year,
        "clean_title": clean_title,
        "movie_id": movie_id,
        "quality": quality,
        "extension": ext
    }


def generate_deep_link(movie_id: str, bot_username: str) -> str:
    """Generates Telegram deep linking URL for the movie."""
    clean_username = bot_username.lstrip("@").strip()
    return f"https://t.me/{clean_username}?start=get_{movie_id}"


def format_quality_selection_keyboard(
    movie_id: str,
    files: List[Dict[str, Any]],
    include_all_button: bool = True
) -> InlineKeyboardMarkup:
    """
    Creates an inline keyboard showing only the file qualities that actually exist.
    Tapping a quality button sends the file to the user.
    """
    keyboard = []

    for f in files:
        qual = f.get("quality", "HD")
        size_str = format_size(f.get("file_size", 0))
        btn_text = f"📥 {qual}  ({size_str})"
        callback = f"getfile:{movie_id}:{qual}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=callback)])

    if include_all_button and len(files) > 1:
        keyboard.append([InlineKeyboardButton("📦 Send All Qualities", callback_data=f"getall:{movie_id}")])

    return InlineKeyboardMarkup(keyboard)


def format_movie_channel_post(
    movie: Dict[str, Any],
    files: List[Dict[str, Any]],
    bot_username: str
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Generates channel post text and inline button linking to the bot via Deep Linking.
    """
    title = movie.get("title", "Movie")
    year = movie.get("year")
    clean_title = f"{title} ({year})" if year and str(year) not in title else title
    movie_id = movie.get("movie_id")

    lines = [
        f"🎬 *{clean_title}*",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "📥 *Available Qualities:*"
    ]

    for f in files:
        qual = f.get("quality", "HD")
        size_str = format_size(f.get("file_size", 0))
        lines.append(f" • *{qual}* ({size_str})")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("👇 *Click below to get all download links:*")

    post_text = "\n".join(lines)

    deep_link = generate_deep_link(movie_id, bot_username)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 GET ALL FILES", url=deep_link)]
    ])

    return post_text, keyboard


# ==================== MANDATORY CHANNEL SUBSCRIPTION (FORCE JOIN) ====================

async def check_channel_membership(
    bot,
    user_id: int,
    channel: str
) -> Tuple[bool, str, str]:
    """
    Verifies if user_id is a subscribed member of the channel.
    Returns: (is_member, status_reason, channel_invite_url)
    """
    clean_chan = (channel or "").strip()
    if not clean_chan:
        # No channel configured, allow access
        return True, "no_channel_set", ""

    # Parse target chat
    if clean_chan.startswith("-100") or (clean_chan.startswith("-") and clean_chan[1:].isdigit()) or clean_chan.isdigit():
        target_chat = int(clean_chan)
        channel_url = f"https://t.me/c/{str(clean_chan).replace('-100', '')}"
    else:
        username = clean_chan.lstrip("@")
        target_chat = f"@{username}"
        channel_url = f"https://t.me/{username}"

    try:
        member = await bot.get_chat_member(chat_id=target_chat, user_id=user_id)
        status = getattr(member, "status", "").lower()
    except Exception as e:
        err_msg = str(e).lower()
        if "user not found" in err_msg or "participant_id_invalid" in err_msg:
            return False, "not_in_chat", channel_url
        logger.warning(f"Failed get_chat_member for user {user_id} in {channel}: {e}")
        return False, f"error: {e}", channel_url

    # Check member status
    is_member = False
    if status in ["creator", "administrator", "member", "owner"]:
        is_member = True
    elif status == "restricted":
        is_member = getattr(member, "is_member", True)

    # Optionally attempt to get invite link or chat username
    try:
        if hasattr(bot, "get_chat"):
            chat_val = bot.get_chat(target_chat)
            if asyncio.iscoroutine(chat_val):
                chat_obj = await chat_val
                if getattr(chat_obj, "username", None):
                    channel_url = f"https://t.me/{chat_obj.username}"
                elif getattr(chat_obj, "invite_link", None):
                    channel_url = chat_obj.invite_link
    except Exception:
        pass

    return is_member, status, channel_url


def format_force_sub_message(channel_url: str, movie_id: str) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Builds the mandatory subscription prompt and verification buttons.
    Preserves the movie_id in the verification callback.
    """
    text = (
        "🎬 *Welcome to MOVIE DOT!*\n\n"
        "⚠️ *Before accessing movie files, you must subscribe to our Telegram channel.*"
    )

    url_btn = InlineKeyboardButton("📢 JOIN CHANNEL", url=channel_url or "https://t.me/")
    verify_btn = InlineKeyboardButton("✅ I'VE JOINED – VERIFY", callback_data=f"verify_sub:{movie_id}")

    keyboard = InlineKeyboardMarkup([
        [url_btn],
        [verify_btn]
    ])

    return text, keyboard

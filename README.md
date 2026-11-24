# 🎬 MOVIE DOT — Telegram Movie File Management & Delivery Bot

A dedicated, high-performance Telegram bot built with Python, `python-telegram-bot` (v22+), and SQLite, designed exclusively for **Movie File Management, Automatic Quality Delivery**, and **Mandatory Channel Subscription (Force Join)**.

---

## 🌟 Key Features

| Feature | Description |
| :--- | :--- |
| 🎬 **Movie File Management** | Add, index, organize, and delete multi-quality movie files (MKV & MP4). |
| 📥 **GET ALL FILES Deep Linking** | Generates unique deep links (`t.me/bot?start=get_<movie_id>`) connecting channel posts directly to the bot. |
| 📢 **Mandatory Channel Subscription (Force Join)** | Automatically verifies channel membership via Telegram Bot API `getChatMember` before allowing access to any movie files. |
| ⚡ **Zero-Bandwidth Instant Delivery** | Delivers original videos and MKV documents using stored Telegram `file_id` values with zero server downloads or re-encoding. |
| 🔍 **Automatic Quality Detection** | Detects **480p**, **720p**, **1080p**, and **2160p / 4K** from filenames, captions, or video streams. |
| 🛡️ **Duplicate Prevention** | Enforces unique `file_unique_id` constraints in SQLite to prevent duplicate file entries. |
| 📱 **Role-Based Home Screen** | Modern welcome screen showing admin controls (`[ 🎬 Manage Movies ]`) exclusively to bot owners. |
| 🛠️ **Dynamic Channel Configuration** | Admins can set or update the mandatory subscription channel anytime using `/setchannel` or the visual Admin Panel. |

---

## 📱 Bot Home Screen

When users send `/start` without parameters:

```
🎬 Welcome to MOVIE DOT!

Your Movie File Management Bot.
```

**Main Menu:**
- `[ 🎬 Manage Movies ]` *(Visible ONLY to Bot Owner / Admins)*
- `[ 📥 GET ALL FILES ]`
- `[ ℹ️ How to Use ]`

---

## 📢 Mandatory Channel Subscription (Force Join) Workflow

1. A user clicks **📥 GET ALL FILES** on a channel post or opens a deep link (`t.me/bot?start=get_418_2026`).
2. The bot queries the Telegram Bot API to check whether the user is an active member (`member`, `administrator`, or `creator/owner`) of the configured channel.
3. If the user is **NOT** subscribed, the bot blocks all file access and sends:
   ```
   🎬 Welcome to MOVIE DOT!

   ⚠️ Before accessing movie files, you must subscribe to our Telegram channel.
   ```
   Buttons:
   - `[ 📢 JOIN CHANNEL ]` (Opens your official Telegram channel)
   - `[ ✅ I'VE JOINED – VERIFY ]` (Preserves the requested `movie_id`)
4. When the user taps **✅ I'VE JOINED – VERIFY**, the bot re-verifies their membership:
   - **If joined:** Displays confirmation toast and **immediately continues the same movie request** without asking the user to start over!
   - **If not joined:** Displays an alert prompting them to join first.
5. The bot presents only the qualities that actually exist:
   ```
   🎬 418 (2026)

   📥 Select Your Quality:

   - 480p
   - 720p
   - 1080p
   ```
6. The user selects a quality, and the bot delivers the file instantly using the stored `file_id`.

---

## 📋 Commands Menu

- `/start` – Start the bot / access movie deep link.
- `/help` – Complete instructions on how to use Movie Dot.
- `/movies` – View all indexed movies, qualities, and deep links (Admin only).
- `/setchannel <@channel>` – Configure mandatory subscription channel (Admin only).
- `/admin` – Open interactive Admin Control Panel (Admin only).
- `/cancel` – Cancel any pending admin input.

---

## 🚀 Setup & Deployment Instructions

### Step 1: Configure `.env`
Edit `.env` in `telegram-watermark-bot`:
```env
BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
ADMIN_IDS=YOUR_TELEGRAM_USER_ID

# Channel username or ID for mandatory subscription (e.g. @MyChannel or -100xxxxxxxxxx)
CHANNEL_ID=@YourChannel

# Bot username without @
BOT_USERNAME=Movie_dot_file_bot
```

### Step 2: Grant Channel Permissions
Add your bot as an **Administrator** in your Telegram channel with:
- **Post Messages**
- **Edit Messages of Others** (to automatically attach `📥 GET ALL FILES` buttons to video uploads)
- **Invite Users via Link**

### Step 3: Start the Bot
- **Windows (foreground):**
  ```powershell
  python bot.py
  # or: .\run_bot.bat
  ```
- **Windows 24/7 background:**
  ```powershell
  wscript start_background_247.vbs
  ```
- **Linux / VPS:**
  ```bash
  python3 bot.py
  # or systemd service
  ```

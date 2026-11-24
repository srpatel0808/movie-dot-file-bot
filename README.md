# 🏷️ Telegram Thumbnail & Watermark Bot (with Video Thumbnail Changer)

A high-performance, production-ready **Telegram Thumbnail & Watermark Bot** built with Python, `python-telegram-bot`, `Pillow`, and `ffmpeg`.

Designed to watermark YouTube thumbnails, social media images, banners, and **change/watermark MP4 video thumbnails with ZERO video re-encoding**, maintaining **100% of the original video and image quality**.

---

## 🌟 Key Features

| Feature | Description |
| :--- | :--- |
| 🎬 **Video Thumbnail Changer** | Send any MP4 video directly to the bot. Extract the current thumbnail, replace it with a custom image, and watermark it. |
| ⚡ **Zero Video Re-encoding** | Uses FFmpeg stream-copy (`-c copy`) so videos are not re-encoded. 100% resolution, bitrate, audio, and quality are preserved. |
| 📱 **Telegram Command Menu** | Commands appear automatically when users tap `/` in Telegram chat via `setMyCommands`. |
| 🖼️ **Exact Custom Watermark** | Upload your brand logo/watermark directly in Telegram. Admin controls ensure exact artwork preservation without redesign. |
| 💎 **Zero Image Quality Loss** | Keeps 100% original dimensions (4K, 1080p, 720p), color profile, and lossless quality. |
| 📍 **9 Anchor Positions** | Top-Left, Top-Center, Top-Right, Mid-Left, Center, Mid-Right, Bottom-Left, Bottom-Center, Bottom-Right. |
| 📐 **Customizable Scale & Opacity** | Watermark size (10% to 50%) and opacity (20% to 100%) with live test preview. |
| 📂 **Stored User Thumbnail** | Users can save a custom thumbnail via `/thumbnail` and attach it to any video with one click. |
| 🛠️ **Admin Control Panel** | Only `ADMIN_IDS` users can change the default watermark and global placement settings. |
| ⏰ **24/7 Keep-Alive** | Includes Linux `systemd` service, `Docker`, `docker-compose`, and auto-restart scripts. |

---

## 📋 Commands Menu

Tap `/` in Telegram to access all registered commands:

- `/start` – Start the bot and display the welcome menu.
- `/help` – Complete instructions for images and video thumbnails.
- `/thumbnail` – Upload, view, or change your stored custom thumbnail.
- `/watermark` – Apply or manage custom watermark (Admin only for changing).
- `/settings` – Bot settings and delivery preferences.
- `/cancel` – Cancel any active operation or pending upload.
- `/admin` – Open visual Admin Panel (Admins only).
- `/preview` – Preview current watermark placement on a sample 1280x720 canvas.

---

## 🎬 How Video Thumbnail Changing Works

1. Send an **MP4 video** (up to 20MB) to the bot.
2. The bot extracts the current thumbnail and presents 3 options:
   - **✨ Apply My Saved Thumbnail (Watermarked)**: Attaches the thumbnail you saved in your profile.
   - **🏷️ Watermark Current Thumbnail & Update**: Takes the video's existing thumbnail, applies your watermark, and updates the video.
   - **📤 Upload New Custom Thumbnail**: Upload any new image to become the video's thumbnail.
3. The bot attaches the thumbnail to the MP4 container and sends the updated video back, along with the high-resolution watermarked thumbnail file.
4. **No Re-encoding**: The process takes only a couple of seconds and never degrades video quality.

---

## 🚀 Quick Setup & Installation

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Configure `.env`
Edit `.env` with your bot token and admin ID:
```env
BOT_TOKEN=9086748319:AAG3QmwLIRUuFbLUMkq0QETAVFh0uFoBFlA
ADMIN_IDS=6160210568
```

### Step 3: Run the Bot
- **Windows**:
  ```powershell
  .\run_bot.bat
  # or: python bot.py
  ```
- **Linux / VPS**:
  ```bash
  chmod +x run_bot.sh
  ./run_bot.sh
  ```
- **Docker Compose**:
  ```bash
  docker-compose up -d --build
  ```

---

## 🧪 Testing

Run both automated test suites to verify all features:
```bash
python test_video_and_commands.py
python test_bot_full.py
```

"""
Verification Test Suite for Video Thumbnail Changer and Telegram Menu Commands.
Tests video generation, thumbnail extraction, thumbnail watermarking,
stream-copy container replacement, Telegram preview generation, and menu registration.
"""

import io
import os
import shutil
import tempfile
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw

from config import BOT_TOKEN
from database import db
from watermark_engine import watermark_engine
from video_engine import video_engine

def run_tests():
    print("=" * 65)
    print("🎬 RUNNING VIDEO THUMBNAIL CHANGER & COMMAND MENU TESTS")
    print("=" * 65)

    # 1. Test FFMPEG availability
    print("\n[1/6] Checking FFmpeg...")
    ffmpeg_exe = video_engine.ffmpeg
    assert Path(ffmpeg_exe).exists(), f"FFmpeg binary not found at {ffmpeg_exe}"
    print(f"  ✓ FFmpeg binary detected: {ffmpeg_exe}")

    temp_dir = Path(tempfile.mkdtemp(prefix="test_video_"))
    try:
        # 2. Generate a synthetic test MP4 video (1280x720, 3 seconds)
        print("\n[2/6] Generating synthetic 1280x720 MP4 test video...")
        test_video_path = temp_dir / "test_input.mp4"
        cmd_gen = [
            ffmpeg_exe,
            "-y",
            "-f", "lavfi",
            "-i", "testsrc=duration=3:size=1280x720:rate=30",
            "-f", "lavfi",
            "-i", "sine=frequency=1000:duration=3",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            str(test_video_path)
        ]
        res = subprocess.run(cmd_gen, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
        assert res.returncode == 0, f"Failed to generate test video: {res.stderr.decode()}"
        assert test_video_path.exists() and test_video_path.stat().st_size > 0
        orig_size_bytes = test_video_path.stat().st_size
        print(f"  ✓ Generated test video: {test_video_path.name} ({orig_size_bytes} bytes)")

        # 3. Test thumbnail extraction from video
        print("\n[3/6] Testing thumbnail extraction from video...")
        extracted_thumb_bytes = video_engine.extract_thumbnail_from_video(test_video_path, timestamp=1.0)
        assert extracted_thumb_bytes is not None, "Failed to extract thumbnail from video"
        extracted_img = Image.open(io.BytesIO(extracted_thumb_bytes))
        print(f"  ✓ Successfully extracted frame thumbnail: {extracted_img.size[0]}x{extracted_img.size[1]} px")
        assert extracted_img.size == (1280, 720), f"Extracted frame size mismatch: {extracted_img.size}"

        # 4. Create custom thumbnail & apply watermark
        print("\n[4/6] Creating custom thumbnail & applying brand watermark...")
        custom_thumb = Image.new("RGB", (1280, 720), (22, 101, 52))
        d = ImageDraw.Draw(custom_thumb)
        d.text((100, 300), "NEW CUSTOM THUMBNAIL COVER", fill=(255, 255, 255))
        
        cbuf = io.BytesIO()
        custom_thumb.save(cbuf, format="JPEG", quality=95)
        
        # Apply watermark
        wm_bytes, out_fmt, dims = watermark_engine.apply_watermark(cbuf.getvalue())
        assert dims == (1280, 720), "Watermarked thumbnail dimensions altered"
        print(f"  ✓ Custom thumbnail watermarked ({dims[0]}x{dims[1]} px, format={out_fmt})")

        # 5. Test video thumbnail replacement with stream copy (-c copy)
        print("\n[5/6] Replacing video thumbnail (stream-copy, zero re-encoding)...")
        wm_thumb_path = temp_dir / "watermarked_thumb.jpg"
        wm_thumb_path.write_bytes(wm_bytes)
        
        output_video_path = temp_dir / "test_output_with_new_thumb.mp4"
        success = video_engine.replace_video_thumbnail(test_video_path, wm_thumb_path, output_video_path)
        assert success is True, "Thumbnail replacement failed"
        assert output_video_path.exists() and output_video_path.stat().st_size > 0
        print(f"  ✓ Successfully attached new thumbnail to MP4: {output_video_path.stat().st_size} bytes")

        # Verify Telegram preview creation
        tg_preview = video_engine.create_telegram_thumbnail_preview(wm_bytes)
        assert len(tg_preview) < (200 * 1024), "Telegram preview exceeds 200KB limit"
        tg_img = Image.open(io.BytesIO(tg_preview))
        assert max(tg_img.size) <= 320, f"Telegram preview dimensions exceed 320px: {tg_img.size}"
        print(f"  ✓ Telegram preview generated: {tg_img.size[0]}x{tg_img.size[1]} px, {len(tg_preview)} bytes (<200KB)")

        # 6. Verify Telegram Bot Command Menu
        print("\n[6/6] Verifying Telegram Bot API Registered Commands...")
        import asyncio
        from telegram import Bot
        
        async def verify_cmds():
            bot = Bot(token=BOT_TOKEN)
            cmds = await bot.get_my_commands()
            cmd_names = [c.command for c in cmds]
            print(f"  ✓ Registered commands returned by Telegram API: {cmd_names}")
            expected = ["start", "help", "thumbnail", "watermark", "settings", "cancel"]
            for exp in expected:
                assert exp in cmd_names, f"Expected command /{exp} missing from Telegram menu!"
            print("  ✓ All 6 expected commands are active in Telegram command menu.")

        asyncio.run(verify_cmds())

        print("\n" + "=" * 65)
        print("🎉 ALL VIDEO & COMMAND MENU TESTS PASSED PERFECTLY!")
        print("=" * 65)

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    run_tests()

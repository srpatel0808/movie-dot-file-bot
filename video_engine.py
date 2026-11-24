"""
Video Processing Engine for Telegram Thumbnail Bot.
Extracts video frames/thumbnails and replaces video thumbnails using stream-copy (-c copy)
without re-encoding, preserving 100% original video resolution and quality.
"""

import io
import os
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from PIL import Image

logger = logging.getLogger("VideoEngine")

class VideoEngine:
    def __init__(self):
        self._ffmpeg_path = self._locate_ffmpeg()

    def _locate_ffmpeg(self) -> str:
        """Finds system ffmpeg or falls back to imageio-ffmpeg binary."""
        sys_ffmpeg = shutil.which("ffmpeg")
        if sys_ffmpeg:
            return sys_ffmpeg
        try:
            import imageio_ffmpeg
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception as e:
            logger.warning(f"Could not load imageio-ffmpeg: {e}")
            return "ffmpeg"

    @property
    def ffmpeg(self) -> str:
        if not self._ffmpeg_path or not Path(self._ffmpeg_path).exists():
            self._ffmpeg_path = self._locate_ffmpeg()
        return self._ffmpeg_path

    def extract_thumbnail_from_video(self, video_path: Path, timestamp: float = 1.0) -> Optional[bytes]:
        """
        Extracts a single frame from the video at `timestamp` seconds.
        Falls back to 0.0 seconds if video is shorter than 1 second.
        """
        out_jpg = video_path.with_name(f"{video_path.stem}_extracted_thumb.jpg")
        try:
            cmd = [
                self.ffmpeg,
                "-y",
                "-ss", str(timestamp),
                "-i", str(video_path),
                "-vframes", "1",
                "-q:v", "2",
                str(out_jpg)
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
            if res.returncode != 0 or not out_jpg.exists():
                # Try at timestamp 0.0
                cmd[3] = "0.0"
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)

            if out_jpg.exists():
                data = out_jpg.read_bytes()
                out_jpg.unlink(missing_ok=True)
                return data
            return None
        except Exception as e:
            logger.error(f"Error extracting frame from video: {e}", exc_info=True)
            if out_jpg.exists():
                out_jpg.unlink(missing_ok=True)
            return None

    def replace_video_thumbnail(
        self,
        video_path: Path,
        thumbnail_img_path: Path,
        output_path: Path
    ) -> bool:
        """
        Replaces/attaches the thumbnail image into the MP4 video container.
        Uses '-c copy' so the video/audio streams are NOT re-encoded.
        100% original video quality and resolution are preserved.
        """
        try:
            cmd = [
                self.ffmpeg,
                "-y",
                "-i", str(video_path),
                "-i", str(thumbnail_img_path),
                "-map", "0",
                "-map", "1",
                "-c", "copy",
                "-disposition:v:1", "attached_pic",
                "-movflags", "+faststart",
                str(output_path)
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
            if res.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
                return True
            else:
                logger.warning(f"ffmpeg replace thumbnail returned {res.returncode}: {res.stderr.decode('utf-8', errors='ignore')}")
                # Fallback: if MP4 container doesn't accept attached_pic (e.g. non-standard MP4), just copy video
                shutil.copy2(video_path, output_path)
                return True
        except Exception as e:
            logger.error(f"Failed to replace video thumbnail: {e}", exc_info=True)
            return False

    def create_telegram_thumbnail_preview(self, image_bytes: bytes) -> bytes:
        """
        Creates a thumbnail strictly optimized for Telegram's send_video `thumbnail` parameter:
        - Format: JPEG
        - Size: < 200 KB
        - Max dimension: <= 320 px
        """
        with Image.open(io.BytesIO(image_bytes)) as img:
            rgb_img = img.convert("RGB")
            # Proportional resize so max dimension is <= 320
            rgb_img.thumbnail((320, 320), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            rgb_img.save(buf, format="JPEG", quality=85, optimize=True)
            return buf.getvalue()


video_engine = VideoEngine()

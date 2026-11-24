"""
Core Watermark Processing Engine.
Applies exact user-provided watermark with customizable position, scale, opacity, and padding
while strictly maintaining original thumbnail dimensions, color profile, and visual quality.
"""

import io
import os
import shutil
from pathlib import Path
from typing import Tuple, Optional, Dict, Any, Union
from PIL import Image, ImageOps, ImageDraw, ImageFont

from config import (
    ACTIVE_WATERMARK_PATH,
    SAMPLE_WATERMARK_PATH,
    DEFAULT_SETTINGS,
    SUPPORTED_EXTENSIONS
)
from database import db


class WatermarkEngine:
    def __init__(self):
        self._ensure_watermark_exists()

    def _ensure_watermark_exists(self):
        """Ensure active watermark file exists, copying sample if needed."""
        if not ACTIVE_WATERMARK_PATH.exists() and SAMPLE_WATERMARK_PATH.exists():
            shutil.copy2(SAMPLE_WATERMARK_PATH, ACTIVE_WATERMARK_PATH)

    def get_watermark_path(self) -> Path:
        """Returns path to the currently active watermark."""
        if ACTIVE_WATERMARK_PATH.exists():
            return ACTIVE_WATERMARK_PATH
        return SAMPLE_WATERMARK_PATH

    def get_watermark_info(self) -> Dict[str, Any]:
        """Returns details about the active watermark file."""
        wm_path = self.get_watermark_path()
        if not wm_path.exists():
            return {"exists": False}

        try:
            with Image.open(wm_path) as img:
                return {
                    "exists": True,
                    "filename": wm_path.name,
                    "width": img.width,
                    "height": img.height,
                    "format": img.format or "PNG",
                    "mode": img.mode,
                    "is_custom": wm_path == ACTIVE_WATERMARK_PATH
                }
        except Exception as e:
            return {"exists": False, "error": str(e)}

    def save_new_watermark(self, image_bytes: bytes) -> Dict[str, Any]:
        """
        Saves user-provided image bytes as the exact active watermark.
        Strictly preserves exact original watermark artwork without redesign.
        Converts color mode to RGBA so transparency works cleanly.
        """
        try:
            with Image.open(io.BytesIO(image_bytes)) as img:
                # Correct orientation from EXIF if present
                img = ImageOps.exif_transpose(img)

                # Ensure RGBA mode for transparency support
                if img.mode != "RGBA":
                    rgba_img = img.convert("RGBA")
                else:
                    rgba_img = img.copy()

                # Save directly as active watermark
                rgba_img.save(ACTIVE_WATERMARK_PATH, format="PNG", optimize=True)

            return {
                "success": True,
                "width": rgba_img.width,
                "height": rgba_img.height,
                "size_bytes": len(image_bytes)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def reset_watermark_to_default(self) -> bool:
        """Resets active watermark to default sample watermark."""
        try:
            if SAMPLE_WATERMARK_PATH.exists():
                shutil.copy2(SAMPLE_WATERMARK_PATH, ACTIVE_WATERMARK_PATH)
                return True
            return False
        except Exception:
            return False

    def calculate_position(
        self,
        thumb_size: Tuple[int, int],
        wm_size: Tuple[int, int],
        position: str,
        padding: int
    ) -> Tuple[int, int]:
        """
        Calculates top-left (x, y) coordinates for watermark placement.
        Supports 9 anchor positions:
        - top_left, top_center, top_right
        - center_left, center, center_right
        - bottom_left, bottom_center, bottom_right
        """
        thumb_w, thumb_h = thumb_size
        wm_w, wm_h = wm_size

        # Clamp padding to not exceed thumbnail bounds
        pad_x = min(padding, max(0, (thumb_w - wm_w) // 2))
        pad_y = min(padding, max(0, (thumb_h - wm_h) // 2))

        # Horizontal positions
        if "left" in position:
            x = pad_x
        elif "right" in position:
            x = thumb_w - wm_w - pad_x
        else:  # center horizontal
            x = (thumb_w - wm_w) // 2

        # Vertical positions
        if "top" in position:
            y = pad_y
        elif "bottom" in position:
            y = thumb_h - wm_h - pad_y
        else:  # center vertical
            y = (thumb_h - wm_h) // 2

        # Safety clamps
        x = max(0, min(x, thumb_w - wm_w))
        y = max(0, min(y, thumb_h - wm_h))

        return (x, y)

    def apply_watermark(
        self,
        image_input: Union[bytes, io.BytesIO, Path, str],
        custom_settings: Optional[Dict[str, Any]] = None
    ) -> Tuple[bytes, str, Tuple[int, int]]:
        """
        Applies watermark to the provided thumbnail image.

        Args:
            image_input: bytes, BytesIO, or file path of thumbnail.
            custom_settings: optional override for settings dict.

        Returns:
            Tuple of:
            - output_bytes: raw bytes of watermarked image
            - output_format: 'PNG' or 'JPEG'
            - dimensions: (width, height)
        """
        # Load settings (database merged with defaults and overrides)
        settings = db.get_all_settings()
        if custom_settings:
            settings.update(custom_settings)

        position = settings.get("position", DEFAULT_SETTINGS["position"])
        scale_pct = int(settings.get("scale", DEFAULT_SETTINGS["scale"]))
        opacity_pct = int(settings.get("opacity", DEFAULT_SETTINGS["opacity"]))
        padding_px = int(settings.get("padding", DEFAULT_SETTINGS["padding"]))

        # Load active watermark
        wm_path = self.get_watermark_path()
        if not wm_path.exists():
            raise FileNotFoundError("Watermark file not found.")

        with Image.open(wm_path) as wm_file:
            wm_img = wm_file.convert("RGBA")

        # Open thumbnail image
        if isinstance(image_input, (str, Path)):
            thumb_orig = Image.open(image_input)
        elif isinstance(image_input, bytes):
            thumb_orig = Image.open(io.BytesIO(image_input))
        else:
            thumb_orig = Image.open(image_input)

        # Handle EXIF orientation
        thumb_orig = ImageOps.exif_transpose(thumb_orig)
        orig_format = thumb_orig.format or "JPEG"
        orig_size = thumb_orig.size  # (width, height)
        orig_mode = thumb_orig.mode
        icc_profile = thumb_orig.info.get("icc_profile")

        thumb_w, thumb_h = orig_size

        # Compute watermark scale relative to thumbnail width
        # Aspect ratio is strictly preserved
        target_wm_w = max(10, int(thumb_w * (scale_pct / 100.0)))
        aspect_ratio = wm_img.height / wm_img.width
        target_wm_h = max(10, int(target_wm_w * aspect_ratio))

        # Check if watermark height exceeds thumbnail height
        if target_wm_h > (thumb_h * 0.9):
            target_wm_h = int(thumb_h * 0.9)
            target_wm_w = int(target_wm_h / aspect_ratio)

        # High-quality resampling using Lanczos
        wm_resized = wm_img.resize((target_wm_w, target_wm_h), resample=Image.Resampling.LANCZOS)

        # Apply opacity if less than 100%
        if opacity_pct < 100:
            r, g, b, alpha = wm_resized.split()
            factor = max(0.0, min(1.0, opacity_pct / 100.0))
            alpha = alpha.point(lambda p: int(p * factor))
            wm_resized = Image.merge("RGBA", (r, g, b, alpha))

        # Calculate position
        pos_x, pos_y = self.calculate_position(orig_size, (target_wm_w, target_wm_h), position, padding_px)

        # Convert thumbnail to RGBA for clean alpha composition
        if orig_mode != "RGBA":
            thumb_rgba = thumb_orig.convert("RGBA")
        else:
            thumb_rgba = thumb_orig.copy()

        # Create overlay canvas
        overlay = Image.new("RGBA", orig_size, (0, 0, 0, 0))
        overlay.paste(wm_resized, (pos_x, pos_y), mask=wm_resized)

        # Composite overlay on top of original thumbnail
        composite_rgba = Image.alpha_composite(thumb_rgba, overlay)

        # Export with maximum quality matching original format
        output_buffer = io.BytesIO()
        save_params = {}
        if icc_profile:
            save_params["icc_profile"] = icc_profile

        # Determine target output format
        if orig_format.upper() in ["PNG", "WEBP"] or orig_mode == "RGBA":
            out_fmt = "PNG"
            composite_rgba.save(output_buffer, format="PNG", optimize=True, **save_params)
        else:
            out_fmt = "JPEG"
            # High-fidelity RGB conversion
            final_rgb = composite_rgba.convert("RGB")
            # Quality 98 and subsampling 0 (4:4:4) preserves maximum detail and zero compression artifacts
            final_rgb.save(
                output_buffer,
                format="JPEG",
                quality=98,
                subsampling=0,
                optimize=True,
                **save_params
            )

        return output_buffer.getvalue(), out_fmt, orig_size

    def generate_preview_thumbnail(self, custom_settings: Optional[Dict[str, Any]] = None) -> bytes:
        """
        Generates a test/preview thumbnail (1280x720 YouTube thumbnail aspect ratio)
        with the current watermark and settings to demonstrate placement to admin.
        """
        # Standard YouTube thumbnail resolution 1280x720
        canvas_w, canvas_h = 1280, 720
        canvas = Image.new("RGBA", (canvas_w, canvas_h), (24, 28, 36, 255))
        draw = ImageDraw.Draw(canvas)

        # Draw decorative background elements
        # Grid lines
        for x in range(0, canvas_w, 80):
            draw.line([(x, 0), (x, canvas_h)], fill=(36, 42, 54, 255), width=1)
        for y in range(0, canvas_h, 80):
            draw.line([(0, y), (canvas_w, y)], fill=(36, 42, 54, 255), width=1)

        # Accent box in center
        draw.rounded_rectangle(
            [160, 100, canvas_w - 160, canvas_h - 100],
            radius=16,
            fill=(30, 41, 59, 255),
            outline=(71, 85, 105, 255),
            width=2
        )

        # Mock video thumbnail elements
        draw.text((canvas_w // 2 - 190, canvas_h // 2 - 40), "PREVIEW THUMBNAIL CANVAS", fill=(241, 245, 249, 255))
        draw.text((canvas_w // 2 - 130, canvas_h // 2 + 10), "Resolution: 1280 x 720", fill=(148, 163, 184, 255))

        # Save canvas to bytes
        canvas_buffer = io.BytesIO()
        canvas.save(canvas_buffer, format="PNG")

        # Apply watermark using the specified settings
        watermarked_bytes, _, _ = self.apply_watermark(canvas_buffer.getvalue(), custom_settings=custom_settings)
        return watermarked_bytes


# Global engine instance
watermark_engine = WatermarkEngine()

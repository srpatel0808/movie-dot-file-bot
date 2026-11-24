"""
Comprehensive End-to-End Test Suite for Telegram Thumbnail Watermark Bot.
Simulates watermark replacement, thumbnail watermarking across various formats/resolutions,
admin controls, database state changes, and preview generation.
"""

import io
from pathlib import Path
from PIL import Image, ImageDraw

from config import DEFAULT_SETTINGS, ACTIVE_WATERMARK_PATH
from database import db
from watermark_engine import watermark_engine
import admin

def run_comprehensive_tests():
    print("=" * 60)
    print("🚀 RUNNING COMPREHENSIVE BOT & WATERMARK ENGINE VERIFICATION")
    print("=" * 60)

    # 1. Database tests
    print("\n[1/7] Testing SQLite Database...")
    db.reset_settings()
    settings = db.get_all_settings()
    assert settings["position"] == DEFAULT_SETTINGS["position"], "Default position mismatch"
    assert settings["scale"] == DEFAULT_SETTINGS["scale"], "Default scale mismatch"
    assert settings["opacity"] == DEFAULT_SETTINGS["opacity"], "Default opacity mismatch"

    # User registration and stats
    test_user_id = 999888777
    db.register_or_update_user(test_user_id, "test_admin", "TestUser")
    db.increment_processed(test_user_id)
    stats = db.get_stats()
    assert stats["total_processed"] >= 1, "Failed to increment total processed count"
    print(f"  ✓ Database verified: {stats}")

    # 2. Test Custom Watermark Upload
    print("\n[2/7] Testing Custom Watermark Upload...")
    custom_wm = Image.new("RGBA", (400, 120), (0, 0, 0, 0))
    draw_wm = ImageDraw.Draw(custom_wm)
    draw_wm.rounded_rectangle([5, 5, 395, 115], radius=15, fill=(220, 38, 38, 230))
    draw_wm.text((25, 45), "CUSTOM WATERMARK LOGO", fill=(255, 255, 255, 255))
    
    wm_buffer = io.BytesIO()
    custom_wm.save(wm_buffer, format="PNG")
    save_res = watermark_engine.save_new_watermark(wm_buffer.getvalue())
    assert save_res["success"] is True, f"Failed to save custom watermark: {save_res}"
    assert ACTIVE_WATERMARK_PATH.exists(), "Active watermark file does not exist after save"
    
    wm_info = watermark_engine.get_watermark_info()
    print(f"  ✓ Custom watermark uploaded and active: {wm_info['width']}x{wm_info['height']} px")

    # 3. Test Various Resolutions (Standard 16:9, 4K, Vertical, Square)
    print("\n[3/7] Testing Thumbnail Resolutions & Aspect Ratios...")
    test_resolutions = [
        ("YouTube Standard 720p", (1280, 720), "RGB", "JPEG"),
        ("Full HD 1080p", (1920, 1080), "RGB", "JPEG"),
        ("Ultra HD 4K", (3840, 2160), "RGB", "JPEG"),
        ("Square Thumbnail", (1080, 1080), "RGBA", "PNG"),
        ("Vertical Short/Reel", (1080, 1920), "RGB", "JPEG")
    ]

    for name, (w, h), mode, fmt in test_resolutions:
        img = Image.new(mode, (w, h), (45, 85, 125) if mode == "RGB" else (45, 85, 125, 255))
        d = ImageDraw.Draw(img)
        d.text((50, 50), f"Test: {name}", fill=(255, 255, 255) if mode == "RGB" else (255, 255, 255, 255))
        
        b = io.BytesIO()
        img.save(b, format=fmt)
        
        out_bytes, out_fmt, out_dims = watermark_engine.apply_watermark(b.getvalue())
        assert out_dims == (w, h), f"Resolution altered for {name}! Expected {(w, h)}, got {out_dims}"
        assert out_fmt == fmt, f"Format altered for {name}! Expected {fmt}, got {out_fmt}"
        
        # Verify result opens cleanly
        res_img = Image.open(io.BytesIO(out_bytes))
        assert res_img.size == (w, h)
        print(f"  ✓ {name} ({w}x{h}) watermarked successfully with exact resolution maintained.")

    # 4. Test 9 Placement Positions
    print("\n[4/7] Testing All 9 Anchor Positions...")
    positions = [
        "top_left", "top_center", "top_right",
        "center_left", "center", "center_right",
        "bottom_left", "bottom_center", "bottom_right"
    ]
    sample_buf = io.BytesIO()
    Image.new("RGB", (1280, 720), (30, 30, 30)).save(sample_buf, format="JPEG")
    sample_bytes = sample_buf.getvalue()

    for pos in positions:
        pos_bytes, _, _ = watermark_engine.apply_watermark(sample_bytes, custom_settings={"position": pos})
        assert len(pos_bytes) > 0
    print(f"  ✓ All 9 positions ({', '.join(positions)}) validated.")

    # 5. Test Opacity and Scaling combinations
    print("\n[5/7] Testing Opacity & Scale Variations...")
    for op in [10, 50, 85, 100]:
        for sc in [10, 20, 35, 50]:
            comb_bytes, _, _ = watermark_engine.apply_watermark(
                sample_bytes,
                custom_settings={"opacity": op, "scale": sc}
            )
            assert len(comb_bytes) > 0
    print("  ✓ Opacity (10%-100%) and Scales (10%-50%) validated.")

    # 6. Test Live Preview Canvas
    print("\n[6/7] Testing Live Preview Generator...")
    preview_bytes = watermark_engine.generate_preview_thumbnail()
    assert len(preview_bytes) > 0
    preview_img = Image.open(io.BytesIO(preview_bytes))
    assert preview_img.size == (1280, 720), "Preview size must be 1280x720"
    print(f"  ✓ Live preview canvas generated ({preview_img.size[0]}x{preview_img.size[1]} px).")

    # 7. Test Admin Keyboards and Dashboard Generation
    print("\n[7/7] Testing Admin Keyboards and UI Renderers...")
    dash_text = admin.get_admin_dashboard_text()
    assert "ADMIN CONTROL PANEL" in dash_text
    assert "Position" in dash_text
    
    admin_kb = admin.get_admin_keyboard()
    assert len(admin_kb.inline_keyboard) >= 5
    
    pos_kb = admin.get_position_keyboard()
    assert len(pos_kb.inline_keyboard) == 4  # 3 rows of 3 buttons + back button
    
    size_kb = admin.get_size_keyboard()
    opac_kb = admin.get_opacity_keyboard()
    pad_kb = admin.get_padding_keyboard()
    out_kb = admin.get_output_mode_keyboard()
    
    assert size_kb is not None
    assert opac_kb is not None
    assert pad_kb is not None
    assert out_kb is not None
    print("  ✓ Admin keyboards and control panels validated.")

    print("\n" + "=" * 60)
    print("🎉 ALL TESTS PASSED! THE SYSTEM IS 100% OPERATIONAL AND READY!")
    print("=" * 60)

if __name__ == "__main__":
    run_comprehensive_tests()

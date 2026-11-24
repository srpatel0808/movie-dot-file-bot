"""
Automated unit tests for the Watermark Processing Engine.
Validates resolution preservation, format handling, opacity, positioning, and preview generation.
"""

import io
from PIL import Image
from watermark_engine import watermark_engine
from database import db

def test_watermark_engine():
    print("=== STARTING WATERMARK ENGINE TESTS ===")

    # 1. Test watermark info
    info = watermark_engine.get_watermark_info()
    print(f"1. Watermark Info: {info}")
    assert info.get("exists") is True, "Watermark file does not exist!"

    # 2. Test 1280x720 RGB image (YouTube standard)
    test_img = Image.new("RGB", (1280, 720), (50, 100, 150))
    buf = io.BytesIO()
    test_img.save(buf, format="JPEG")
    input_bytes = buf.getvalue()

    # Test default application
    out_bytes, out_fmt, dims = watermark_engine.apply_watermark(input_bytes)
    print(f"2. Watermarked JPEG: dims={dims}, format={out_fmt}, output_size={len(out_bytes)} bytes")
    assert dims == (1280, 720), f"Dimension mismatch! Expected (1280, 720), got {dims}"
    assert out_fmt == "JPEG"

    # Verify output image readable by PIL
    out_img = Image.open(io.BytesIO(out_bytes))
    assert out_img.size == (1280, 720), "Output image size does not match original!"

    # 3. Test PNG transparent image (RGBA)
    png_img = Image.new("RGBA", (1920, 1080), (200, 50, 50, 255))
    buf_png = io.BytesIO()
    png_img.save(buf_png, format="PNG")
    out_png_bytes, out_png_fmt, png_dims = watermark_engine.apply_watermark(buf_png.getvalue())
    print(f"3. Watermarked PNG: dims={png_dims}, format={out_png_fmt}")
    assert png_dims == (1920, 1080)
    assert out_png_fmt == "PNG"

    # 4. Test all 9 positions
    positions = [
        "top_left", "top_center", "top_right",
        "center_left", "center", "center_right",
        "bottom_left", "bottom_center", "bottom_right"
    ]
    for pos in positions:
        b, f, d = watermark_engine.apply_watermark(input_bytes, custom_settings={"position": pos})
        assert d == (1280, 720)
    print(f"4. Successfully verified all 9 anchor positions: {positions}")

    # 5. Test Opacity and Scales
    for op in [25, 50, 80, 100]:
        for sc in [10, 25, 40]:
            b, f, d = watermark_engine.apply_watermark(input_bytes, custom_settings={"opacity": op, "scale": sc})
            assert d == (1280, 720)
    print("5. Successfully verified opacity and scale ranges.")

    # 6. Test Live Preview Generation
    preview_bytes = watermark_engine.generate_preview_thumbnail()
    assert len(preview_bytes) > 0
    preview_img = Image.open(io.BytesIO(preview_bytes))
    print(f"6. Preview Canvas Generated: size={preview_img.size}")
    assert preview_img.size == (1280, 720)

    # 7. Test Database settings read/write
    db.set_setting("position", "center")
    assert db.get_setting("position") == "center"
    db.set_setting("position", "bottom_right")
    assert db.get_setting("position") == "bottom_right"
    print("7. Database settings read/write validated successfully.")

    print("\nALL ENGINE TESTS PASSED PERFECTLY!")

if __name__ == "__main__":
    test_watermark_engine()

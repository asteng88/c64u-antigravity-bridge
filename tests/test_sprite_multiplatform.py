import base64
import io
import json
import urllib.request
from PIL import Image, ImageDraw
import pytest

from c64u_bridge.sprite import (
    MultiPlatformSpriteFrame,
    PlatformType,
    SpriteAnimationProject,
    get_platform_palette,
)
from c64u_bridge.sprite_import import (
    detect_and_strip_background,
    import_image_to_frames,
    quantize_to_platform,
    slice_sprite_sheet,
    smart_grid_downsample,
)
from c64u_bridge.sprite_animator import (
    generate_ai_animation_frames,
    generate_motion_cycle,
    tween_keyframes,
)
from c64u_bridge.sprite_server import start_sprite_server_background


# =============================================================================
# 1. Multi-Platform Palettes & Hardware Byte / Assembly Encoders
# =============================================================================

def test_platform_palettes():
    assert len(get_platform_palette(PlatformType.C64)) == 16
    assert len(get_platform_palette(PlatformType.ZX_SPECTRUM)) == 16
    assert len(get_platform_palette(PlatformType.ZX_NEXT)) == 256
    assert len(get_platform_palette(PlatformType.BBC_MICRO)) == 8


def test_c64_overlay_and_metasprite_bytes_and_asm():
    # Overlay mode: 24x21 = 128 bytes (64B Multicolor block + 64B Hires outline block)
    f_ov = MultiPlatformSpriteFrame(platform="c64", mode="overlay", width=24, height=21)
    f_ov.set_pixel(0, 0, 2)  # Multicolor slot 2
    f_ov.set_pixel(4, 0, 4)  # Hires overlay outline pixel
    raw_ov = f_ov.to_c64_bytes()
    assert len(raw_ov) == 128
    assert (raw_ov[0] >> 6) & 0x03 == 2
    assert (raw_ov[64] & (1 << 3)) != 0

    # 2x2 Meta-Sprite (48x42) = 256 bytes (4 x 64B hardware sprites)
    f_meta = MultiPlatformSpriteFrame(platform="c64", mode="multicolor", width=48, height=42)
    f_meta.set_pixel(30, 25, 3)
    raw_meta = f_meta.to_c64_bytes()
    assert len(raw_meta) == 256

    proj = SpriteAnimationProject(name="hero_spr", platform="c64", mode="overlay", width=24, height=21, frames=[f_ov])
    asm = proj.export_code("c64_kickass")
    assert "hero_spr_frame_0_b0:" in asm
    assert "hero_spr_frame_0_b1:" in asm
    assert "sta $d028" in asm

    py_bank = proj.export_code("c64_python_bank")
    assert "GROUPS =" in py_bank

    run_asm = proj.export_code("c64_runnable_prg_asm")
    assert "BasicUpstart2(start)" in run_asm


def test_zx_spectrum_bytes_and_sjasm():
    # 16x16 ULA attribute sprite -> 32 bitmap bytes, 32 mask bytes, 4 attribute bytes (2x2 8x8 cells)
    f = MultiPlatformSpriteFrame(platform="zx_spectrum", mode="attr_8x8", width=16, height=16)
    f.set_pixel(0, 0, 10)  # Bright Red in cell (0,0)
    f.set_pixel(8, 8, 12)  # Bright Green in cell (1,1)
    bmp, msk, attrs = f.to_zx_spectrum_bytes()
    assert len(bmp) == 32
    assert len(msk) == 32
    assert len(attrs) == 4
    assert bmp[0] & 0x80 == 0x80
    assert msk[0] & 0x80 == 0x00  # Opaque pixel has mask bit 0

    proj = SpriteAnimationProject(name="zx_hero", platform="zx_spectrum", mode="attr_8x8", width=16, height=16, frames=[f])
    sjasm = proj.export_code("zx_sjasm")
    assert "DEFB" in sjasm
    assert "zx_hero_frame_0_attrs:" in sjasm


def test_zx_next_8bit_and_4bit_bytes_and_asm():
    # 16x16 8-bit Next sprite = 256 bytes ($E3 transparent)
    f8 = MultiPlatformSpriteFrame(platform="zx_next", mode="next_8bit", width=16, height=16)
    f8.set_pixel(0, 0, 0)     # Transparent -> $E3
    f8.set_pixel(1, 0, 0xFC)  # Yellow
    raw8 = f8.to_zx_next_bytes()
    assert len(raw8) == 256
    assert raw8[0] == 0xE3
    assert raw8[1] == 0xFC

    # 16x16 4-bit Next sprite = 128 bytes (2 nibbles per byte)
    f4 = MultiPlatformSpriteFrame(platform="zx_next", mode="next_4bit", width=16, height=16)
    f4.set_pixel(0, 0, 3)
    f4.set_pixel(1, 0, 12)
    raw4 = f4.to_zx_next_bytes()
    assert len(raw4) == 128
    assert raw4[0] == (3 << 4) | 12

    proj = SpriteAnimationProject(name="next_spr", platform="zx_next", mode="next_8bit", width=16, height=16, frames=[f8])
    asm = proj.export_code("next_sjasm")
    assert "NEXTREG $15" in asm
    assert "SPRITE_PATTERN_PORT" in asm


def test_bbc_micro_mode1_mode2_mode4_interleaved_bytes():
    # Mode 2: 24x21 grid with step_x=2 -> 12 logical double-wide pixels per row -> 6 bytes/row * 21 rows = 126 bytes
    f_m2 = MultiPlatformSpriteFrame(platform="bbc_micro", mode="mode2", width=24, height=21, color_slots=list(range(8)))
    # Set left pixel (col 0..1) = 5 (0b0101, Magenta), right pixel (col 2..3) = 3 (0b0011, Yellow)
    f_m2.set_pixel(0, 0, 5)
    f_m2.set_pixel(2, 0, 3)
    raw_m2 = f_m2.to_bbc_micro_bytes()
    assert len(raw_m2) == 6 * 21
    # Expected interleaved byte for c0=5 (0101), c1=3 (0011):
    # b7=0, b6=0, b5=1, b4=0, b3=0, b2=1, b1=1, b0=1 -> 0b00100111 = 0x27
    assert raw_m2[0] == 0x27

    # Mode 1: 16x16, 4 pixels per byte -> 4 bytes/row * 16 rows = 64 bytes
    f_m1 = MultiPlatformSpriteFrame(platform="bbc_micro", mode="mode1", width=16, height=16, color_slots=[0, 1, 3, 7])
    f_m1.set_pixel(0, 0, 3)  # Logical 3 (binary 11) -> sets bit 7 and bit 3 -> 0x88
    raw_m1 = f_m1.to_bbc_micro_bytes()
    assert len(raw_m1) == 64
    assert raw_m1[0] == 0x88

    proj = SpriteAnimationProject(name="bbc_ship", platform="bbc_micro", mode="mode1", width=16, height=16, frames=[f_m1])
    beeb_asm = proj.export_code("bbc_beebasm")
    assert "EQUB" in beeb_asm
    assert ".bbc_ship_palette" in beeb_asm


# =============================================================================
# 2. AI Sprite De-Fading, Sheet Slicer & Perceptual CIELAB Quantization
# =============================================================================

def test_ai_sprite_defading_and_cielab_quantizer():
    # Create a synthetic 96x84 image simulating an AI-generated sprite with:
    # - A solid dark navy background (#080A14)
    # - A faded anti-aliased halo ring around the sprite
    # - A bright red and yellow interior body
    img = Image.new("RGBA", (96, 84), (8, 10, 20, 255))
    draw = ImageDraw.Draw(img)
    # Faded outer halo ring
    draw.rectangle([18, 14, 78, 70], fill=(45, 20, 30, 255))
    # Crisp red main body
    draw.rectangle([22, 18, 74, 66], fill=(220, 20, 20, 255))
    # Yellow cockpit highlight
    draw.rectangle([36, 26, 60, 44], fill=(245, 240, 80, 255))

    cleaned = detect_and_strip_background(img, bg_tolerance=38.0, alpha_cutoff=128, defade_strength=0.75, auto_crop=False)
    px = cleaned.load()
    # Corners must be stripped to full transparency (alpha == 0)
    assert px[0, 0][3] == 0
    assert px[95, 83][3] == 0
    # Center must remain opaque
    assert px[48, 40][3] == 255

    # Downsample and quantize to C64 Multicolor (max 3 opaque colors + transparent)
    grid_rgb = smart_grid_downsample(cleaned, target_w=24, target_h=21, step_x=2, sample_mode="dominant")
    c64_frame = quantize_to_platform(grid_rgb, platform="c64", mode="multicolor")
    used_slots = {v for row in c64_frame.grid for v in row}
    assert 0 in used_slots
    assert all(0 <= v <= 3 for v in used_slots)
    # Verify double-wide pixel alignment on every row
    for y in range(21):
        for x in range(0, 24, 2):
            assert c64_frame.grid[y][x] == c64_frame.grid[y][x + 1]

    # Quantize same image to ZX Spectrum attr_8x8 and verify max 2 colors per 8x8 block
    zx_grid = smart_grid_downsample(cleaned, target_w=16, target_h=16, step_x=1)
    zx_frame = quantize_to_platform(zx_grid, platform="zx_spectrum", mode="attr_8x8")
    for cy in range(2):
        for cx in range(2):
            cell_colors = {
                zx_frame.grid[cy * 8 + dy][cx * 8 + dx]
                for dy in range(8)
                for dx in range(8)
                if zx_frame.grid[cy * 8 + dy][cx * 8 + dx] > 0
            }
            assert len(cell_colors) <= 2


def test_sprite_sheet_slicer_grid_and_islands():
    # Create a 3-frame horizontal sprite sheet (72x24)
    sheet = Image.new("RGBA", (72, 24), (0, 0, 0, 0))
    draw = ImageDraw.Draw(sheet)
    draw.rectangle([4, 4, 18, 18], fill=(255, 0, 0, 255))
    draw.rectangle([28, 4, 42, 18], fill=(0, 255, 0, 255))
    draw.rectangle([52, 4, 66, 18], fill=(0, 128, 255, 255))

    grid_slices = slice_sprite_sheet(sheet, rows=1, cols=3, auto_detect_islands=False)
    assert len(grid_slices) == 3

    island_slices = slice_sprite_sheet(sheet, auto_detect_islands=True)
    assert len(island_slices) == 3


# =============================================================================
# 3. Smooth Animation Generation (Keyframe Tweening & Motion Presets)
# =============================================================================

def test_keyframe_tweening_and_motion_presets():
    fa = MultiPlatformSpriteFrame(platform="c64", mode="multicolor", width=24, height=21)
    fb = MultiPlatformSpriteFrame(platform="c64", mode="multicolor", width=24, height=21)
    for y in range(6, 14):
        for x in range(2, 10, 2):
            fa.set_pixel(x, y, 2)
        for x in range(12, 20, 2):
            fb.set_pixel(x, y, 2)

    tweens = tween_keyframes(fa, fb, num_inbetweens=3)
    assert len(tweens) == 3
    # Centroid X should progress monotonically from fa toward fb
    def mean_x(f):
        xs = [x for y in range(f.height) for x in range(f.width) if f.grid[y][x] > 0]
        return sum(xs) / len(xs)

    c0 = mean_x(fa)
    c1 = mean_x(tweens[0])
    c2 = mean_x(tweens[1])
    c3 = mean_x(tweens[2])
    c4 = mean_x(fb)
    assert c0 < c1 <= c2 <= c3 < c4

    for preset in ("walk_cycle", "hover_bob", "rotate_bank", "pulse_breathe", "explode_dissolve"):
        seq = generate_motion_cycle(fa, preset=preset, num_frames=4, intensity=1.0)
        assert len(seq) == 4
        assert any(seq[0].grid != seq[i].grid for i in range(1, 4))

    # Test AI fallback generator (works offline without GEMINI_API_KEY)
    ai_frames, note = generate_ai_animation_frames(fa, prompt="smooth walk cycle", num_frames=4)
    assert len(ai_frames) == 4
    assert len(note) > 0


# =============================================================================
# 4. Local Studio HTTP Server API Endpoints
# =============================================================================

def test_sprite_studio_http_server():
    server, base_url = start_sprite_server_background(port=0)
    try:
        # 1. GET /api/specs
        with urllib.request.urlopen(base_url + "api/specs", timeout=5) as resp:
            specs = json.loads(resp.read().decode("utf-8"))
        assert specs["ok"] is True
        assert "c64" in specs["platforms"]
        assert "zx_spectrum" in specs["platforms"]
        assert "zx_next" in specs["platforms"]
        assert "bbc_micro" in specs["platforms"]

        # 2. POST /api/import-image
        img = Image.new("RGBA", (24, 21), (0, 0, 0, 255))
        draw = ImageDraw.Draw(img)
        draw.ellipse([4, 3, 20, 17], fill=(255, 255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64_img = base64.b64encode(buf.getvalue()).decode("ascii")

        req_import = urllib.request.Request(
            base_url + "api/import-image",
            data=json.dumps({
                "image_b64": b64_img,
                "platform": "bbc_micro",
                "mode": "mode2",
                "width": 24,
                "height": 21,
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req_import, timeout=5) as resp:
            imp_data = json.loads(resp.read().decode("utf-8"))
        assert imp_data["ok"] is True
        assert imp_data["count"] == 1
        frame_dict = imp_data["frames"][0]

        # 3. POST /api/generate-animation
        req_anim = urllib.request.Request(
            base_url + "api/generate-animation",
            data=json.dumps({
                "type": "preset",
                "preset": "hover_bob",
                "base_frame": frame_dict,
                "num_frames": 4,
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req_anim, timeout=5) as resp:
            anim_data = json.loads(resp.read().decode("utf-8"))
        assert anim_data["ok"] is True
        assert len(anim_data["frames"]) == 4

        # 4. POST /api/export
        req_exp = urllib.request.Request(
            base_url + "api/export",
            data=json.dumps({
                "project": {
                    "name": "test_bbc",
                    "platform": "bbc_micro",
                    "mode": "mode2",
                    "width": 24,
                    "height": 21,
                    "fps": 8,
                    "frames": anim_data["frames"],
                },
                "format": "bbc_beebasm",
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req_exp, timeout=5) as resp:
            exp_data = json.loads(resp.read().decode("utf-8"))
        assert exp_data["ok"] is True
        assert "EQUB" in exp_data["code"]
        assert len(exp_data["gif_b64"]) > 20
        assert len(exp_data["png_sheet_b64"]) > 20
    finally:
        server.shutdown()

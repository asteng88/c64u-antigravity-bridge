import pytest
from c64u_bridge.sprite import Sprite, SpriteMode, SpriteTool, C64Color


def test_sprite_initialization():
    s = Sprite()
    assert s.WIDTH == 24
    assert s.HEIGHT == 21
    assert s.RAW_BYTE_SIZE == 64
    assert s.mode == SpriteMode.HIRES
    # All pixels initially 0
    assert all(all(val == 0 for val in row) for row in s.grid)


def test_sprite_set_and_get_pixel_hires():
    s = Sprite(mode=SpriteMode.HIRES)
    s.set_pixel(5, 10, 1)
    assert s.get_pixel(5, 10) == 1
    assert s.get_pixel(6, 10) == 0

    s.set_pixel(5, 10, 0)
    assert s.get_pixel(5, 10) == 0


def test_sprite_set_and_get_pixel_multicolor():
    s = Sprite(mode=SpriteMode.MULTICOLOR)
    # Setting pixel at (4, 8) in multicolor sets both 4 and 5 (double width)
    s.set_pixel(4, 8, 3)
    assert s.get_pixel(4, 8) == 3
    assert s.get_pixel(5, 8) == 3
    assert s.get_pixel(6, 8) == 0


def test_sprite_clear_and_invert():
    s = Sprite(mode=SpriteMode.HIRES)
    s.set_pixel(0, 0, 1)
    s.set_pixel(1, 1, 1)
    s.clear(0)
    assert s.get_pixel(0, 0) == 0

    s.set_pixel(2, 2, 1)
    s.invert()
    assert s.get_pixel(2, 2) == 0
    assert s.get_pixel(0, 0) == 1


def test_sprite_flood_fill():
    s = Sprite(mode=SpriteMode.HIRES)
    # Draw a 5x5 bounding box
    for x in range(2, 7):
        s.set_pixel(x, 2, 1)
        s.set_pixel(x, 6, 1)
    for y in range(2, 7):
        s.set_pixel(2, y, 1)
        s.set_pixel(6, y, 1)

    # Flood fill inside (4, 4)
    s.flood_fill(4, 4, 1)
    assert s.get_pixel(4, 4) == 1
    assert s.get_pixel(3, 3) == 1
    assert s.get_pixel(5, 5) == 1
    # Outside should still be 0
    assert s.get_pixel(0, 0) == 0
    assert s.get_pixel(10, 10) == 0


def test_sprite_shift_and_flip():
    s = Sprite(mode=SpriteMode.HIRES)
    s.set_pixel(5, 5, 1)

    s.shift(2, 3)
    assert s.get_pixel(5, 5) == 0
    assert s.get_pixel(7, 8) == 1

    s.flip_horizontal()
    # Width is 24, mirrored index is 23 - 7 = 16
    assert s.get_pixel(16, 8) == 1

    s.flip_vertical()
    # Height is 21, mirrored index is 20 - 8 = 12
    assert s.get_pixel(16, 12) == 1


def test_sprite_bytes_roundtrip():
    s = Sprite(mode=SpriteMode.HIRES)
    s.set_pixel(0, 0, 1)
    s.set_pixel(7, 0, 1) # First byte should be %10000001 = $81
    raw = s.to_bytes()
    assert len(raw) == 64
    assert raw[0] == 0x81
    assert raw[-1] == 0x00 # 64th byte padding

    s2 = Sprite(mode=SpriteMode.HIRES)
    s2.load_bytes(raw)
    assert s2.get_pixel(0, 0) == 1
    assert s2.get_pixel(7, 0) == 1
    assert s2.get_pixel(1, 0) == 0


def test_sprite_asm_generation():
    s = Sprite(mode=SpriteMode.HIRES)
    s.set_pixel(0, 0, 1)
    asm = s.to_kickass_asm(label="my_sprite")
    assert "my_sprite:" in asm
    assert ".align $40" in asm
    assert ".byte %10000000" in asm
    assert "Row  0" in asm
    assert ".byte $00 // Byte 64: Padding" in asm

    acme = s.to_acme_asm(label="acme_sprite")
    assert "acme_sprite" in acme
    assert "!byte %10000000" in acme

    hex_asm = s.to_hex_asm(label="hex_sprite")
    assert "hex_sprite:" in hex_asm
    assert ".byte $80, $00, $00" in hex_asm


def test_multicolor_airwolf_and_vic2_setup():
    from c64u_bridge.sprite import create_multicolor_airwolf_sprite
    s = create_multicolor_airwolf_sprite()
    assert s.mode == SpriteMode.MULTICOLOR
    assert s.color == C64Color.WHITE.value
    assert s.extra_color_1 == C64Color.RED.value
    assert s.extra_color_2 == C64Color.YELLOW.value

    # Verify multiple distinct color values within same sprite boundary
    values = set()
    for row in s.grid:
        for val in row:
            values.add(val)
    # Must have 0 (bg), 1 (red), 2 (white), 3 (yellow)
    assert 0 in values
    assert 1 in values
    assert 2 in values
    assert 3 in values

    # Test VIC-II setup assembly generation
    vic_asm = s.get_vic2_setup_asm(0)
    assert "sta $d027 + 0" in vic_asm # Sprite 0 color
    assert "sta $d025" in vic_asm     # Extra Color 1
    assert "sta $d026" in vic_asm     # Extra Color 2
    assert "sta $d01c" in vic_asm     # Multicolor register


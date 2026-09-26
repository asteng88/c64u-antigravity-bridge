"""
Commodore 64 Sprite Data Model and Code Generator.

Supports 24x21 pixel sprites in both High-Resolution (1 bit/pixel, 24x21)
and Multicolor (2 bits/pixel, 12x21 double-wide pixels) modes.
Provides raster drawing primitives (pen, erase, flood fill, shift, flip, invert)
and real-time generation of 6502 assembly (KickAssembler, ACME, Hex).
"""

from __future__ import annotations

from collections import deque
from enum import Enum
from typing import List, Tuple, Optional


class C64Color(int, Enum):
    """The 16 standard Commodore 64 palette colors."""
    BLACK = 0
    WHITE = 1
    RED = 2
    CYAN = 3
    PURPLE = 4
    GREEN = 5
    BLUE = 6
    YELLOW = 7
    ORANGE = 8
    BROWN = 9
    LIGHT_RED = 10
    DARK_GREY = 11
    GREY = 12
    LIGHT_GREEN = 13
    LIGHT_BLUE = 14
    LIGHT_GREY = 15

    @property
    def hex_code(self) -> str:
        """Standard C64 RGB hex color representation."""
        hex_map = {
            0: "#000000",
            1: "#ffffff",
            2: "#880000",
            3: "#aaffee",
            4: "#cc44cc",
            5: "#00cc55",
            6: "#0000aa",
            7: "#eeee77",
            8: "#dd8855",
            9: "#664400",
            10: "#ff7777",
            11: "#333333",
            12: "#777777",
            13: "#aaff66",
            14: "#0088ff",
            15: "#bbbbbb",
        }
        return hex_map[self.value]

    @property
    def label(self) -> str:
        names = {
            0: "Black",
            1: "White",
            2: "Red",
            3: "Cyan",
            4: "Purple",
            5: "Green",
            6: "Blue",
            7: "Yellow",
            8: "Orange",
            9: "Brown",
            10: "Lt Red",
            11: "Dk Grey",
            12: "Grey",
            13: "Lt Green",
            14: "Lt Blue",
            15: "Lt Grey",
        }
        return names[self.value]


class SpriteMode(str, Enum):
    HIRES = "hires"          # 24x21 pixels, 1 bit/pixel (0: transparent/bg, 1: sprite color)
    MULTICOLOR = "multicolor"# 12x21 pixels (double width), 2 bits/pixel:
                             # %00 = transparent / screen bg
                             # %01 = sprite extra color 1 ($D025)
                             # %10 = sprite individual color ($D027-$D02E)
                             # %11 = sprite extra color 2 ($D026)


class SpriteTool(str, Enum):
    PEN = "pen"
    ERASER = "eraser"
    FILL = "fill"


class Sprite:
    """
    Representation of a single 24x21 Commodore 64 hardware sprite (64 bytes).
    """

    WIDTH = 24
    HEIGHT = 21
    RAW_BYTE_SIZE = 64  # 63 data bytes + 1 padding byte

    def __init__(
        self,
        mode: SpriteMode = SpriteMode.HIRES,
        color: int = C64Color.WHITE.value,
        extra_color_1: int = C64Color.RED.value,
        extra_color_2: int = C64Color.YELLOW.value,
        bg_color: int = C64Color.BLACK.value,
    ):
        self.mode = mode
        self.color = color
        self.extra_color_1 = extra_color_1
        self.extra_color_2 = extra_color_2
        self.bg_color = bg_color
        # 21 rows of 24 pixels (values 0..3)
        self.grid: List[List[int]] = [[0 for _ in range(self.WIDTH)] for _ in range(self.HEIGHT)]

    # -------------------------------------------------------------------------
    # Pixel Manipulation
    # -------------------------------------------------------------------------

    def set_pixel(self, x: int, y: int, value: int) -> None:
        """Set pixel value at (x, y). In multicolor, sets double-wide pair."""
        if not (0 <= x < self.WIDTH and 0 <= y < self.HEIGHT):
            return
        if self.mode == SpriteMode.MULTICOLOR:
            # Snap to even column pair (0-1, 2-3, ...)
            even_x = (x // 2) * 2
            self.grid[y][even_x] = value & 0x03
            self.grid[y][even_x + 1] = value & 0x03
        else:
            self.grid[y][x] = 1 if value else 0

    def get_pixel(self, x: int, y: int) -> int:
        """Get pixel value at (x, y)."""
        if not (0 <= x < self.WIDTH and 0 <= y < self.HEIGHT):
            return 0
        return self.grid[y][x]

    def clear(self, fill_value: int = 0) -> None:
        """Clear all pixels to fill_value."""
        val = fill_value if self.mode == SpriteMode.MULTICOLOR else (1 if fill_value else 0)
        for y in range(self.HEIGHT):
            for x in range(self.WIDTH):
                self.grid[y][x] = val

    def invert(self) -> None:
        """Invert all pixels."""
        if self.mode == SpriteMode.HIRES:
            for y in range(self.HEIGHT):
                for x in range(self.WIDTH):
                    self.grid[y][x] = 0 if self.grid[y][x] else 1
        else:
            # In multicolor, 0 <-> 2 (bg <-> main sprite color)
            for y in range(self.HEIGHT):
                for x in range(self.WIDTH):
                    v = self.grid[y][x]
                    if v == 0:
                        self.grid[y][x] = 2
                    elif v == 2:
                        self.grid[y][x] = 0

    def flood_fill(self, start_x: int, start_y: int, new_val: int) -> None:
        """4-directional flood fill algorithm."""
        if not (0 <= start_x < self.WIDTH and 0 <= start_y < self.HEIGHT):
            return

        target_val = self.get_pixel(start_x, start_y)
        if target_val == new_val:
            return

        step_x = 2 if self.mode == SpriteMode.MULTICOLOR else 1
        norm_x = (start_x // step_x) * step_x

        queue = deque([(norm_x, start_y)])
        visited = set()

        while queue:
            cx, cy = queue.popleft()
            if (cx, cy) in visited:
                continue
            if not (0 <= cx < self.WIDTH and 0 <= cy < self.HEIGHT):
                continue
            if self.get_pixel(cx, cy) != target_val:
                continue

            visited.add((cx, cy))
            self.set_pixel(cx, cy, new_val)

            # Check neighbors
            for dx, dy in [(-step_x, 0), (step_x, 0), (0, -1), (0, 1)]:
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < self.WIDTH and 0 <= ny < self.HEIGHT and (nx, ny) not in visited:
                    if self.get_pixel(nx, ny) == target_val:
                        queue.append((nx, ny))

    def shift(self, dx: int, dy: int, wrap: bool = False) -> None:
        """Shift sprite content horizontally and/or vertically."""
        if self.mode == SpriteMode.MULTICOLOR:
            dx = (dx // 2) * 2  # maintain double-width pixel alignment

        new_grid = [[0 for _ in range(self.WIDTH)] for _ in range(self.HEIGHT)]
        for y in range(self.HEIGHT):
            for x in range(self.WIDTH):
                val = self.grid[y][x]
                if not val:
                    continue
                nx = x + dx
                ny = y + dy
                if wrap:
                    nx %= self.WIDTH
                    ny %= self.HEIGHT
                    new_grid[ny][nx] = val
                else:
                    if 0 <= nx < self.WIDTH and 0 <= ny < self.HEIGHT:
                        new_grid[ny][nx] = val
        self.grid = new_grid

    def flip_horizontal(self) -> None:
        """Mirror sprite along the vertical axis."""
        if self.mode == SpriteMode.MULTICOLOR:
            for y in range(self.HEIGHT):
                # 12 pairs of pixels
                pairs = [self.grid[y][x * 2] for x in range(12)]
                pairs.reverse()
                for x in range(12):
                    self.grid[y][x * 2] = pairs[x]
                    self.grid[y][x * 2 + 1] = pairs[x]
        else:
            for y in range(self.HEIGHT):
                self.grid[y].reverse()

    def flip_vertical(self) -> None:
        """Mirror sprite along the horizontal axis."""
        self.grid.reverse()

    # -------------------------------------------------------------------------
    # Serialization & 6502 Assembly Generation
    # -------------------------------------------------------------------------

    def to_bytes(self) -> bytes:
        """
        Convert sprite grid to the 64-byte Commodore 64 VIC-II hardware format:
        21 rows * 3 bytes per row = 63 bytes, plus 1 trailing padding byte ($00).
        """
        raw = bytearray()
        for y in range(self.HEIGHT):
            for byte_idx in range(3):
                b = 0
                if self.mode == SpriteMode.MULTICOLOR:
                    # 4 double-pixels per byte
                    for p in range(4):
                        x = byte_idx * 8 + p * 2
                        val = self.grid[y][x] & 0x03
                        shift = (3 - p) * 2
                        b |= (val << shift)
                else:
                    # 8 pixels per byte
                    for bit in range(8):
                        x = byte_idx * 8 + bit
                        if self.grid[y][x]:
                            b |= (1 << (7 - bit))
                raw.append(b)
        # 64th byte is padding
        raw.append(0)
        return bytes(raw)

    def load_bytes(self, data: bytes) -> None:
        """Load sprite from 63 or 64 bytes of raw C64 sprite data."""
        if len(data) < 63:
            raise ValueError(f"Expected at least 63 bytes for sprite data, got {len(data)}")

        for y in range(self.HEIGHT):
            for byte_idx in range(3):
                b = data[y * 3 + byte_idx]
                if self.mode == SpriteMode.MULTICOLOR:
                    for p in range(4):
                        shift = (3 - p) * 2
                        val = (b >> shift) & 0x03
                        x = byte_idx * 8 + p * 2
                        self.grid[y][x] = val
                        self.grid[y][x + 1] = val
                else:
                    for bit in range(8):
                        val = 1 if (b & (1 << (7 - bit))) else 0
                        x = byte_idx * 8 + bit
                        self.grid[y][x] = val

    def to_kickass_asm(self, label: str = "sprite_data", include_comments: bool = True) -> str:
        """
        Generate KickAssembler 6502 source code with binary representation (%xxxxxxxx).
        Includes visual row comments and hardware setup directives.
        """
        raw = self.to_bytes()
        mode_str = "MULTICOLOR (2-bit)" if self.mode == SpriteMode.MULTICOLOR else "HIGH-RESOLUTION (1-bit)"
        lines = [
            f"// ====================================================================",
            f"// Commodore 64 Sprite: {label}",
            f"// Mode: {mode_str} | Dimensions: 24x21 | Size: 64 bytes",
            f"// Colors: Main={self.color} (MC1={self.extra_color_1}, MC2={self.extra_color_2})",
            f"// ====================================================================",
            f".align $40 // Sprites must align to 64-byte boundaries",
            f"{label}:",
        ]

        for y in range(self.HEIGHT):
            b0 = raw[y * 3 + 0]
            b1 = raw[y * 3 + 1]
            b2 = raw[y * 3 + 2]
            comment = f" // Row {y:2d}" if include_comments else ""
            lines.append(f"    .byte %{b0:08b}, %{b1:08b}, %{b2:08b}{comment}")

        lines.append(f"    .byte $00 // Byte 64: Padding")
        return "\n".join(lines) + "\n"

    def get_vic2_setup_asm(self, sprite_index: int = 0) -> str:
        """Generate 6502 assembly snippet to configure VIC-II color registers for this sprite."""
        bitmask = 1 << (sprite_index & 7)
        c_main = C64Color(self.color).label
        lines = [
            f"// --- VIC-II Color & Mode Setup for Sprite {sprite_index} ---",
            f"setup_sprite_{sprite_index}_colors:",
            f"    lda #${self.color:02x}",
            f"    sta $d027 + {sprite_index} // Sprite {sprite_index} Color: {c_main}",
        ]
        if self.mode == SpriteMode.MULTICOLOR:
            c_mc1 = C64Color(self.extra_color_1).label
            c_mc2 = C64Color(self.extra_color_2).label
            lines.extend([
                f"    lda #${self.extra_color_1:02x}",
                f"    sta $d025     // Sprite Extra Color 1: {c_mc1}",
                f"    lda #${self.extra_color_2:02x}",
                f"    sta $d026     // Sprite Extra Color 2: {c_mc2}",
                f"    lda $d01c",
                f"    ora #%{bitmask:08b} // Enable Multicolor for Sprite {sprite_index}",
                f"    sta $d01c",
            ])
        else:
            lines.extend([
                f"    lda $d01c",
                f"    and #%{(~bitmask) & 0xFF:08b} // Set High-Resolution (1-bit) for Sprite {sprite_index}",
                f"    sta $d01c",
            ])
        lines.append("    rts")
        return "\n".join(lines) + "\n"

    def to_acme_asm(self, label: str = "sprite_data") -> str:
        """Generate ACME assembler compatible syntax (!byte %xxxxxxxx)."""
        raw = self.to_bytes()
        lines = [
            f"; Commodore 64 Sprite: {label} (24x21)",
            f"!align 63, 0",
            f"{label}",
        ]
        for y in range(self.HEIGHT):
            b0 = raw[y * 3 + 0]
            b1 = raw[y * 3 + 1]
            b2 = raw[y * 3 + 2]
            lines.append(f"    !byte %{b0:08b}, %{b1:08b}, %{b2:08b} ; Row {y:2d}")
        lines.append(f"    !byte $00 ; Padding")
        return "\n".join(lines) + "\n"

    def to_hex_asm(self, label: str = "sprite_data") -> str:
        """Generate concise hexadecimal byte definition."""
        raw = self.to_bytes()
        lines = [f"{label}:"]
        for y in range(self.HEIGHT):
            b0, b1, b2 = raw[y * 3 : y * 3 + 3]
            lines.append(f"    .byte ${b0:02x}, ${b1:02x}, ${b2:02x} // Row {y:2d}")
        lines.append(f"    .byte $00 // Padding")
        return "\n".join(lines) + "\n"

    def render_ascii(self) -> str:
        """Render a text-based preview of the sprite."""
        lines = []
        for y in range(self.HEIGHT):
            row_chars = []
            for x in range(self.WIDTH):
                v = self.grid[y][x]
                if v == 0:
                    row_chars.append("·")
                elif v == 1:
                    row_chars.append("■")
                elif v == 2:
                    row_chars.append("◆")
                else:
                    row_chars.append("▲")
            lines.append("".join(row_chars))
        return "\n".join(lines)


def copy_to_clipboard(text: str) -> bool:
    """Copy text to system clipboard across Windows, macOS, and Linux."""
    import shutil
    import subprocess
    import sys

    try:
        if sys.platform == "win32":
            subprocess.run(["clip"], input=text.encode("utf-8"), check=True)
            return True
        elif sys.platform == "darwin" and shutil.which("pbcopy"):
            subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
            return True
        elif shutil.which("xclip"):
            subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode("utf-8"), check=True)
            return True
        elif shutil.which("wl-copy"):
            subprocess.run(["wl-copy"], input=text.encode("utf-8"), check=True)
            return True
    except Exception:
        pass
    return False


def create_airwolf_sprite() -> Sprite:
    """Create a default sleek supersonic helicopter sprite in Hires mode."""
    s = Sprite(mode=SpriteMode.HIRES, color=C64Color.WHITE.value)
    rows = [
        "000000000000000000000000",
        "000001111111111111000000",
        "000000000011000000000000",
        "000000000011000000000000",
        "000000001111110000000000",
        "000001111111111100000000",
        "000111111111111111000000",
        "001111001111111111110000",
        "011111001111111111111100",
        "111111111111111111111110",
        "111111111111111111111111",
        "011111111111111111111110",
        "001111111111111111110000",
        "000011111111111111000000",
        "000000111111111100000000",
        "000000001100001100000000",
        "000000001100001100000000",
        "000000111111111111000000",
        "000000000000000000000000",
        "000000000000000000000000",
        "000000000000000000000000",
    ]
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch == "1":
                s.set_pixel(x, y, 1)
    return s


def create_multicolor_airwolf_sprite() -> Sprite:
    """
    Create a sleek Airwolf helicopter using 3 distinct simultaneous colors
    within the same 24x21 VIC-II sprite boundary:
    0 = %00 Transparent / Background ($D021)
    1 = %01 Extra Color 1 ($D025): Red ($02) - ADF weapon pods, turbos, markings
    2 = %10 Individual Sprite Color ($D027): White ($01) - Fuselage body, rotor, nose
    3 = %11 Extra Color 2 ($D026): Yellow ($07) - Cockpit windshield & turbine flare
    """
    s = Sprite(
        mode=SpriteMode.MULTICOLOR,
        color=C64Color.WHITE.value,
        extra_color_1=C64Color.RED.value,
        extra_color_2=C64Color.YELLOW.value,
        bg_color=C64Color.BLACK.value,
    )
    mc_rows = [
        "000000000000",
        "002222222200",  # Rotor blade (White 2)
        "000002000000",  # Rotor mast (White 2)
        "000002000000",  # Rotor mast (White 2)
        "000022200000",  # Engine housing (White 2)
        "000222220000",  # Fuselage upper spine
        "002233222000",  # Cockpit windshield (Yellow 3) + Fuselage (White 2)
        "022333222200",  # Canopy (Yellow 3)
        "222222222210",  # Fuselage (White 2) + ADF Pod (Red 1)
        "222222221111",  # Shark nose + 30mm chain guns (Red 1)
        "222222222220",  # Sleek underbody
        "022222222200",  # Lower fuselage
        "002222222000",  # Tailboom root
        "000222220000",  # Tapered tailboom
        "000022200000",  # Tailboom
        "000001000000",  # Tactical sensor / weapon (Red 1)
        "000011100000",  # Retractable landing skids (Red 1)
        "000000000000",
        "000000000000",
        "000000000000",
        "000000000000",
    ]
    for y, r in enumerate(mc_rows):
        for x, ch in enumerate(r):
            val = int(ch)
            if val > 0:
                s.set_pixel(x * 2, y, val)
    return s


def create_commodore_logo_sprite() -> Sprite:
    """
    Create the iconic Commodore (C=) 'chicken lips' logo as a 24x21 multicolor sprite:
    0 = %00 Transparent / Screen BG ($D021): Black ($00)
    1 = %01 Extra Color 1 ($D025): Red ($02)
    2 = %10 Individual Sprite Color ($D027): Light Grey ($0F)
    3 = %11 Extra Color 2 ($D026): Blue ($06)
    """
    s = Sprite(
        mode=SpriteMode.MULTICOLOR,
        color=C64Color.LIGHT_GREY.value,
        extra_color_1=C64Color.RED.value,
        extra_color_2=C64Color.BLUE.value,
        bg_color=C64Color.BLACK.value,
    )
    mc_rows = [
        "000222220000",
        "022233332220",
        "223333333320",
        "233333333320",
        "233322223320",
        "233220002222",
        "233200023332",
        "233200023322",
        "233200023220",
        "233200002200",
        "233200021220",
        "233200021122",
        "233200021112",
        "233200002222",
        "233220023320",
        "233322223320",
        "233333333320",
        "223333332220",
        "022233332000",
        "000022222000",
        "000000000000",
    ]
    for y, r in enumerate(mc_rows):
        for x, ch in enumerate(r):
            val = int(ch)
            if val > 0:
                s.set_pixel(x * 2, y, val)
    return s




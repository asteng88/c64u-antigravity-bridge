"""
Retro Commodore 64 Themes, Bundled Bitmap Font Registration,
and Attribution Credits for the C64U Antigravity Bridge Lookalike Studio.

Font Attribution & Credits:
---------------------------
- `PetMe64.ttf` ("Pet Me 64") was created and produced by
  **Kreative Korporation / Kreative Software** (Rebecca G. Bettencourt)
  (<https://www.kreativekorp.com/software/fonts/c64/>) and is distributed free of
  charge under the **Kreative Software Relay Fonts Free Use License version 1.2f**.
- The license notice (`LICENSE-Kreative-FreeUse-1.2f.txt`) is included verbatim
  in `src/c64u_bridge/assets/fonts/`.
- Font files and notices were sourced from the **Faerie** project's bundled-font
  collection (<https://github.com/KiwiGeek/Faerie/tree/master/src/Faerie.Terminal.Avalonia/Assets/Fonts>)
  and shared with the sister **BackMeUpScotty** retro utility project.
"""

from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path
from typing import Optional

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:  # pragma: no cover
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore
    ImageFilter = None  # type: ignore


def _resolve_assets_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass_assets = Path(getattr(sys, "_MEIPASS")) / "c64u_bridge" / "assets"
        if meipass_assets.is_dir():
            return meipass_assets
    return Path(__file__).resolve().parent / "assets"


ASSETS_DIR = _resolve_assets_dir()
FONTS_DIR = ASSETS_DIR / "fonts"

_FONT_FILES = (
    "PetMe64.ttf",  # Commodore 64, Kreative Korporation / Kreative Software
)

_FONTS_REGISTERED = False


def get_asset_path(*parts: str) -> Path:
    """Return the absolute path to a bundled asset inside `src/c64u_bridge/assets`."""
    return ASSETS_DIR.joinpath(*parts)


def register_embedded_fonts() -> bool:
    """
    Register the bundled Commodore 64 TrueType font (`PetMe64.ttf`)
    privately for the current Windows process (`FR_PRIVATE = 0x10`).
    No administrator rights or system-wide font installation required.
    """
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return True

    if os.name != "nt":
        return False

    loaded_any = False
    try:
        add_font = ctypes.windll.gdi32.AddFontResourceExW
        add_font.argtypes = [ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
        add_font.restype = ctypes.c_int
        private_font = 0x10  # FR_PRIVATE: process-local registration
        for filename in _FONT_FILES:
            font_path = FONTS_DIR / filename
            if font_path.is_file():
                res = add_font(str(font_path), private_font, None)
                if res > 0:
                    loaded_any = True
        _FONTS_REGISTERED = loaded_any
    except (AttributeError, OSError):
        pass
    return loaded_any


FONT_CREDITS_TEXT = (
    "CREDITS, FONTS & ACKNOWLEDGMENTS\n"
    "============================================================\n\n"
    "1. COMMODORE 64 BITMAP FONT:\n"
    "   • 'Pet Me 64' (PetMe64.ttf)\n"
    "   • Created & Produced by: Kreative Korporation / Kreative Software\n"
    "     (Rebecca G. Bettencourt) — https://www.kreativekorp.com/software/fonts/c64/\n"
    "   • License: Kreative Software Relay Fonts Free Use License v1.2f\n"
    "     (Included verbatim at src/c64u_bridge/assets/fonts/LICENSE-Kreative-FreeUse-1.2f.txt)\n"
    "   • Sourced via: The Faerie Project bundled font collection\n"
    "     (https://github.com/KiwiGeek/Faerie) & BackMeUpScotty.\n\n"
    "2. COMMODORE 64 ULTIMATE / ULTIMATE-64 HARDWARE & REST API:\n"
    "   • Gideon Zweijtzer (Gideon's Logic Architectures)\n"
    "     Creator of the Ultimate-II+, Ultimate 64, and C64U FPGA core & DMA engine.\n\n"
    "3. 6502 CROSS-ASSEMBLER TOOLCHAIN:\n"
    "   • Mads Nielsen — Creator of KickAssembler v5.x (http://theweb.dk/KickAssembler/)\n"
    "   • Marco Baye (ACME Cross-Assembler) & the CC65 Development Team.\n\n"
    "4. ORIGINAL COMMODORE 64 SILICON ARCHITECTURE (1982):\n"
    "   • MOS Technology & Commodore Business Machines (CBM)\n"
    "   • Chuck Peddle & Bill Mensch (MOS 6502 / 6510 CPU)\n"
    "   • Al Charpentier & Charles Winterble (MOS 6567/6569 VIC-II Video)\n"
    "   • Bob Yannes (MOS 6581/8580 SID Sound Interface Device)"
)


THEMES: dict[str, dict[str, object]] = {
    "Commodore 64": {
        "id": "c64",
        "name": "Commodore 64 BASIC V2",
        "boot_banner": "    **** COMMODORE 64 BASIC V2 ****\n 64K RAM SYSTEM  38911 BASIC BYTES FREE",
        "ready_prompt": "READY.",
        "border_idle": "#70A4B2",  # Authentic VIC-II Light Blue ($0E)
        "border_active_1": ["#6C5EB5", "#70A4B2", "#B8C76F", "#883932", "#FFFFFF", "#352879"],
        "border_active_2": ["#9AD284", "#352879", "#6F3D86", "#588D43", "#70A4B2", "#B8C76F"],
        "paper": "#352879",         # Authentic VIC-II Dark Blue ($06)
        "panel_bg": "#221955",      # Deep C64 CRT cavity blue
        "panel_fg": "#70A4B2",      # Light Blue text
        "editor_bg": "#1B1447",     # High-contrast dark blue for code editing
        "editor_fg": "#70A4B2",     # Classic C64 Light Blue code text
        "gutter_bg": "#140E36",     # Line number gutter background
        "gutter_fg": "#6C5EB5",     # Line number gutter foreground
        "ink": "#70A4B2",           # Light Blue text
        "accent": "#B8C76F",        # C64 Yellow ($07)
        "accent_bright": "#FFFFFF", # C64 White ($01)
        "highlight": "#70A4B2",     # Light Blue highlight
        "cyan": "#70A4B2",          # C64 Cyan/Light Blue
        "success": "#9AD284",       # C64 Light Green ($0D)
        "warning": "#B8C76F",       # C64 Yellow ($07)
        "danger": "#9A6759",        # C64 Light Red ($0A)
        "button_bg": "#70A4B2",     # Reversed PETSCII Light Blue button
        "button_fg": "#352879",     # Dark Blue text on Light Blue button
        "button_active_bg": "#FFFFFF",
        "button_active_fg": "#352879",
        "input_bg": "#1B1447",
        "input_fg": "#FFFFFF",
        "bar_bg": "#140E36",
        "bar_fg": "#9AD284",
        "bar_alt": "#70A4B2",
        "rainbow": ["#883932", "#675200", "#B8C76F", "#588D43", "#70A4B2", "#6F3D86"],
        "font_family": "Pet Me 64",
        # Syntax highlighting colors (authentic C64 palette)
        "syn_opcode": "#FFFFFF",     # White for 6502 opcodes
        "syn_directive": "#B8C76F",  # Yellow for KickAssembler directives
        "syn_number": "#9AD284",     # Light Green for hex/binary literals ($D020, #$00)
        "syn_label": "#58C8D8",      # Bright Cyan for labels & symbols
        "syn_comment": "#8A7BCE",    # Soft Lavender/Blue for comments
        "syn_string": "#B8C76F",     # Yellow for strings
        "syn_hardware": "#FF9E88",   # Light Red/Orange for VIC-II / SID / CIA registers
    },
}

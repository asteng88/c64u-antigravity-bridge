"""
C64U Antigravity Bridge
Connecting Google Antigravity to the Commodore 64 Ultimate (C64U) for real-time 6502 development.
"""

__version__ = "0.1.0"
__author__ = "Andrew Thomas"

from .client import C64UClient
from .compiler import CrossCompiler
from .screen import format_screen, screen_code_to_ascii
from .sprite import (
    C64Color,
    Sprite,
    SpriteMode,
    SpriteTool,
    copy_to_clipboard,
    create_airwolf_sprite,
    create_commodore_logo_sprite,
    create_multicolor_airwolf_sprite,
)
from .tap import asm_to_tap, prg_to_tap, save_prg_to_tap

__all__ = [
    "C64UClient",
    "format_screen",
    "screen_code_to_ascii",
    "CrossCompiler",
    "prg_to_tap",
    "save_prg_to_tap",
    "asm_to_tap",
    "Sprite",
    "SpriteMode",
    "SpriteTool",
    "C64Color",
    "copy_to_clipboard",
    "create_airwolf_sprite",
    "create_multicolor_airwolf_sprite",
    "create_commodore_logo_sprite",
]

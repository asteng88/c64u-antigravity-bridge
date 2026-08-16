"""
PETSCII and C64 Screen Code Decoder
Converts raw screen memory dumps into human-readable ASCII and ANSI text representations.
"""

from __future__ import annotations
from typing import List, Optional

# Screen code to ASCII table for C64 Uppercase/Graphics character set
SCREEN_CODE_TO_ASCII = [
    # 0x00 - 0x1F (@, A-Z, [, £, ], ↑, ←)
    "@", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O",
    "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z", "[", "£", "]", "^", "<",
    # 0x20 - 0x3F (Space, punctuation, 0-9, : ; < = > ?)
    " ", "!", '"', "#", "$", "%", "&", "'", "(", ")", "*", "+", ",", "-", ".", "/",
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", ":", ";", "<", "=", ">", "?",
    # 0x40 - 0x5F (Graphics/Special)
    "-", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O",
    "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z", "+", "|", "+", "+", "+",
    # 0x60 - 0x7F (Box drawing / graphics)
    " ", "#", "#", "-", "-", "|", "|", "#", "#", "#", "#", "+", "+", "+", "+", "+",
    "-", "-", "|", "|", "+", "+", "+", "+", "+", "+", "+", "+", "+", "+", "+", "#",
]

# C64 color palette names (0-15)
C64_COLOR_NAMES = [
    "Black", "White", "Red", "Cyan",
    "Purple", "Green", "Blue", "Yellow",
    "Orange", "Brown", "Light Red", "Dark Grey",
    "Grey", "Light Green", "Light Blue", "Light Grey"
]

# ANSI 256-color codes approximating the C64 palette
C64_ANSI_COLORS = [
    "\033[38;5;16m",   # 0: Black
    "\033[38;5;231m",  # 1: White
    "\033[38;5;160m",  # 2: Red
    "\033[38;5;51m",   # 3: Cyan
    "\033[38;5;127m",  # 4: Purple
    "\033[38;5;34m",   # 5: Green
    "\033[38;5;21m",   # 6: Blue
    "\033[38;5;226m",  # 7: Yellow
    "\033[38;5;208m",  # 8: Orange
    "\033[38;5;94m",   # 9: Brown
    "\033[38;5;203m",  # 10: Light Red
    "\033[38;5;238m",  # 11: Dark Grey
    "\033[38;5;244m",  # 12: Grey
    "\033[38;5;119m",  # 13: Light Green
    "\033[38;5;75m",   # 14: Light Blue
    "\033[38;5;250m",  # 15: Light Grey
]
ANSI_RESET = "\033[0m"


def screen_code_to_ascii(code: int) -> str:
    """Convert a single C64 screen code byte (0-255) to a printable ASCII character."""
    normalized = code & 0x7F  # Strip inverted bit for basic character lookup
    if normalized < len(SCREEN_CODE_TO_ASCII):
        return SCREEN_CODE_TO_ASCII[normalized]
    return " "


def format_screen(
    screen_bytes: bytes,
    color_bytes: Optional[bytes] = None,
    use_ansi: bool = False,
    cols: int = 40,
    rows: int = 25,
) -> str:
    """
    Format 1000 bytes of C64 Screen RAM into a 40x25 grid text block.
    
    Args:
        screen_bytes: Raw memory buffer from Screen RAM ($0400-$07E7).
        color_bytes: Optional raw memory buffer from Color RAM ($D800-$DBE7).
        use_ansi: Whether to embed ANSI color escape sequences.
        cols: Number of columns (default 40).
        rows: Number of rows (default 25).
        
    Returns:
        Formatted multi-line string representing the C64 screen.
    """
    total_chars = cols * rows
    raw_screen = list(screen_bytes[:total_chars])
    if len(raw_screen) < total_chars:
        raw_screen.extend([32] * (total_chars - len(raw_screen)))

    raw_colors = list(color_bytes[:total_chars]) if color_bytes else [14] * total_chars  # Default light blue

    lines: List[str] = []
    lines.append("+" + "-" * cols + "+")
    for r in range(rows):
        line_chars: List[str] = []
        for c in range(cols):
            idx = r * cols + c
            char = screen_code_to_ascii(raw_screen[idx])
            if use_ansi and color_bytes:
                color_idx = raw_colors[idx] & 0x0F
                ansi_color = C64_ANSI_COLORS[color_idx]
                line_chars.append(f"{ansi_color}{char}{ANSI_RESET}")
            else:
                line_chars.append(char)
        lines.append("|" + "".join(line_chars) + "|")
    lines.append("+" + "-" * cols + "+")

    return "\n".join(lines)

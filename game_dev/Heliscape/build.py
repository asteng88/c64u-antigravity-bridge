"""
HELISCAPE build manifest - for tools/build/build_tool.py (load it and press F7).

Regenerates the sprites, the world charset, both tunes and the levels, then assembles
heliscape.asm into heliscape.prg and a HYPERLOAD heliscape.tap.
"""
TITLE = "HELISCAPE"
STEPS = [
    ("sprites", "sprites/heliscape_sprites.py"),
    ("tileset", "map/heliscape_map.py"),
    ("song", "music/heliscape_theme.py"),
    ("song", "music/death/death_march.py"),
    ("levels", "map/heliscape_levels.py"),
    ("asm", "heliscape.asm"),
    ("hyperload", "heliscape.prg"),
]

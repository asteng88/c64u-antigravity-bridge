"""
TORNADO build manifest - for tools/build/build_tool.py (load it and press F7).

Regenerates the sprites, the archipelago tileset, the title music, and the
Koala title picture (loading/loading.kla), then assembles game/tornado.asm
(title screen + game) into game/tornado.prg.
"""
TITLE = "TORNADO"
STEPS = [
    ("sprites", "sprites/tornado_sprites.py"),
    ("tileset", "map/tornado_map.py"),
    ("song", "music/tornado_theme.py"),
    ("koala", "loading/loading_scene.py"),
    ("asm", "game/tornado.asm"),
]

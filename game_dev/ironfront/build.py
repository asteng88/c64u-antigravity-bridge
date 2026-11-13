"""
IRONFRONT build manifest - for tools/build/build_tool.py (load it and press F7).

Regenerates the sprites, the battlefield tileset, the title music, and the
Koala title picture (loading/loading.kla), then assembles game/ironfront.asm
(title screen + game) into game/ironfront.prg.
"""
TITLE = "IRONFRONT"
STEPS = [
    ("sprites", "sprites/ironfront_sprites.py"),
    ("tileset", "map/ironfront_map.py"),
    ("song", "music/ironfront_march.py"),
    ("koala", "loading/loading_scene.py"),
    ("asm", "game/ironfront.asm"),
]

"""
TORNADO build manifest - for tools/build/build_tool.py (load it and press F7).

Regenerates the sprites, the isometric archipelago terrain, the title music, and the
Koala title picture (loading/loading.kla), then assembles game/tornado.asm
(title screen + game) into game/tornado.prg.
"""
TITLE = "TORNADO"
# GAME CHECK input: title, briefing, flying in all directions, then a forced
# game over (last life, exploding) and back to the title
CHECK_INPUT = "check.json"
STEPS = [
    ("sprites", "sprites/tornado_sprites.py"),
    ("isotiles", "map/tornado_iso.py"),
    ("song", "music/tornado_theme.py"),
    ("koala", "loading/loading_scene.py"),
    ("asm", "game/tornado.asm"),
]

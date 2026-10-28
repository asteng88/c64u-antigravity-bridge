"""
IRONFRONT build manifest - for tools/build/build_tool.py (GAME DEV > BUILD GAME).

Regenerates the sprites, the battlefield tileset and the title music, then
assembles game/ironfront.asm (title screen + game) into game/ironfront.prg.
The loading picture (loading/loading.kla) is built separately with the Koala
tool because it is hand-tuned.
"""
TITLE = "IRONFRONT"
STEPS = [
    ("sprites", "sprites/ironfront_sprites.py"),
    ("tileset", "map/ironfront_map.py"),
    ("song", "music/ironfront_march.py"),
    ("asm", "game/ironfront.asm"),
]

# Tools

Standalone build tools for C64 game development. Each one is a plain Python
script (no dependencies beyond the standard library, plus Java for
KickAssembler). Each tool is also on the studio's **50 GAME DEV** menu
(`Alt+G` in `c64u-bridge`), registered in `src/c64u_bridge/gamedev.py`.

Tools read a *definition file* that holds the game's own content, and write
their outputs next to it. Content lives with the game in `game_dev/<game>/`;
the machinery lives here.

| Folder | Tool | Input | Output |
| --- | --- | --- | --- |
| `kickassembler/` | KickAssembler 5.x | `.asm` | `.prg` |
| `sprites/` | `sprite_tool.py` | sprite bank `.py` (`GROUPS` of `Sprite` builders) | `sprites.asm`, review page, `--png` contact sheet |
| `charset/` | `tileset_tool.py` | tileset `.py` (`TILES` 2x2-char art, `BLOCKS` multi-char buildings, `MAP`, `OBJECTS`) | `_charset.bin` (de-duplicated, bold font at codes 0-63), `_tiles.asm` (tile/block tables, map, start objects), review page |
| `bitmap/` | `koala_tool.py` | scene `.py` (`compose(cv)` on a 160×100 canvas) | `.kla` Koala bitmap with the 3-colours-per-cell rule enforced, review page |
| `sid/` | `song_tool.py` | song `.py` (instruments, patterns, order lists) | `music_data.asm`, `music_config.asm`; with `--build` also `.prg`, register log and `.sid` |
| `sid/` | `sid_player.asm` | – | 3-voice SID driver (wavetables, PWM, vibrato, hard restart) that songs compile for; `music_voice_off` lets a game take a voice for sound effects |
| `sid/` | `make_psid.py` | music `.prg` | PSID v2 `.sid` |
| `sim6502/` | `sim6502.py` | `.prg` or `.sid` | runs init/play in a 6502 emulator: crash check, CPU time per frame, SID register log |
| `c64sim/` | `c64sim.py` | `.prg` | headless C64 on top of `sim6502`: VIC-II rendered per raster line (text/bitmap modes, sprites, borders), raster IRQs, keyboard + joystick from an input script, memory pokes; PNG screenshots of chosen frames |
| `build/` | `build_tool.py` | game `build.py` manifest (`STEPS`) | runs the asset tools in order, then KickAssembler; `--shot N` adds a headless screenshot. The studio runs the PRG on the C64U |

Each script's docstring documents its definition-file format; run any of them
with `--help`.

## Adding a tool

1. Put the script in a subfolder here. Take the target file as the first
   argument and write outputs next to it.
2. Print `wrote <filename>` for each file produced. The studio opens `.html`
   review pages and remembers `.sid` files for **PLAY SID**.
3. Register it in `GAME_TOOLS` in `src/c64u_bridge/gamedev.py`, add a menu
   button in `tui.py`, and add a test in `tests/test_gamedev.py`.

// ==============================================================================
// HELISCAPE: RESCUE PROTOCOL
// Side-scrolling helicopter rescue for the Commodore 64.
//
// Fly into hostile territory, blast open the POW camps, land next to the
// prisoners, and carry them back to base eight at a time. 255 levels, each harder
// than the last, and a top five table with arcade initials.
//
// Joystick in port 2 or 1, or W/A/S/D + SPACE, or cursor keys + RETURN.
//   left/right ... fly; turning swings through the head-on pose
//   tap back ..... a quick tap of the opposite direction stops head-on
//   up/down ...... climb/descend; touch down gently to land
//   fire ......... cannon forward
//   down + fire .. bomb (fire alone also drops one while head-on)
//   P ............ pause
//
// Memory:  $0810 boot     $1000 current tune (see load_tune)    $1600 core code
//          $4000 charset  $4800 screen    $4C00 sprites (VIC bank 1)
//          $2C00 tunes + score table    $6C00 world art    $7800 game code    $9800 levels
//          $C000 world chars  $C600 world colours  $CC00 column heights  $CD00 RAM
//          (KERNAL and BASIC are banked out)
// Build:   python tools/build/build_tool.py game_dev/Heliscape/build.py
// Target Assembler: KickAssembler v5.x
// ==============================================================================

.encoding "screencode_upper"

#import "src/defs.asm"

// ---------------------------------------------------------------- generated data first:
// KickAssembler needs their .const values defined before they are used
* = $4000 "Charset"
        .import binary "map/heliscape_charset.bin"
* = $4C00 "Sprites"
#import "sprites/sprites.asm"
.assert "sprites end below the world art", * <= $6C00, true
.label SPRPTR0 = (sprite_bank - $4000) / 64

* = $6C00 "World art"
#import "map/heliscape_tiles.asm"
.assert "world art ends below the game code", * <= $7800, true

* = $9800 "Levels"
#import "map/heliscape_levels.asm"
.assert "levels end below the world RAM", * <= $C000, true

// ---------------------------------------------------------------- zero page
* = $02 "Zero page" virtual
#import "src/zp.asm"
.assert "zero page clear of the music driver", * <= $FB, true

// ---------------------------------------------------------------- general RAM
* = $CD00 "RAM" virtual
#import "src/ram.asm"
.assert "RAM fits under I/O", * <= $D000, true

// ---------------------------------------------------------------- program
BasicUpstart2(boot)

* = $1600 "Core"
#import "src/boot.asm"
#import "src/irq.asm"
#import "src/scroll.asm"
#import "src/world.asm"
#import "src/render.asm"
#import "src/hud.asm"
.assert "core ends below the tunes", * <= $2C00, true

* = $2C00 "Tunes + scores"
// Both tunes as built by tools/sid/song_tool.py: driver + song, assembled for $1000.
// load_tune copies the one that is wanted into place.
theme_tune:
        .import c64 "music/music.prg"
theme_end:
march_tune:
        .import c64 "music/death/music.prg"
march_end:
.assert "title theme fits the music area", theme_end - theme_tune <= TUNE_SIZE, true
.assert "game over tune fits the music area", march_end - march_tune <= TUNE_SIZE, true
#import "src/hiscore.asm"
.assert "tunes + scores end below the VIC bank", * <= $4000, true

* = $7800 "Game"
#import "src/player.asm"
#import "src/shots.asm"
#import "src/enemies.asm"
#import "src/pows.asm"
#import "src/sfx.asm"
#import "src/states.asm"
.assert "game code ends below the levels", * <= $9800, true

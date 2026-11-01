// HELISCAPE - shared constants (imported first)

.label music_init = $1000        // the tune copied here by load_tune
.label music_play = $1003
.const TUNE_SIZE = $600

.const SCREEN   = $4800
.const SPRPTR   = SCREEN + $3F8
.const COLRAM   = $D800
.const WCH      = $C000         // world chars, 6 rows x 256 columns (page per row)
.const WCO      = $C600         // world colours, same layout
.const WH       = $CC00         // per column: lowest chopper Y allowed there

.function ROW(n) { .return SCREEN + n * 40 }
.function CROW(n) { .return COLRAM + n * 40 }

// screen rows of each band
.const R_CLOUD  = 0
.const R_SUN    = 4
.const R_FAR    = 9
.const R_MID    = 13
.const R_NEAR   = 16
.const R_GROUND = 20
.const R_HUD    = 22
.const NEAR_H   = 6
.const FAR_ROWS = 4
.const MID_ROWS = 3
.const CLD_ROWS = 2
.const SUN_COL  = 28
.const SPLITS   = 9

// raster lines: a split fires on the line before its row (see irq.asm)
.function SPLITLINE(row) { .return 50 + row * 8 }
.const LINE_TOP    = 30
.const LINE_ZONE   = 184        // ground-band sprites are loaded here
.const LINE_BOTTOM = 251

// sprite Y: air-band sprites must have ended by LINE_ZONE, ground ones start after it
.const AIR_Y_MAX  = 160
.const GND_Y_MIN  = 188
.const TANK_Y     = 195
.const POW_Y      = 197
.const SHADOW_Y   = 194
.const Y_OFF      = 255

// chopper: Y is the top of the sprite, X the world centre
.const CHOP_GROUND = 193
.const CHOP_CEIL   = 46
.const GEAR_Y      = CHOP_GROUND - 22  // wheels down below this height
.const CHOP_CY     = 12         // centre line relative to Y
.const COMPOUND_Y  = 168        // chopper Y limit over a standing camp
.const HANGAR_Y    = 160
.const GROUND_LINE = 213        // shots hit the ground here
.const HIT_LINE    = 187        // top of a standing camp

.const WORLD_PX    = 2048
.const CAM_MAX     = WORLD_PX - 304
.const BASE_MAX_X  = 232        // landing west of here is the home base
.const DOOR_X      = 56         // hangar door, where rescued POWs walk to
.const PAD_COL     = 15
.const HANGAR_COL  = 2
.const TOWER_COL   = 26
.const START_X     = 156

// flight tuning, 8.8 fixed point per frame
.const ACC_X   = $0C
.const ACC_Y   = $14
.const MAX_VX  = $0240
.const MAX_VY  = $0180
.const SAFE_VY = $0140          // harder touchdowns hurt
.const SAFE_VX = $0120

.const TURN_T  = 12            // frames to hold a direction before leaving head-on
.const FACE_R  = 0
.const FACE_F  = 1
.const FACE_L  = 2

// player states
.const PS_FLY    = 0
.const PS_LANDED = 1
.const PS_FALL   = 2            // shot down
.const PS_DEAD   = 3

.const MAX_ARMOR = 8
.const MAX_CARGO = 8
.const START_LIVES = 3
.const MAX_LIVES = 5

// game states
.const ST_TITLE = 0
.const ST_BRIEF = 1
.const ST_PLAY  = 2
.const ST_DONE  = 3             // mission won: tally
.const ST_OVER  = 4             // out of choppers or too many lost
.const ST_NAME  = 5             // entering initials

// joystick bits, active high
.const J_UP    = 1
.const J_DOWN  = 2
.const J_LEFT  = 4
.const J_RIGHT = 8
.const J_FIRE  = 16

// pools
.const MAX_COMP = 5
.const MAX_TANK = 6
.const MAX_POW  = 8
.const MAX_AIR  = 3
.const MAX_EX   = 5
.const P_SHOTS  = 3             // shot slots 0-2 player, 3-5 enemy
.const E_SHOTS  = 3
.const MAX_SHOT = P_SHOTS + E_SHOTS

// shot types
.const S_NONE    = 0
.const S_BULLET  = 1
.const S_BOMB    = 2
.const S_FLAK    = 3
.const S_MISSILE = 4
.const S_EBOMB   = 5

// air enemy kinds
.const A_NONE  = 0
.const A_JET   = 1
.const A_HELI = 2

// ground enemy kinds
.const T_NONE   = 0
.const T_TANK   = 1
.const T_TURRET = 2

// POW squad states
.const P_FREE = 0
.const P_IDLE = 1
.const P_RUN  = 2
.const P_WALK = 3               // rescued, walking into the hangar

// explosion kinds
.const EX_BIG   = 0
.const EX_SMALL = 1
.const EX_SMOKE = 2

// sound effects (priority rises with the number)
.const FX_GUN     = 1
.const FX_DROP    = 2
.const FX_FLAK    = 3
.const FX_SMALL   = 4
.const FX_HIT     = 5
.const FX_BIG     = 6

// chimes on voice 2
.const CH_BOARD = 0
.const CH_SAVED = 1
.const CH_ALARM = 2
.const CH_LOST  = 3
.const CH_WIN   = 4

// colour RAM values for multicolor world blocks
.const CYAN8  = 3 | 8
.const WHITE8 = 1 | 8
.const GREEN8 = 5 | 8
.const RED8   = 2 | 8

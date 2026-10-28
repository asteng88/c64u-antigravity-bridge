// ==============================================================================
// IRONFRONT - shared constants (imported first: KickAssembler needs .const
// values defined before they are used)
// ==============================================================================

.const MAXU   = 32              // unit slots: 0-15 player, 16-31 enemy
.const MAXB   = 24              // structure slots
.const MUXMAX = 48              // display list entries per buffer
.const VMAX   = 48              // virtual sprites per frame
.const MAXF   = 10              // explosion slots

.const PLAYER_COL = 7           // yellow
.const ENEMY_COL  = 6           // blue

// unit types (index into the stat tables; 6 = turret, for damage only)
.const UT_TANK   = 1
.const UT_BUGGY  = 2
.const UT_HARV   = 3
.const UT_HELI   = 4
.const UT_SQUAD  = 5
.const UT_TURRET = 6

// unit states
.const S_IDLE    = 0
.const S_MOVE    = 1
.const S_ATTACK  = 2
.const S_HSEEK   = 3
.const S_HMOVE   = 4
.const S_HARVEST = 5
.const S_HRETURN = 6
.const S_HUNLOAD = 7
.const S_DYING   = 8

.const HARV_CAP  = 20           // ore units per load
.const ORE_VALUE = 25           // credits per ore unit
.const PROG_MAX  = 56           // production steps (7 bar chars x 8)

// sidebar items: 0-4 structures, 5-9 units
.const ITEM_COUNT = 10
.const ITEM_SQUAD = 5
.const ITEM_HARV  = 8

// explosions
.const FX_PUFF  = 1
.const FX_BLAST = 2

// sound effects
.const SFX_SHOT   = 0
.const SFX_CANNON = 1
.const SFX_BOOM   = 2
.const SFX_CLICK  = 3
.const SFX_READY  = 4
.const SFX_ERROR  = 5

// messages (7 characters each, see msg_text)
.const MSG_READY  = 0
.const MSG_UNIT   = 1
.const MSG_CASH   = 2
.const MSG_BUSY   = 3
.const MSG_ALERT  = 4
.const MSG_LOCKED = 5
.const MSG_PLACED = 6
.const MSG_FULL   = 7

.const WAVE_FIRST = 4500        // frames before the first enemy attack (90 s)
.const WAVE_GAP   = 2700        // frames between attacks

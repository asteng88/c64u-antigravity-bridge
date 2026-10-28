// ==============================================================================
// IRONFRONT - game data: unit and structure stats, production list, lookup
// tables and sidebar text
// ==============================================================================

// ---------------------------------------------------------------- units
// index: 0 -, 1 tank, 2 buggy, 3 harvester, 4 helicopter, 5 squad, 6 turret
hp_tab:      .byte 0, 120, 60, 160, 70, 60
speed_tab:   .byte 0, 128, 250, 100, 220, 80     // 1/256 px per frame
range_tab:   .byte 0, 4, 3, 0, 4, 3, 5           // tiles
reload_tab:  .byte 0, 50, 12, 0, 36, 24, 45      // frames
air_tab:     .byte 0, 0, 1, 0, 1, 1, 1           // can hit helicopters
// damage per shot vs infantry, vehicles, structures
dmg_tab:     .byte 0, 0, 0
             .byte 8, 22, 18                     // tank: cannon
             .byte 9, 4, 2                       // buggy: machine gun
             .byte 0, 0, 0                       // harvester: unarmed
             .byte 8, 16, 12                     // helicopter: rockets
             .byte 7, 3, 3                       // squad: rifles
             .byte 10, 20, 0                     // turret
spr_base_tab: .byte 0, SPR_TANK, SPR_BUGGY, SPR_HARVESTER, SPR_HELI, SPR_SQUAD3

// structures: HQ, refinery, barracks, factory, helipad, turret
bhp_tab:     .byte 250, 200, 160, 220, 140, 180

// ---------------------------------------------------------------- production
// items 0-4 are structures (kind = B_*), 5-9 units (kind = UT_*)
item_kind:   .byte B_REFINERY, B_BARRACKS, B_FACTORY, B_HELIPAD, B_TURRET
             .byte UT_SQUAD, UT_BUGGY, UT_TANK, UT_HARV, UT_HELI
item_req:    .byte B_HQ, B_HQ, B_HQ, B_HQ, B_HQ
             .byte B_BARRACKS, B_FACTORY, B_FACTORY, B_FACTORY, B_HELIPAD
item_cost_l: .byte <1200, <400, <1000, <800, <500, <100, <300, <600, <1000, <900
item_cost_h: .byte >1200, >400, >1000, >800, >500, >100, >300, >600, >1000, >900
item_time:   .byte 16, 8, 14, 12, 9, 4, 7, 11, 14, 13   // frames per progress step
item_names:  .text "REFINRY"
             .text "BARRACK"
             .text "FACTORY"
             .text "HELIPAD"
             .text "TURRET "
             .text "SQUAD  "
             .text "BUGGY  "
             .text "TANK   "
             .text "HARVEST"
             .text "CHOPPER"
ai_pick:     .byte 5, 5, 6, 7, 7, 7, 9, 6

// ---------------------------------------------------------------- lookups
tyoff_lo:    .fill 32, <(i * 32)
tyoff_hi:    .fill 32, >(i * 32)
scr_lo:      .fill 25, <(SCREEN + i * 40)
scr_hi:      .fill 25, >(SCREEN + i * 40)
mul64:       .byte 0, 64, 128, 192
// headings 0-7 = N NE E SE S SW W NW
dxt:         .byte 0, 1, 1, 1, 0, $ff, $ff, $ff
dyt:         .byte $ff, $ff, 0, 1, 1, 1, 0, $ff
dir_tab:     .byte 7, 6, 5, 0, $ff, 4, 1, 2, 3    // [sign x * 3 + sign y]
dir4_tab:    .byte 0, 1, 1, 2, 2, 3, 3, 0        // squad walk N E S W
// 7x7 spiral around a tile, nearest first
ring_dx: .byte 0,0,255,1,0,255,1,255,1,0,254,2,0,255,1,254,2,254,2,255,1,254,2,254,2,0,253,3,0,255,1,253,3,253,3,255,1,254,2,253,3,253,3,254,2,253,3,253,3
ring_dy: .byte 0,1,0,0,255,1,1,255,255,2,0,0,254,2,2,1,1,255,255,254,254,2,2,254,254,3,0,0,253,3,3,1,1,255,255,253,253,3,3,2,2,254,254,253,253,3,3,253,253
pow10_lo:    .byte <10000, <1000, <100, <10, <1
pow10_hi:    .byte >10000, >1000, >100, >10, >1
num_buf:     .fill 5, 0
price_buf:   .fill ITEM_COUNT * 5, 0
have_bld:    .fill 6, 0
sb_next:     .byte 0

// ---------------------------------------------------------------- text
sb_text:
sbt_credit:  .text "$      "
sbt_options: .text "OPTIONS"
sbt_shadows: .text "SHADOWS"
sbt_music:   .text "MUSIC  "
sbt_on:      .text "     ON"
sbt_off:     .text "    OFF"
sbt_resume:  .text "RESUME "
sbt_quit:    .text "QUIT   "
sbt_mission: .text "MISSION"
sbt_success: .text "SUCCESS"
sbt_failed:  .text " FAILED"
sbt_press:   .text "PRESS  "
sbt_fire:    .text "FIRE   "
sbt_ready:   .text "  READY"
.label SBT_CREDIT  = sbt_credit - sb_text
.label SBT_OPTIONS = sbt_options - sb_text
.label SBT_SHADOWS = sbt_shadows - sb_text
.label SBT_MUSIC   = sbt_music - sb_text
.label SBT_ON      = sbt_on - sb_text
.label SBT_OFF     = sbt_off - sb_text
.label SBT_RESUME  = sbt_resume - sb_text
.label SBT_QUIT    = sbt_quit - sb_text
.label SBT_MISSION = sbt_mission - sb_text
.label SBT_SUCCESS = sbt_success - sb_text
.label SBT_FAILED  = sbt_failed - sb_text
.label SBT_PRESS   = sbt_press - sb_text
.label SBT_FIRE    = sbt_fire - sb_text
.label SBT_READY   = sbt_ready - sb_text

// MSG_* order
msg_text:    .text "READY  "
             .text "UNIT UP"
             .text "NO CASH"
             .text "BUSY   "
             .text "ALERT! "
             .text "LOCKED "
             .text "PLACED "
             .text "NO ROOM"

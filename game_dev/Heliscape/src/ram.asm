// HELISCAPE - general RAM (virtual, zeroed at boot)
ram_start:

// display list buffers: 12 logical slots x 2 buffers
// slots 0-3 are always live (chopper A/B, player shot, enemy shot),
// 4-7 the air band, 8-11 the ground band
s_x:        .fill 24, 0
s_m:        .fill 24, 0
s_y:        .fill 24, 0
s_p:        .fill 24, 0
s_c:        .fill 24, 0
s_msb_top:  .fill 24, 0
s_msb_gnd:  .fill 24, 0

// live palette per split, loaded from the mission tables
pal_21:     .fill SPLITS, 0
pal_22:     .fill SPLITS, 0
pal_23:     .fill SPLITS, 0

// camps
c_col:      .fill MAX_COMP, 0
c_hp:       .fill MAX_COMP, 0
c_wait:     .fill MAX_COMP, 0   // POWs still inside
c_delay:    .fill MAX_COMP, 0   // release ticks to wait after the camp falls
c_n:        .byte 0

// tanks and turrets
g_kind:     .fill MAX_TANK, 0
g_xl:       .fill MAX_TANK, 0
g_xh:       .fill MAX_TANK, 0
g_hp:       .fill MAX_TANK, 0
g_reload:   .fill MAX_TANK, 0
g_speed:    .fill MAX_TANK, 0
g_aim:      .fill MAX_TANK, 0
g_n:        .byte 0

// POW squads
q_st:       .fill MAX_POW, 0
q_xl:       .fill MAX_POW, 0
q_xh:       .fill MAX_POW, 0
q_n:        .fill MAX_POW, 0    // figures in the squad, 1-3
q_dir:      .fill MAX_POW, 0    // 0 right, 1 left
q_t:        .fill MAX_POW, 0

// aircraft
a_kind:     .fill MAX_AIR, 0
a_xl:       .fill MAX_AIR, 0
a_xh:       .fill MAX_AIR, 0
a_y:        .fill MAX_AIR, 0
a_dir:      .fill MAX_AIR, 0    // 0 left, 1 right
a_hp:       .fill MAX_AIR, 0
a_t:        .fill MAX_AIR, 0

// shots
s_type:     .fill MAX_SHOT, 0
s_xf:       .fill MAX_SHOT, 0
s_xl:       .fill MAX_SHOT, 0
s_xh:       .fill MAX_SHOT, 0
s_yf:       .fill MAX_SHOT, 0
s_yl:       .fill MAX_SHOT, 0
s_vxl:      .fill MAX_SHOT, 0
s_vxh:      .fill MAX_SHOT, 0
s_vyl:      .fill MAX_SHOT, 0
s_vyh:      .fill MAX_SHOT, 0
s_age:      .fill MAX_SHOT, 0
aim_vxl:    .byte 0
aim_vxh:    .byte 0
aim_vyl:    .byte 0
aim_vyh:    .byte 0

// explosions
e_kind:     .fill MAX_EX, 0     // kind + 1, 0 = free
e_xl:       .fill MAX_EX, 0
e_xh:       .fill MAX_EX, 0
e_y:        .fill MAX_EX, 0
e_age:      .fill MAX_EX, 0

// score, BCD
score0:     .byte 0
score1:     .byte 0
score2:     .byte 0
hi0:        .byte 0
hi1:        .byte 0
hi2:        .byte 0

// sound
rotor_t:    .byte 0
fx_id:      .byte 0
fx_t:       .byte 0
fx_w:       .byte 0
fx_f:       .byte 0
fx_d:       .byte 0
fx_req:     .byte 0
ch_pos:     .byte 0
ch_t:       .byte 0
ch_req:     .byte 0
alarm_t:    .byte 0
hs:         .fill 30, 0         // top five, see hiscore.asm
rank:       .byte 0
name_pos:   .byte 0
name_rep:   .byte 0
name_idx:   .fill 3, 0
level_d:    .fill 3, 0
dbg_line:   .byte 0             // raster when the last frame's logic ended
dbg_over:   .byte 0             // frames whose logic overran

ram_end:

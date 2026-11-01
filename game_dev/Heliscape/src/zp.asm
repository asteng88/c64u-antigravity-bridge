// HELISCAPE - zero page variables (virtual; $FB/$FC belong to the music driver)

ptr:        .word 0
ptr2:       .word 0
t0:         .byte 0
t1:         .byte 0
t2:         .byte 0
t3:         .byte 0
t4:         .byte 0
t5:         .byte 0
a0:         .byte 0             // world position A (abs_dx, world_x)
a1:         .byte 0
b0:         .byte 0             // world position B (abs_dx)
b1:         .byte 0
sa:         .byte 0             // IRQ register saves
sx:         .byte 0
sy:         .byte 0
xsave:      .byte 0
xsave_s:    .byte 0             // pool loop index across calls
ey:         .byte 0             // spawn_ex: centre line

frame:      .byte 0
vflag:      .byte 0
game_state: .byte 0
state_t:    .byte 0
rnd:        .byte 0
joy:        .byte 0
joy_prev:   .byte 0
paused:     .byte 0
key_prev:   .byte 0

// display buffers
front:      .byte 0             // 0 or 12: slot offset the IRQs read
bk:         .byte 0             // the other one, being built
back_ready: .byte 0
air_n:      .byte 0             // next air slot (4-7)
gnd_n:      .byte 0             // next ground slot (8-11)
spr_x0:     .byte 0
spr_x1:     .byte 0
spr_y:      .byte 0
spr_f:      .byte 0

// raster-split values
d_cloud:    .byte 0
d_far:      .byte 0
d_mid:      .byte 0
d_near:     .byte 0

// scrolling
cam_l:      .byte 0
cam_h:      .byte 0
cam_dx:     .byte 0             // signed pixels moved since the last apply
drift:      .byte 0
clouds_on:  .byte 0
far_f:      .byte 0             // band positions: fraction, pixel lo, pixel hi
far_l:      .byte 0
far_h:      .byte 0
mid_f:      .byte 0
mid_l:      .byte 0
mid_h:      .byte 0
cld_f:      .byte 0
cld_l:      .byte 0
cld_h:      .byte 0
col_near:   .byte 0             // world column at screen column 0
col_far:    .byte 0
col_mid:    .byte 0
col_cld:    .byte 0

// art row pointers, filled at boot
far_p:      .fill 2 * FAR_ROWS, 0
mid_p:      .fill 2 * MID_ROWS, 0
cld_p:      .fill 2 * CLD_ROWS, 0

// player
p_state:    .byte 0
p_xf:       .byte 0
p_xl:       .byte 0
p_xh:       .byte 0
p_yf:       .byte 0
p_y:        .byte 0
p_vxl:      .byte 0
p_vxh:      .byte 0
p_vyl:      .byte 0
p_vyh:      .byte 0
p_face:     .byte 0
p_want:     .byte 0
p_turn:     .byte 0
p_tilt:     .byte 0
p_armor:    .byte 0
p_cargo:    .byte 0
p_invul:    .byte 0
p_flash:    .byte 0
p_cool:     .byte 0
p_timer:    .byte 0
p_at_base:  .byte 0
p_unload:   .byte 0
p_repair:   .byte 0

// mission
mission:    .byte 0             // level number, from 0
palette:    .byte 0
lvp:        .word 0             // this level's layout record
lvy:        .byte 0             // read position in it
title_page: .byte 0             // 0 logo, 1 score table
title_t:    .byte 0
lives:      .byte 0
pow_total:  .byte 0
pow_saved:  .byte 0
pow_lost:   .byte 0
jet_timer:  .byte 0
heli_timer: .byte 0
flash:      .byte 0
hud_dirty:  .byte 0
pow_spawn:  .byte 0
music_on:   .byte 0
sfx_on:     .byte 0

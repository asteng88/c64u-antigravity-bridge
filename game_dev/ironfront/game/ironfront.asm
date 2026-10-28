// ==============================================================================
// IRONFRONT - real-time strategy for the Commodore 64
//
// Title screen (loading.kla + title march) -> one skirmish against the CPU on a
// 32x32-tile desert map. Build a base from the sidebar, harvest ore for
// credits, and destroy every enemy structure.
//
// Joystick in port 2 moves the cursor; push against a screen edge to scroll.
//   fire on own unit ..... select it           fire + drag ...... box select
//   fire on ground ....... move selection      fire on enemy .... attack
//   SPACE ................ deselect / cancel   A ................ select army
//   F1 or O .............. options (shadows, music, quit)
//
// Memory:  $0810 boot + title      $1000 music       $1580 code
//          $4000 screen, $4400 unit/building tables, $4800 charset,
//          $5000 sprites (VIC bank 1)   $7200 multiplexer buffers
//          $8000/$8400/$A000 title picture (VIC bank 2)   $8800 map data + code
//          $C000 char map  $E000 colour map  $F000 occupancy  $F400 tile map
//          $F800 ore amounts   (KERNAL and BASIC are banked out)
// Target Assembler: KickAssembler v5.x
// ==============================================================================

.encoding "screencode_upper"

#import "../music/music_config.asm"
#import "defs.asm"

.const SCREEN   = $4000
.const SPRPTR   = SCREEN + $3F8
.const CHARSET  = $4800
.const COLRAM   = $D800
.const CHARMAP  = $C000         // 64x64 chars: the whole battlefield
.const COLMAP   = $E000         // 64x64 colour RAM values
.const OCC      = $F000         // 32x32: 0 free, 1-32 unit+1, $40+n building n, $FF rock
.const TMAP     = $F400         // 32x32 tile ids
.const ORE_AMT  = $F800         // 32x32 ore units left
.const VIEW_W   = 32            // playfield columns; the sidebar is columns 32-39
.const VIEW_H   = 25
.const FRAME_LINE = 251         // bottom-border raster IRQ: music, frame tick, sprites 0-7

// ---------------------------------------------------------------- zero page
.label ptr      = $02
.label ptr2     = $04
.label ptr3     = $06
.label ptr4     = $08
.label gp       = $0a           // OCC grid pointer
.label gpt      = $0c           // TMAP grid pointer
.label gpo      = $0e           // ORE_AMT grid pointer
.label t0       = $10
.label t1       = $11
.label t2       = $12
.label t3       = $13
.label t4       = $14
.label t5       = $15
.label t6       = $16
.label t7       = $17
.label frame    = $18
.label frame_hi = $19
.label frame_flag = $1a
.label joy      = $1b           // active high: 1 up 2 down 4 left 8 right 16 fire
.label joy_prev = $1c
.label keys     = $1d           // KEY_* bits, active high
.label keys_new = $1e
.label keys_prev = $1f
.label cur_xl   = $20
.label cur_xh   = $21
.label cur_y    = $22
.label cur_hold = $23
.label cam_x    = $24           // view top-left in chars
.label cam_y    = $25
.label view_dirty = $26
.label cu       = $27           // unit being updated
.label rnd      = $28
.label rnd2     = $29
.label game_state = $2a         // GS_*
.label quit_flag = $2b
.label save_a   = $2c
.label save_x   = $2d
.label save_y   = $2e
.label mux_cur  = $2f           // display list being shown (0 or MUXMAX)
.label mux_back = $30           // display list being built
.label mux_end  = $31
.label mux_idx  = $32
.label mux_ready = $33
.label back_count = $34
.label cur_spr_x = $35
.label cur_spr_msb = $36
.label cur_spr_y = $37
.label cur_spr_ptr = $38
.label cur_spr_col = $39
.label vs_count   = $3a
.label wx_l     = $3b           // cursor in world pixels
.label wx_h     = $3c
.label wy_l     = $3d
.label wy_h     = $3e
.label ctx      = $3f           // cursor tile
.label cty      = $40
.label hover_u  = $41
.label hover_b  = $42
.label cam_px_l = $43
.label cam_px_h = $44
.label cam_py_l = $45
.label cam_py_h = $46
.label opt_shadow = $47
.label opt_music = $48
.label credits_l = $49          // player credits
.label credits_h = $4a
.label ai_cr_l  = $4b
.label ai_cr_h  = $4c
.label t8       = $4d
.label t9       = $4e
.label tgt      = $4f           // current target id ($40+ = building)
.label tx_a     = $50
.label ty_a     = $51
.label tx_b     = $52
.label ty_b     = $53
.label sfx_pri  = $54
.label sfx_pos  = $55
.label sfx_ptr  = $56           // 2 bytes
.label sfx_rel  = $58
.label sel_count = $59
.label drag     = $5a           // 1 while box-selecting
.label anc_xl   = $5b           // drag anchor (screen)
.label anc_xh   = $5c
.label anc_y    = $5d
.label press    = $5e           // fire went down in the playfield
.label plc_on   = $5f           // placing a finished structure
.label plc_ox   = $60           // footprint drawn at (tile), $FF none
.label plc_oy   = $61
.label plc_ok   = $62
.label plc_okd  = $63
.label hover_item = $64
.label msg_timer = $65
.label alert_t  = $66
.label end_t    = $67
.label sp_type  = $69           // spawn_unit / place_building arguments
.label sp_owner = $6a
.label loops    = $6b           // main loop passes (vs frame: CPU load check)

.const GS_PLAY    = 0
.const GS_OPTIONS = 1
.const GS_WON     = 2
.const GS_LOST    = 3

.const KEY_SPACE = 1
.const KEY_A     = 2
.const KEY_F1    = 4
.const KEY_O     = 8

// ---------------------------------------------------------------- data blocks
.var pic = LoadBinary("../loading/loading.kla", BF_KOALA)

* = $4800 "Charset"
        .import binary "../map/ironfront_charset.bin"

* = $5000 "Sprites"
#import "../sprites/sprites.asm"
.label SPR_BASE = (sprite_bank - $4000) / 64

* = $8000 "Title screen RAM"
title_scr:
        .fill 1000, pic.getScreenRam(i)
* = $8400 "Title colour RAM"
title_col:
        .fill 1000, pic.getColorRam(i)
* = $A000 "Title bitmap"
        .fill 8000, pic.getBitmap(i)

* = $1000 "Music"
#import "../../../tools/sid/sid_player.asm"
#import "../music/music_data.asm"
.assert "music ends before the code", * <= $1580, true

* = $8800 "Map data"
#import "../map/ironfront_tiles.asm"
#import "tables.asm"
#import "ai.asm"
#import "sfx.asm"
.assert "map data + code below the title bitmap", * <= $A000, true

// ---------------------------------------------------------------- boot + title
BasicUpstart2(boot)

* = $0810 "Boot"
boot:
        sei
        cld
        ldx #$ff
        txs
        lda #$35                // RAM everywhere, I/O at $D000
        sta $01
        lda #$7f
        sta $dc0d
        sta $dd0d
        lda $dc0d
        lda $dd0d
        lda #<nmi
        sta $fffa
        lda #>nmi
        sta $fffb
        lda #$ff
        sta $dc02               // CIA1 port A: keyboard columns out
        lda #$00
        sta $dc03               // port B: keyboard rows in
        lda #$3f
        sta $dd02
        lda #1
        sta opt_shadow
        sta opt_music
        lda #$a5
        sta rnd
        lda #$5a
        sta rnd2
        jmp title
nmi:    rti

title:
        sei
        lda #$0b                // blank the screen while switching
        sta $d011
        lda #0
        sta $d015
        sta $d01a
        sta $d020
        lda #$ff
        sta $d019
        jsr sid_silence
        ldx #0
!:      lda title_col,x
        sta COLRAM,x
        lda title_col+$100,x
        sta COLRAM+$100,x
        lda title_col+$200,x
        sta COLRAM+$200,x
        lda title_col+$2e8,x
        sta COLRAM+$2e8,x
        inx
        bne !-
        lda #pic.getBackgroundColor()
        sta $d021
        lda $dd00
        and #$fc
        ora #$01                // VIC bank 2 ($8000-$BFFF)
        sta $dd00
        lda #$08                // screen $8000, bitmap $A000
        sta $d018
        lda #$18                // multicolor, 40 columns
        sta $d016
        jsr music_init
        lda #0
        sta music_voice_off
        sta music_voice_off+1
        sta music_voice_off+2
        lda #<title_irq
        sta $fffe
        lda #>title_irq
        sta $ffff
        lda #FRAME_LINE
        sta $d012
        lda #1
        sta $d01a
!:      lda $d012               // switch on in the border: no half-drawn frame
        cmp #FRAME_LINE
        bne !-
        lda #$3b                // bitmap mode on
        sta $d011
        cli
title_wait:
!:      jsr read_input          // wait for fire / space to be released...
        lda joy
        and #$10
        bne !-
        lda keys
        and #KEY_SPACE
        bne !-
!:      jsr read_input          // ...then pressed
        lda joy
        and #$10
        bne !+
        lda keys
        and #KEY_SPACE
        beq !-
!:      jmp game_start

title_irq:
        pha
        txa
        pha
        tya
        pha
        lda #$ff
        sta $d019
        jsr music_play
        inc frame
        pla
        tay
        pla
        tax
        pla
        rti

sid_silence:
        lda #0
        ldx #$18
!:      sta $d400,x
        dex
        bpl !-
        rts

// Joystick port 2 and a few keys, straight from CIA 1.
read_input:
        lda joy
        sta joy_prev
        lda keys
        sta keys_prev
        lda #$ff
        sta $dc00
        lda $dc00
        eor #$ff
        and #$1f
        sta joy
        lda #0
        sta t0
        lda #%01111111          // column 7: SPACE = row 4
        sta $dc00
        lda $dc01
        and #%00010000
        bne !+
        lda #KEY_SPACE
        sta t0
!:      lda #%11111101          // column 1: A = row 2
        sta $dc00
        lda $dc01
        and #%00000100
        bne !+
        lda t0
        ora #KEY_A
        sta t0
!:      lda #%11111110          // column 0: F1 = row 4
        sta $dc00
        lda $dc01
        and #%00010000
        bne !+
        lda t0
        ora #KEY_F1
        sta t0
!:      lda #%11101111          // column 4: O = row 6
        sta $dc00
        lda $dc01
        and #%01000000
        bne !+
        lda t0
        ora #KEY_O
        sta t0
!:      lda #$ff
        sta $dc00
        lda t0
        sta keys
        lda keys_prev
        eor #$ff
        and keys
        sta keys_new
        rts
.assert "boot code below the music", * <= $1000, true

// ---------------------------------------------------------------- game
* = $1580 "Code"
game_start:
        sei
        lda #$0b
        sta $d011
        lda #0
        sta $d01a
        sta $d015
        lda #$ff
        sta $d019
        jsr sid_silence
        jsr music_init
        jsr apply_music_option
        jsr init_world
        jsr init_vic_game
        jsr sidebar_init
        jsr draw_view
        jsr mux_init
        lda #<frame_irq
        sta $fffe
        lda #>frame_irq
        sta $ffff
        lda #FRAME_LINE
        sta $d012
        lda #1
        sta $d01a
!:      lda $d012
        cmp #FRAME_LINE
        bne !-
        lda #$1b                // text mode, 25 rows
        sta $d011
        cli

main_loop:
        lda frame_flag
        beq main_loop
        lda #0
        sta frame_flag
        inc loops
        jsr read_input
        jsr ui_update
        lda game_state
        bne !+
        jsr units_update
        jsr buildings_update
        jsr production_update
        jsr ai_update
        jsr effects_update
        jsr check_end
!:      jsr sidebar_update
        lda view_dirty
        beq !+
        jsr draw_view
        lda #$ff
        sta plc_ox
!:      jsr place_overlay
        jsr build_sprites
        lda quit_flag
        beq main_loop
        jmp title

init_vic_game:
        lda $dd00
        and #$fc
        ora #$02                // VIC bank 1 ($4000-$7FFF)
        sta $dd00
        lda #$02                // screen $4000, charset $4800
        sta $d018
        lda #$18                // multicolor text, 40 columns
        sta $d016
        lda #0
        sta $d020
        sta $d017
        sta $d01d
        sta $d01b
        sta $d010
        sta $d01c
        lda #BG0
        sta $d021
        lda #BG1
        sta $d022
        lda #BG2
        sta $d023
        lda #0                  // sprite multicolors: black, white
        sta $d025
        lda #1
        sta $d026
        rts

// Victory when every enemy structure is gone; defeat when the player has
// neither structures nor units left.
check_end:
        lda frame
        and #31
        beq !+
        rts
!:      ldx #0                  // t0 = player structures + units, t1 = enemy structures
        stx t0
        stx t1
        ldx #MAXB-1
!:      lda b_type,x
        bmi !next+
        lda b_owner,x
        bne !enemy+
        inc t0
        jmp !next+
!enemy: inc t1
!next:  dex
        bpl !-
        ldx #15
!:      lda u_type,x
        beq !+
        inc t0
!:      dex
        bpl !--
        lda t1
        bne !+
        lda #GS_WON
        jmp end_game
!:      lda t0
        beq !+
        rts
!:      lda #GS_LOST
end_game:
        sta game_state
        lda #0
        sta plc_on
        sta drag
        jsr sidebar_draw_page
        lda #SFX_READY
        jmp sfx_play

#import "mux.asm"
#import "world.asm"
#import "units.asm"
#import "ui.asm"
.assert "code fits below the screen", * <= $4000, true

// ---------------------------------------------------------------- runtime tables
* = $4400 "Unit tables" virtual
u_type:   .fill MAXU, 0
u_hp:     .fill MAXU, 0
u_xl:     .fill MAXU, 0
u_xh:     .fill MAXU, 0
u_yl:     .fill MAXU, 0
u_yh:     .fill MAXU, 0
u_tx:     .fill MAXU, 0
u_ty:     .fill MAXU, 0
u_nx:     .fill MAXU, 0
u_ny:     .fill MAXU, 0
u_gx:     .fill MAXU, 0
u_gy:     .fill MAXU, 0
u_ax:     .fill MAXU, 0     // attack-move destination
u_ay:     .fill MAXU, 0
u_dir:    .fill MAXU, 0
u_state:  .fill MAXU, 0
u_target: .fill MAXU, 0
u_reload: .fill MAXU, 0
u_timer:  .fill MAXU, 0
u_sel:    .fill MAXU, 0
u_flash:  .fill MAXU, 0
u_cargo:  .fill MAXU, 0
u_step:   .fill MAXU, 0     // pixels left in the current tile step
u_sub:    .fill MAXU, 0     // sub-pixel speed accumulator
u_stuck:  .fill MAXU, 0
u_auto:   .fill MAXU, 0     // 1: target picked automatically, 2: attack-move
u_anim:   .fill MAXU, 0
u_fire:   .fill MAXU, 0     // frames left of the firing pose
.assert "unit tables below the charset", * <= $4800, true
.label TABLES_END = *

* = $7200 "Mux tables" virtual
d_y:     .fill MUXMAX*2, 0
d_x:     .fill MUXMAX*2, 0
d_slot2: .fill MUXMAX*2, 0
d_slot:  .fill MUXMAX*2, 0
d_ptr:   .fill MUXMAX*2, 0
d_col:   .fill MUXMAX*2, 0
d_and:   .fill MUXMAX*2, 0
d_msb:   .fill MUXMAX*2, 0
d_mcb:   .fill MUXMAX*2, 0
d_irq:   .fill MUXMAX*2, 0
v_y:     .fill VMAX, 0
v_x:     .fill VMAX, 0
v_xh:    .fill VMAX, 0
v_ptr:   .fill VMAX, 0
v_col:   .fill VMAX, 0
v_mc:    .fill VMAX, 0
v_next:  .fill VMAX, 0
v_order: .fill VMAX, 0
v_head:  .fill 32, 0
slot_y:  .fill 8, 0
b_type:   .fill MAXB, 0     // $FF = empty, else B_* block id
b_owner:  .fill MAXB, 0
b_tx:     .fill MAXB, 0
b_ty:     .fill MAXB, 0
b_hp:     .fill MAXB, 0
b_reload: .fill MAXB, 0
f_kind:  .fill MAXF, 0
f_fr:    .fill MAXF, 0
f_t:     .fill MAXF, 0
f_xl:    .fill MAXF, 0
f_xh:    .fill MAXF, 0
f_yl:    .fill MAXF, 0
f_yh:    .fill MAXF, 0
// production queues: index 0 = structures, 1 = units (player); 2 = AI units
q_item:  .fill 3, 0
q_prog:  .fill 3, 0
q_tick:  .fill 3, 0
q_ready: .fill 3, 0
msg_ptr: .fill 2, 0
ai_wave_l: .byte 0
ai_wave_h: .byte 0
ai_wave_size: .byte 0
ai_harv_t: .byte 0
shown_cr_l: .byte 0
shown_cr_h: .byte 0
.assert "mux tables below $8000", * <= $8000, true

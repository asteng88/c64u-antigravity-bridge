// ==============================================================================
// TORNADO - Cyclone-Inspired Archipelago Rescue for the Commodore 64
//
// Replicates Vortex Software's 1985 classic CYCLONE on the C64:
//   * Title screen (loading.kla + 3-voice SID music)
//   * 32x32-tile tropical archipelago with Home Base Helipad & 5 Supply Crates
//   * 8-direction helicopter flight + ground shadow + altitude / landing
//   * Double-size animated Cyclone with wind turbulence & HUD proximity alert
//   * Instrument HUD: CRATES, FUEL bar, ALT/STATUS, CYCLONE alert, SCORE, LIVES
//   * Press M for full-screen Tactical Archipelago Map (Heli, Crates, Cyclone)
//
// Controls: Joystick Port 2 (or W/A/S/D), FIRE / SPACE = Land / Take Off, M = Map
// Build:    python tools/build/build_tool.py game_dev/tornado/build.py
// Target:   KickAssembler v5.x
// ==============================================================================

.encoding "screencode_upper"

#import "../music/music_config.asm"

// ------------------------------------------------------------------------------
// Generated Assets (imported first so KickAssembler sees .const definitions)
// ------------------------------------------------------------------------------
* = $4800 "Charset"
        .import binary "../map/tornado_charset.bin"

* = $5000 "Sprites"
#import "../sprites/sprites.asm"

* = $6000 "Loading Koala"
        .import binary "../loading/loading.kla", 2

* = $8800 "Iso Terrain & Map"
#import "../map/tornado_iso.asm"

// ------------------------------------------------------------------------------
// Hardware & Memory Constants
// ------------------------------------------------------------------------------
.const SCREEN    = $4000
.const SPRPTR    = SCREEN + $03F8
.const COLRAM    = $D800
.const KLA_SCR   = $7F40
.const KLA_COL   = $8328
.const KLA_BG    = $8710
.const SPRPTR0   = (sprite_bank - $4000) / 64

.const VIEW_TW   = 20           // 20 tiles wide (40 chars)
.const VIEW_TH   = 11           // 11 tiles tall (22 chars; rows 22-24 = HUD)
.const BASE_TX   = 3            // Home Base Helipad tile X (cols 3-4)
.const BASE_TY   = 55           // Home Base Helipad tile Y (rows 55-56)
.const MAX_PEOPLE = 12           // most survivors in one mission
.const MAP_MARKS = MAX_PEOPLE
.const LAST_LEVEL = 25
// runners go from the heli on the H to the hangar door (sprite anchors)
.const RUN_X0 = 53
.const RUN_Y0 = $68             // + $300 = 872
.const RUN_TX = 93
.const RUN_TY = $4E             // + $300 = 846
.const GRAB_TIME = 72            // frames from capture to explosion (~1.4 s)
.const WINCH_TOL = 6            // px: survivor must be this close below the heli
.const WINCH_MAX = 19           // px: longest rope the hook frames can draw
.const WINCH_HOLD = 12          // px: drift allowed while the hook goes down
.const HUD_SPLIT = 215          // first raster IRQ of the HUD split (see raster_irq)
.const HUD_DIV   = 21           // HUD screen rows: divider line,
.const HUD_ROW1  = 22           //   fuel / alt / score,
.const HUD_ROW2  = 23           //   rescue / lives / status
.const NUM_TORNS = 3            // 3 active cyclones across the 64x64 world

// ------------------------------------------------------------------------------
// Zero Page ($02..$5F, safe below $FB music driver)
// ------------------------------------------------------------------------------
.label zp_ptr    = $02
.label zp_dst    = $04
.label zp_col    = $06
.label zp_tmp    = $08
.label zp_row    = $09
.label zp_cx     = $0A
.label zp_tx     = $0B
.label zp_ty     = $0C
.label zp_dx     = $0D
.label zp_dy     = $0E
.label zp_cy     = $0F

// Helicopter world position in 8.4 sub-tile units (0..511 pixels -> tx = hi*16 + lo>>4)
// Simpler & exact: 16-bit world pixel coordinates (0..511)
.label heli_wx_lo = $10
.label heli_wx_hi = $11
.label heli_wy_lo = $12
.label heli_wy_hi = $13
.label heli_vx    = $14         // signed velocity (-2..+2)
.label heli_vy    = $15         // signed velocity (-2..+2)
.label heli_dir   = $16         // 0..7 (N NE E SE S SW W NW)
.label heli_alt   = $17         // 0 = landed, 1..12 = flying altitude
.label heli_land  = $18         // 0 = airborne, 1 = landed

// Camera top-left in tiles / chars / world pixels
.label cam_tx     = $19         // kept for compatibility (cam_cx >> 1)
.label cam_ty     = $1A         // kept for compatibility (cam_cy >> 1)
.label cam_dirty  = $1B
.label cam_px_lo  = $3C         // 16-bit camera X in world pixels (0..704)
.label cam_px_hi  = $3D
.label cam_py_lo  = $3E         // 16-bit camera Y in world pixels (0..848)
.label cam_py_hi  = $3F
.label cam_cx     = $55         // char X = cam_px >> 3 (0..88)
.label cam_cy     = $56         // char Y = cam_py >> 3 (0..106)
.label fine_x     = $52         // 7 - (cam_px & 7)
.label fine_y     = $53         // 7 - (cam_py & 7)
.label irq_phase  = $54         // 0=split 215, 1=split 219/223, 2=VBL restore (252)
.label back_page  = $57         // 0 = draw $4000, 4 = draw $4400
.label d018_val   = $58         // $02 ($4000) or $12 ($4400): page shown after the last publish

// Frame hand-off between the main loop and the raster IRQ
.label disp_d011  = $59         // registers the IRQ restores at line 252
.label disp_d016  = $5A
.label disp_d018  = $5B
.label st_ready   = $5C         // 1 = published frame waiting for the IRQ
.label st_color   = $5D         // 1 = published frame flips the page (colour RAM rebuild)
.label flip_cool  = $5E         // IRQ -> main: colour RAM was rebuilt this frame
.label step_dx    = $5F         // camera char step this frame (-1/0/+1)
.label step_dy    = $60
.label flip_pend  = $61         // back page built, flip on next publish
.label nx_d011    = $62         // published register values
.label nx_d016    = $63
.label nx_d018    = $64
.label cam_hold   = $65         // no char step allowed this frame
.label dc_scol    = $66         // draw_col scratch
.label dc_tx      = $67
.label jvec       = $68         // 2 bytes
.label lag_x      = $6A         // signed camera lag (px) vs. the centred heli
.label lag_y      = $6B
.label winch_dx   = $6C         // hook X offset from the heli (signed px)
.label w_tx       = $6D         // winch scratch: target hook X offset
.label w_lt       = $6E         //   target rope length
.label w_tol      = $6F         //   tolerance for survivor_offset
.label w_v        = $70
.label w_hi       = $71
.label grab_timer = $72         // >0: heli caught by a cyclone (frames to the blast)
.label grab_idx   = $73         // which cyclone has it
// isometric renderer scratch (RowCodes, draw_col, terrain_at)
.label rc_cy      = $74
.label rc_cx      = $75
.label rc_n       = $76
.label rc_pu      = $77         // 2 bytes
.label rc_pl      = $79         // 2 bytes
.label rc_s       = $7B
.label rc_i       = $7C
.label rc_l       = $7D
.label rc_c       = $7E
.label dc_q       = $7F         // 2 bytes
.label dc_u       = $81         // 2 bytes
.label dc_l       = $83         // 2 bytes
.label tg_x       = $85         // 2 bytes
.label tg_y       = $87         // 2 bytes
.label tg_yb      = $89
.label tg_cx      = $8A
.label tg_q       = $8B
.label rc_lh      = $8C         // RowCodes: half type << 4 scratch
.label elev_cur   = $8D         // px the ground under the heli is raised (0..48)
.label elev_lvl   = $8E         // its level (0..3); 3 = the control tower
.label tg_half    = $8F         // cell_at: 0 left half, 1 right half
.label ht_sh      = $90         // height_at scratch
// levels
.label level      = $91         // mission 1..25
.label n_people   = $92         // survivors to rescue this mission
.label rng        = $93
.label night      = $94         // 1 = night mission
.label pull_mask  = $95         // cyclone pull every (mask + 1) frames
.label gale_r     = $96         // wind radius in tiles
.label spd_mask   = $97         // cyclones move every (mask + 1) frames
.label home_mask  = $98         // hunting cyclone re-aims every (mask + 1) frames
.label pull_px    = $99         // px per pull
.label col_night  = $9A         // COLMAP holds night colours ($80) or day (0)
.label pull_cnt   = $9B
.label lv_isl     = $9C         // place_people scratch
.label lv_k       = $9D
.label lv_m       = $9E
// tactical map scratch
.label map_r      = $9F
.label map_c      = $A0
.label map_j0     = $A1
.label map_j1     = $A2
.label map_mask   = $A3
.label map_base   = $A4
.label map_f      = $A5
.label map_par    = $A6
.label map_msb    = $A7
.label map_bit    = $A8
.label map_t0     = $A9
.label map_t1     = $AA
.label map_t2     = $AB
.label map_t3     = $AC
// drop-off at the helipad
.label aboard     = $AD         // survivors in the heli, not saved until dropped off
.label run_state  = $AE         // 1 = one of them is running to the hangar
.label run_x      = $AF         // runner's world x (sprite anchor, < 256)
.label run_y      = $B0         // runner's world y - $300
.label run_delay  = $B1         // frames before the next one climbs out
.label on_pad     = $B2         // 1 = landed on the H this frame
.label sp_try     = $B3         // spawn_person scratch

// Cyclone world pixel coordinates (0..1023, 3 cyclones)
.label torn_wx_lo    = $40      // 3 bytes ($40..$42)
.label torn_wx_hi    = $43      // 3 bytes ($43..$45)
.label torn_wy_lo    = $46      // 3 bytes ($46..$48)
.label torn_wy_hi    = $49      // 3 bytes ($49..$4B)
.label torn_vx       = $4C      // 3 bytes ($4C..$4E)
.label torn_vy       = $4F      // 3 bytes ($4F..$51)
.label torn_near     = $22      // 0 = far, 1 = wind warning, 2 = danger!
.label torn_near_idx = $38      // index (0..2) of nearest cyclone
.label torn_cur_idx  = $39      // loop scratch for sprite/tornado update

// Game state
.label anim_cnt   = $23
.label fuel       = $24         // 0..64
.label fuel_sub   = $25
.label crates_got = $26         // 0..5
.label lives      = $27         // 3..0
.label score_lo   = $28
.label score_hi   = $29
.label joy_bits   = $2A         // active-high: 1=U,2=D,4=L,8=R,16=F
.label fire_prev  = $2B
.label map_prev   = $2C
.label sfx_timer  = $2D
.label expl_timer = $2E
.label msg_state  = $2F         // 0=normal, 1=refuel, 2=crate, 3=return, 4=win, 5=over

// Active survivor screen coords (computed per frame)
.label crate_vis  = $30
.label crate_sx_lo = $31
.label crate_sx_hi = $32
.label crate_sy   = $33

// Rescue winch state
.label winch_state = $34        // 0=idle, 1=lowering hook, 2=lifting survivor
.label winch_idx   = $35        // 0..4 survivor index
.label winch_y     = $36        // 0..16 cable extension
.label winch_sub   = $37        // frame divider for slow lift
.label music_on    = $3A        // 1 = BGM on, 0 = BGM off
.label mus_prev    = $3B        // Q key debounce

// ------------------------------------------------------------------------------
// Program Entry
// ------------------------------------------------------------------------------
BasicUpstart2(boot)

* = $0900 "Ground Heights"
#import "../map/tornado_heights.asm"
* = * "Survivor Spots"
#import "../map/tornado_extra.asm"

* = $1000 "Music"
music_bin:
        .import c64 "../music/music.prg"

* = $1800 "Code"
boot:
        sei
        cld
        ldx #$FF
        txs
        lda #$35                // Bank out BASIC & KERNAL, keep I/O
        sta $01
        lda #$7F                // Disable CIA1 & CIA2 IRQs
        sta $DC0D
        sta $DD0D
        lda $DC0D               // Acknowledge pending CIA IRQs
        lda $DD0D
        lda #$FF                // CIA1 Port A = output (keyboard cols)
        sta $DC02
        lda #$00                // CIA1 Port B = input (keyboard rows)
        sta $DC03
        lda #$00
        sta $D01A               // Disable VIC IRQs (we poll $D012)
        sta $D019
        sta $D015               // Disable sprites
        lda #<nmi_rti
        sta $FFFA
        lda #>nmi_rti
        sta $FFFB
        lda #<nmi_rti
        sta $FFFE
        lda #>nmi_rti
        sta $FFFF
        lda $DD02
        ora #$03                // CIA2 PA0-PA1 output for VIC bank
        sta $DD02
        lda #$01                // title music on (Q on the title toggles it)
        sta music_on
        lda #$00
        sta col_night
        jsr build_colmap        // Per-char colour map used by the scroller
        lda $7FFF               // Koala screen byte that doubles as the VIC idle byte
        sta kla_idle_save
        cli
        jmp title_screen

nmi_rti:
        rti

// ------------------------------------------------------------------------------
// Title Screen (Koala loading.kla)
// ------------------------------------------------------------------------------
title_screen:
        sei                     // the game's raster split must not touch the title
        lda #$00
        sta $D01A
        lda #$0F
        sta $D019
        lda #<nmi_rti
        sta $FFFE
        lda #>nmi_rti
        sta $FFFF
        cli
        jsr music_silence
        lda music_on            // the tune starts from the top on every title
        beq !no_mus+
        jsr $1000
!no_mus:
        lda kla_idle_save       // put back the Koala byte cleared for the HUD gap
        sta $7FFF
        lda #$00
        sta $D015
        ldx #$00
!lp:
        lda KLA_SCR + $000, x
        sta $5C00 + $000, x
        lda KLA_SCR + $100, x
        sta $5C00 + $100, x
        lda KLA_SCR + $200, x
        sta $5C00 + $200, x
        lda KLA_SCR + $2E8, x
        sta $5C00 + $2E8, x

        lda KLA_COL + $000, x
        sta COLRAM + $000, x
        lda KLA_COL + $100, x
        sta COLRAM + $100, x
        lda KLA_COL + $200, x
        sta COLRAM + $200, x
        lda KLA_COL + $2E8, x
        sta COLRAM + $2E8, x
        inx
        bne !lp-

        lda $DD00
        and #$FC
        ora #$02                // VIC Bank 1 ($4000-$7FFF)
        sta $DD00

        lda #$3B                // Bitmap mode on
        sta $D011
        lda #$18                // Multicolor on
        sta $D016
        lda #$78                // Screen $5C00, Bitmap $6000
        sta $D018
        lda KLA_BG
        sta $D020
        sta $D021

!wait_t:
        jsr title_frame
        jsr read_input
        lda joy_bits
        and #$10
        beq !wait_t-
!wait_rel:
        jsr title_frame
        jsr read_input
        lda joy_bits
        and #$10
        bne !wait_rel-

// ------------------------------------------------------------------------------
// New Game Initialization
// ------------------------------------------------------------------------------
new_game:
        lda #$03
        sta lives
        lda #$00
        sta score_lo
        sta score_hi
        sta crates_got
        sta expl_timer
        sta sfx_timer
        sta winch_state
        sta winch_y
        sta winch_sub
        sta mus_prev
        jsr music_silence       // music is for the title only

        lda $D012               // a different set of islands each game
        eor anim_cnt
        ora #$01
        sta rng
        lda #$01
        sta level
start_mission:
        jsr setup_level
        jsr level_intro

respawn_heli:
        jsr lose_aboard         // a crash loses whoever was on board
        // Place helicopter over the Home Base Helipad (ground point = pad centre;
        // heli px 44, 872 = $002C, $0368)
        lda #RUN_X0             // over the centre of the H (heli px 53, 866)
        sta heli_wx_lo
        lda #$00
        sta heli_wx_hi
        lda #$62
        sta heli_wy_lo
        lda #$03
        sta heli_wy_hi
        lda #$00
        sta heli_vx
        sta heli_vy
        sta heli_land
        lda #$0C
        sta heli_alt
        lda #$02                // Facing East
        sta heli_dir
        lda #64
        sta fuel
        lda #$00
        sta fuel_sub
        sta expl_timer
        sta msg_state
        sta winch_state
        sta grab_timer
        sta elev_cur
        sta elev_lvl

        // Center camera on base (cam_px = 0, cam_py = 872 - 88 = 784 = $0310)
        lda #$00
        sta cam_px_lo
        sta cam_px_hi
        sta cam_cx
        sta cam_tx
        lda #$0A                // cam_py = 866 - 88 = 778 = $030A
        sta cam_py_lo
        lda #$03
        sta cam_py_hi
        lda #97
        sta cam_cy
        lda #48
        sta cam_ty
        lda #$07
        sta fine_x
        sta fine_y

setup_game_vic:
        lda #$00                // idle lines above the HUD show byte $7FFF: blank it
        sta $7FFF
        lda #$00
        sta $D015
        lda $DD00
        and #$FC
        ora #$02                // VIC Bank 1 ($4000-$7FFF)
        sta $DD00
        lda #$1B                // Text mode
        sta $D011
        lda #$18                // Multicolor charset
        sta $D016
        lda #$02                // Screen $4000, Charset $4800
        sta $D018
        sta d018_val
        lda #$04                // Back buffer = $4400
        sta back_page

        // Reset the main loop <-> IRQ frame hand-off
        lda #$00
        sta st_ready
        sta st_color
        sta flip_pend
        sta flip_cool
        sta cam_dirty
        sta lag_x
        sta lag_y
        sta vic_sh + $15
        lda #$02
        sta disp_d018
        lda #$17                // 24 rows, fine_y = 7
        sta disp_d011
        lda #$17                // 38 cols, multicolor, fine_x = 7
        sta disp_d016

        lda #$00                // Crisp black arcade border
        sta $D020
        jsr set_palette
        lda night               // night colours in the colour map
        beq !cm+
        lda #$80
!cm:    cmp col_night
        beq !cm_ok+
        sta col_night
        jsr build_colmap
!cm_ok:

        lda #$00
        sta $D025
        lda #$01
        sta $D026

        // Sprite config: 0=Heli, 2=Torn0(2x), 3=Person, 4=Hook, 5=Torn1(2x), 6=Torn2(2x), 7=Shadow
        lda #$6D                // Multicolor on 0, 2, 3, 5, 6
        sta $D01C
        lda #$64                // Double height+width on Sprites 2, 5, 6 (Tornadoes)
        sta $D017
        sta $D01D
        lda #$07                // Yellow heli
        sta $D027
        lda #$00                // Black shadow
        sta $D02E
        lda #$03                // Cyan tornado 0
        sta $D029
        lda #$0A                // Light red survivor
        sta $D02A
        lda #$01                // White rescue winch hook
        sta $D02B
        lda #$03                // Cyan tornado 1 & 2
        sta $D02C
        sta $D02D

        jsr draw_hud_frame
        jsr draw_map
        jsr update_hud

        // Install 2-split raster IRQ for smooth playfield scroll + fixed HUD
        sei
        lda #<raster_irq
        sta $FFFE
        lda #>raster_irq
        sta $FFFF
        lda #$00
        sta irq_phase
        lda #HUD_SPLIT
        sta $D012
        lda #$01
        sta $D019
        sta $D01A
        cli

// ------------------------------------------------------------------------------
// Main Game Loop
// ------------------------------------------------------------------------------
game_loop:
        // Frame sync is publish_frame at the end of each pass (the raster IRQ
        // consumes the published state once per frame), so no wait here.
        jsr update_sfx
        inc anim_cnt

        // Check if exploding
        lda expl_timer
        beq !alive+
        dec expl_timer
        bne !expl_draw+
        // Explosion finished
        dec lives
        beq game_over
        jmp respawn_heli
!expl_draw:
        jsr update_sprites_expl
        jsr publish_frame
        jmp game_loop

!alive:
        jsr read_input
        jsr check_map_key
        jsr update_heli
        jsr update_camera
        jsr update_elev
        jsr update_tornado
        jsr check_collisions
        jsr update_unload
        jsr update_fuel

        // Camera crossed a char: shift the back buffer (fast) instead of a
        // full redraw. HUD refresh is skipped that frame to stay in budget.
        lda cam_dirty
        beq !no_redraw+
        jsr scroll_map
!no_redraw:
        jsr update_sprites
        lda cam_dirty
        bne !skip_hud+
        jsr update_hud
!skip_hud:
        lda #$00
        sta cam_dirty
        jsr publish_frame

        // Check mission win (msg_state == 4)
        lda msg_state
        cmp #$04
        beq mission_won
        jmp game_loop

// ------------------------------------------------------------------------------
// Mission Complete / Game Over
// ------------------------------------------------------------------------------
mission_won:
!fin:   jsr wait_vbl            // let the drop-off beep finish first
        jsr update_sfx
        lda sfx_timer
        bne !fin-
        jsr music_silence
        jsr show_banner_win
!won_w: jsr wait_vbl
        jsr read_input
        lda joy_bits
        and #$10
        beq !won_w-
        inc level
        lda level
        cmp #LAST_LEVEL + 1
        bcs !all_done+
        jmp start_mission       // next mission: new islands, stronger cyclones
!all_done:
        jmp title_screen

game_over:
        lda #$00
        sta $D015
        jsr music_silence
        jsr show_banner_over

!wait_end:
        jsr wait_vbl
        jsr read_input
        lda joy_bits
        and #$10
        beq !wait_end-
!wait_end_rel:
        jsr wait_vbl
        jsr read_input
        lda joy_bits
        and #$10
        bne !wait_end_rel-
        jmp title_screen

// ------------------------------------------------------------------------------
// Input (Joystick Port 2 + W/A/S/D + Space + M)
// ------------------------------------------------------------------------------
read_input:
        lda #$FF
        sta $DC00
        lda $DC00               // Port 2 active-low
        eor #$1F
        and #$1F
        sta joy_bits

        // Keyboard fallback: W (col 1, row 1), A (col 1, row 2), S (col 1, row 5), D (col 2, row 2)
        lda #$FD                // Col 1
        sta $DC00
        lda $DC01
        tax
        and #$02                // W -> Up
        bne !no_w+
        lda joy_bits
        ora #$01
        sta joy_bits
!no_w:
        txa
        and #$20                // S -> Down
        bne !no_s+
        lda joy_bits
        ora #$02
        sta joy_bits
!no_s:
        txa
        and #$04                // A -> Left
        bne !no_a+
        lda joy_bits
        ora #$04
        sta joy_bits
!no_a:
        lda #$FB                // Col 2
        sta $DC00
        lda $DC01
        and #$04                // D -> Right
        bne !no_d+
        lda joy_bits
        ora #$08
        sta joy_bits
!no_d:
        lda #$7F                // Col 7
        sta $DC00
        lda $DC01
        and #$10                // SPACE -> Fire
        bne !no_sp+
        lda joy_bits
        ora #$10
        sta joy_bits
!no_sp:
        lda #$FF
        sta $DC00
        rts

check_map_key:
        lda #$EF                // Col 4
        sta $DC00
        lda $DC01
        and #$10                // M key (col 4, row 4)
        pha
        lda #$FF
        sta $DC00
        pla
        bne !not_m+
        lda map_prev
        bne !done_m+
        lda #$01
        sta map_prev
        jsr show_tactical_map
!done_m:
        rts
!not_m:
        lda #$00
        sta map_prev
        rts

// One title-screen frame: wait for the beam, play the tune if it is on, Q toggles it
title_frame:
        jsr wait_vbl
        lda music_on
        beq !q+
        jsr $1003
!q:     jmp check_music_key

// Silence all 3 voices, keep master volume $0F for the sound effects
music_silence:
        lda #$00
        sta $D404
        sta $D40B
        sta $D412
        lda #$0F
        sta $D418
        rts

// Q on the title screen: music on / off
check_music_key:
        lda #$7F                // Col 7
        sta $DC00
        lda $DC01
        and #$40                // Q key (col 7, row 6)
        pha
        lda #$FF
        sta $DC00
        pla
        bne !not_q+
        lda mus_prev
        bne !done_q+
        lda #$01
        sta mus_prev
        lda music_on
        eor #$01
        sta music_on
        beq !mus_off+
        jsr $1000               // Re-init SID music cleanly
        rts
!mus_off:
        jmp music_silence
!done_q:
        rts
!not_q:
        lda #$00
        sta mus_prev
        rts

// ------------------------------------------------------------------------------
// Helicopter Physics, Altitude & Landing
// ------------------------------------------------------------------------------
update_heli:
        lda grab_timer
        beq !free+
        jmp heli_grabbed
!free:
        // Fire toggles landing / takeoff
        lda joy_bits
        and #$10
        beq !no_fire+
        lda fire_prev
        bne !after_fire+
        lda #$01
        sta fire_prev
        lda heli_land
        eor #$01
        sta heli_land
        jmp !after_fire+
!no_fire:
        lda #$00
        sta fire_prev
!after_fire:

        // Adjust altitude toward target (0 if landed, 12 if airborne), 1 px
        // every 2nd frame so take-off and landing are visible (~0.5 s)
        lda anim_cnt
        and #$01
        bne !alt_ok+
        lda heli_land
        bne !descend+
        lda heli_alt
        cmp #$0C
        bcs !alt_ok+
        inc heli_alt
        jmp !alt_ok+
!descend:
        lda heli_alt
        beq !alt_ok+
        dec heli_alt
!alt_ok:

        // If landed (alt == 0), zero velocity and skip steering
        lda heli_alt
        bne !flying+
        lda #$00
        sta heli_vx
        sta heli_vy
        rts

!flying:
        // Steering + momentum every 2nd frame for smooth Cyclone inertia
        lda anim_cnt
        and #$01
        bne !apply_vel+

        lda joy_bits
        and #$0C                // Left/Right
        beq !damp_x+
        and #$04
        beq !try_rt+
        lda #$FE                // -2
        sta heli_vx
        jmp !steer_y+
!try_rt:
        lda #$02                // +2
        sta heli_vx
        jmp !steer_y+
!damp_x:
        lda #$00
        sta heli_vx

!steer_y:
        lda joy_bits
        and #$03                // Up/Down
        beq !damp_y+
        and #$01
        beq !try_dn+
        lda #$FE                // -2
        sta heli_vy
        jmp !upd_dir+
!try_dn:
        lda #$02                // +2
        sta heli_vy
        jmp !upd_dir+
!damp_y:
        lda #$00
        sta heli_vy

!upd_dir:
        // Update 8-way facing direction from joy_bits
        lda joy_bits
        and #$0F
        beq !apply_vel+
        tax
        lda dir_lut, x
        bmi !apply_vel+
        sta heli_dir

!apply_vel:
        // Severe wind turbulence when near cyclone: fight controls, pull inward, swirl & buffet
        lda torn_near
        bne !in_gale+
        jmp !no_wind+
!in_gale:
        // Resist steering: every 2nd frame, cancel half the player's thrust
        lda anim_cnt
        and #$01
        beq !gale_pull+
        lda heli_vx
        beq !g_vy+
        bpl !g_vx_p+
        inc heli_vx
        jmp !g_vy+
!g_vx_p:
        dec heli_vx
!g_vy:
        lda heli_vy
        beq !gale_pull+
        bpl !g_vy_p+
        inc heli_vy
        jmp !gale_pull+
!g_vy_p:
        dec heli_vy
!gale_pull:
        // Pull helicopter toward nearest tornado center (every 2nd frame)
        lda anim_cnt            // how often and how hard grow with the mission
        and pull_mask
        bne !gale_gust+
        lda pull_px
        sta pull_cnt
!pull_again:
        ldx torn_near_idx
        lda heli_wx_lo
        cmp torn_wx_lo, x
        lda heli_wx_hi
        sbc torn_wx_hi, x
        bcs !pull_w+
        inc heli_wx_lo
        bne !pull_y+
        inc heli_wx_hi
        jmp !pull_y+
!pull_w:
        lda heli_wx_lo
        bne !pw_dec+
        dec heli_wx_hi
!pw_dec:
        dec heli_wx_lo
!pull_y:
        lda heli_wy_lo
        cmp torn_wy_lo, x
        lda heli_wy_hi
        sbc torn_wy_hi, x
        bcs !pull_n+
        inc heli_wy_lo
        bne !gale_gust+
        inc heli_wy_hi
        jmp !gale_gust+
!pull_n:
        lda heli_wy_lo
        bne !pn_dec+
        dec heli_wy_hi
!pn_dec:
        dec heli_wy_lo
        dec pull_cnt
        beq !gale_gust+
        jmp !pull_again-
!gale_gust:
        // Swirling crosswind & altitude buffeting every 4th frame
        lda anim_cnt
        and #$03
        bne !no_wind+
        lda anim_cnt
        and #$08
        beq !gust_neg+
        inc heli_wx_lo
        bne !g_alt+
        inc heli_wx_hi
        jmp !g_alt+
!gust_neg:
        lda heli_wx_lo
        bne !gn_dec+
        dec heli_wx_hi
!gn_dec:
        dec heli_wx_lo
!g_alt:
        lda anim_cnt
        and #$04
        beq !alt_up+
        lda heli_alt
        cmp #$03
        bcc !no_wind+
        dec heli_alt
        jmp !no_wind+
!alt_up:
        lda heli_alt
        cmp #$0C
        bcs !no_wind+
        inc heli_alt
!no_wind:

        // Apply heli_vx to 16-bit world X (clamp 16..1007 = $0010..$03EF)
        lda heli_vx
        beq !move_y+
        bmi !vx_neg+
        lda heli_wx_lo
        clc
        adc heli_vx
        sta heli_wx_lo
        lda heli_wx_hi
        adc #$00
        sta heli_wx_hi
        cmp #$03
        bcc !move_y+
        bne !clamp_x_hi+
        lda heli_wx_lo
        cmp #$EF
        bcc !move_y+
!clamp_x_hi:
        lda #$03
        sta heli_wx_hi
        lda #$EF
        sta heli_wx_lo
        jmp !move_y+
!vx_neg:
        lda heli_wx_lo
        clc
        adc heli_vx
        sta heli_wx_lo
        lda heli_wx_hi
        sbc #$00
        sta heli_wx_hi
        bpl !chk_min_x+
        lda #$10
        sta heli_wx_lo
        lda #$00
        sta heli_wx_hi
        jmp !move_y+
!chk_min_x:
        bne !move_y+
        lda heli_wx_lo
        cmp #$10
        bcs !move_y+
        lda #$10
        sta heli_wx_lo

!move_y:
        // Apply heli_vy to 16-bit world Y (clamp 16..1007 = $0010..$03EF)
        lda heli_vy
        beq !done_move+
        bmi !vy_neg+
        lda heli_wy_lo
        clc
        adc heli_vy
        sta heli_wy_lo
        lda heli_wy_hi
        adc #$00
        sta heli_wy_hi
        cmp #$03
        bcc !done_move+
        bne !clamp_y_hi+
        lda heli_wy_lo
        cmp #$EF
        bcc !done_move+
!clamp_y_hi:
        lda #$03
        sta heli_wy_hi
        lda #$EF
        sta heli_wy_lo
        jmp !done_move+
!vy_neg:
        lda heli_wy_lo
        clc
        adc heli_vy
        sta heli_wy_lo
        lda heli_wy_hi
        sbc #$00
        sta heli_wy_hi
        bpl !chk_min_y+
        lda #$10
        sta heli_wy_lo
        lda #$00
        sta heli_wy_hi
        rts
!chk_min_y:
        bne !done_move+
        lda heli_wy_lo
        cmp #$10
        bcs !done_move+
        lda #$10
        sta heli_wy_lo
!done_move:
        rts

// ------------------------------------------------------------------------------
// Smooth 1-Pixel Camera Follow + Hardware Fine-Scroll + Raster Split IRQ
// ------------------------------------------------------------------------------
update_camera:
        lda #$00
        sta step_dx
        sta step_dy
        lda flip_cool           // set by the IRQ when it rebuilt colour RAM
        sta cam_hold
        lda #$00
        sta flip_cool
        // Update heli tile coords (zp_tx, zp_ty) for collision checks
        lda heli_wx_lo
        lsr
        lsr
        lsr
        lsr
        sta zp_tmp
        lda heli_wx_hi
        asl
        asl
        asl
        asl
        ora zp_tmp
        sta zp_tx               // 0..63

        lda heli_wy_lo
        lsr
        lsr
        lsr
        lsr
        sta zp_tmp
        lda heli_wy_hi
        asl
        asl
        asl
        asl
        ora zp_tmp
        sta zp_ty               // 0..63

        // ---- X axis ----
        // Camera lag eases back to 0 (1 px/frame) while the heli is not moving on this axis
        lda heli_vx
        bne !x_nodecay+
        lda lag_x
        beq !x_nodecay+
        bmi !x_lagneg+
        dec lag_x
        jmp !x_nodecay+
!x_lagneg:
        inc lag_x
!x_nodecay:
        // cam_px = clamp(heli_wx - 160 + lag_x, 0, 704 = $02C0)
        lda heli_wx_lo
        sec
        sbc #160
        sta cam_px_lo
        lda heli_wx_hi
        sbc #$00
        sta cam_px_hi
        ldx #$00
        lda lag_x
        bpl !x_lagpos+
        dex
!x_lagpos:
        clc
        adc cam_px_lo
        sta cam_px_lo
        txa
        adc cam_px_hi
        sta cam_px_hi
        bpl !x_nonneg+
        lda #$00
        sta cam_px_lo
        sta cam_px_hi
        jmp !x_ready+
!x_nonneg:
        cmp #$02
        bcc !x_ready+
        bne !x_clamp+
        lda cam_px_lo
        cmp #$C1
        bcc !x_ready+
!x_clamp:
        lda #$C0
        sta cam_px_lo
        lda #$02
        sta cam_px_hi
!x_ready:
        // new char = cam_px >> 3
        lda cam_px_lo
        lsr
        lsr
        lsr
        sta zp_tmp
        lda cam_px_hi
        asl
        asl
        asl
        asl
        asl
        ora zp_tmp
        sta zp_row              // new char position
        cmp cam_cx
        beq !x_fine+
        ldx cam_hold
        beq !x_step+
        // Colour RAM was rebuilt last frame, so no char step now: park the
        // camera on the edge of its current char and keep the difference as
        // camera lag. While the heli keeps moving the lag stays, so the X and
        // Y char steps stop landing on back-to-back frames.
        ldx #$00                // new < cur -> lowest px of current char
        bcc !x_hold+          // C still from cmp
        ldx #$07                // new > cur -> highest px of current char
!x_hold:
        stx zp_tmp
        lda #$00
        sta zp_dy
        lda cam_cx
        asl
        rol zp_dy
        asl
        rol zp_dy
        asl
        rol zp_dy
        ora zp_tmp
        sta zp_dx               // zp_dx/zp_dy = parked camera position
        sec
        sbc heli_wx_lo
        clc
        adc #160           // lag = parked - (heli_wx - 160)
        tax
        clc
        adc #6
        cmp #13
        bcs !x_step_new+      // more than 6 px of lag: take the step anyway
        stx lag_x
        lda zp_dx
        sta cam_px_lo
        lda zp_dy
        sta cam_px_hi
        jmp !x_fine+
!x_step_new:
        lda zp_row
!x_step:
        tax
        sec
        sbc cam_cx
        sta step_dx              // +1 / -1 (anything else -> full redraw)
        stx cam_cx
        txa
        lsr
        sta cam_tx
        lda #$01
        sta cam_dirty
!x_fine:
        // fine_x = 7 - (cam_px_lo & 7)
        lda cam_px_lo
        and #$07
        eor #$07
        sta fine_x

        // ---- Y axis ----
        // Camera lag eases back to 0 (1 px/frame) while the heli is not moving on this axis
        lda heli_vy
        bne !y_nodecay+
        lda lag_y
        beq !y_nodecay+
        bmi !y_lagneg+
        dec lag_y
        jmp !y_nodecay+
!y_lagneg:
        inc lag_y
!y_nodecay:
        // cam_py = clamp(heli_wy - 88 + lag_y, 0, 848 = $0350)
        lda heli_wy_lo
        sec
        sbc #88
        sta cam_py_lo
        lda heli_wy_hi
        sbc #$00
        sta cam_py_hi
        ldx #$00
        lda lag_y
        bpl !y_lagpos+
        dex
!y_lagpos:
        clc
        adc cam_py_lo
        sta cam_py_lo
        txa
        adc cam_py_hi
        sta cam_py_hi
        bpl !y_nonneg+
        lda #$00
        sta cam_py_lo
        sta cam_py_hi
        jmp !y_ready+
!y_nonneg:
        cmp #$03
        bcc !y_ready+
        bne !y_clamp+
        lda cam_py_lo
        cmp #$51
        bcc !y_ready+
!y_clamp:
        lda #$50
        sta cam_py_lo
        lda #$03
        sta cam_py_hi
!y_ready:
        // new char = cam_py >> 3
        lda cam_py_lo
        lsr
        lsr
        lsr
        sta zp_tmp
        lda cam_py_hi
        asl
        asl
        asl
        asl
        asl
        ora zp_tmp
        sta zp_row              // new char position
        cmp cam_cy
        beq !y_fine+
        ldx cam_hold
        beq !y_step+
        // Colour RAM was rebuilt last frame, so no char step now: park the
        // camera on the edge of its current char and keep the difference as
        // camera lag. While the heli keeps moving the lag stays, so the X and
        // Y char steps stop landing on back-to-back frames.
        ldx #$00                // new < cur -> lowest px of current char
        bcc !y_hold+          // C still from cmp
        ldx #$07                // new > cur -> highest px of current char
!y_hold:
        stx zp_tmp
        lda #$00
        sta zp_dy
        lda cam_cy
        asl
        rol zp_dy
        asl
        rol zp_dy
        asl
        rol zp_dy
        ora zp_tmp
        sta zp_dx               // zp_dx/zp_dy = parked camera position
        sec
        sbc heli_wy_lo
        clc
        adc #88           // lag = parked - (heli_wy - 88)
        tax
        clc
        adc #6
        cmp #13
        bcs !y_step_new+      // more than 6 px of lag: take the step anyway
        stx lag_y
        lda zp_dx
        sta cam_py_lo
        lda zp_dy
        sta cam_py_hi
        jmp !y_fine+
!y_step_new:
        lda zp_row
!y_step:
        tax
        sec
        sbc cam_cy
        sta step_dy              // +1 / -1 (anything else -> full redraw)
        stx cam_cy
        txa
        lsr
        sta cam_ty
        lda #$01
        sta cam_dirty
!y_fine:
        // fine_y = 7 - (cam_py_lo & 7)
        lda cam_py_lo
        and #$07
        eor #$07
        sta fine_y
        rts

// The main loop publishes one complete frame state (nx_d011/d016/d018 + the
// sprite shadow) with publish_frame; the IRQ applies all of it in the border
// at once, so fine scroll, screen page and sprites can never disagree.
// HUD split. Playfield row 20 (the last) is shown on lines 208+fine_y ..
// 215+fine_y. The HUD must always start on the same raster line AND right
// after row 20 in the VIC's row counter: if a partial "gap" row is displayed
// for some fine_y values and not others, the HUD shows different screen rows
// from frame to frame (the flicker seen while scrolling up and down).
// So the VIC is kept idle between row 20 and the HUD for every fine_y:
//   line 215: YSCROLL=6 - after row 20 has started for every fine_y, before
//             line 216 can start a row (fine_y = 0). No line 215..219 is = 6.
//   line 219: YSCROLL=7 - no line 219..222 is = 7, so the next row starts on
//             line 223 for every fine_y: the HUD (screen rows 21-23).
//   line 223: 40 columns, XSCROLL=0, written before the HUD's first pixel
//             (and after row 20's last line, 222 at most).
// The idle lines in between show byte $7FFF, which is cleared during play.
raster_irq:
        pha
        lda irq_phase
        beq !split1+
        cmp #$01
        beq !split2+
        jmp !irq_top+
!split1:
        lda #$16                // 24 rows, YSCROLL = 6
        sta $D011
        lda #219
        sta $D012
        lda #$01
        sta irq_phase
        sta $D019
        pla
        rti
!split2:
        lda #$17                // 24 rows, YSCROLL = 7: HUD starts at 223
        sta $D011
        txa
        pha
        ldx #$18                // HUD: 40 cols, XSCROLL = 0
        lda #223
!wt:    cmp $D012
        bne !wt-
        stx $D016
        lda #252
        sta $D012
        lda #$02
        sta irq_phase
        lda #$01
        sta $D019
        pla
        tax
        pla
        rti

!irq_top:
        txa
        pha
        tya
        pha
        // Line 252 (HUD finished): apply the published frame
        lda st_ready
        beq !keep+
        jsr apply_state
        lda st_color
        beq !keep+
        // Page flip: rebuild colour RAM rows 0-20 from the colour map. Rows
        // 0-6 are done by line ~295 and rows 7-20 by line ~69 of the next
        // frame, well ahead of the beam (row 0 starts at line 48 + fine_y).
        // The main loop is parked in publish_frame, so cam_cx/cam_cy still
        // describe the page that was just shown.
        jsr patch_colsrc
        jsr cc_pass1
        jsr cc_pass2
        lda #$00
        sta st_color
        lda #$01
        sta flip_cool
!keep:
        lda disp_d018
        sta $D018
        lda disp_d011
        sta $D011
        lda disp_d016
        sta $D016
        lda #HUD_SPLIT
        sta $D012
        lda #$00
        sta irq_phase
        lda #$01
        sta $D019
!irq_out:
        pla
        tay
        pla
        tax
        pla
        rti

apply_state:
        lda nx_d018
        sta disp_d018
        sta $D018
        lda nx_d011
        sta disp_d011
        sta $D011
        lda nx_d016
        sta disp_d016
        sta $D016
        .for (var i = 0; i <= $10; i++) {
            lda vic_sh + i
            sta $D000 + i
        }
        lda vic_sh + $15
        sta $D015
        lda #$00
        sta st_ready
        rts

// Main loop: hand the finished frame to the IRQ and wait until it is shown.
publish_frame:
        lda flip_pend
        beq !nf+
        lda back_page
        eor #$04
        sta back_page
        lda d018_val
        eor #$10
        sta d018_val
        lda #$00
        sta flip_pend
        lda #$01
        sta st_color
!nf:
        lda d018_val
        sta nx_d018
        lda fine_y
        ora #$10
        sta nx_d011
        lda fine_x
        ora #$10
        sta nx_d016
        lda #$01
        sta st_ready
!w:     lda st_ready
        bne !w-
        rts

// ------------------------------------------------------------------------------
// Cyclone AI & Movement (3 active cyclones across 64x64 world)
// ------------------------------------------------------------------------------
update_tornado:
        lda anim_cnt
        and spd_mask            // faster cyclones in later missions
        beq !t_go+
        rts
!t_go:
        ldx #(NUM_TORNS - 1)
!t_loop:
        // Tornado 0 gently steers toward helicopter every 64 frames; 1 & 2 patrol
        cpx #$00
        bne !t_move+
        lda anim_cnt
        and home_mask           // the hunter re-aims more often later on
        bne !t_move+
        lda heli_wx_hi
        cmp torn_wx_hi, x
        bcc !t_left+
        bne !t_right+
        lda heli_wx_lo
        cmp torn_wx_lo, x
        bcc !t_left+
!t_right:
        lda #$01
        sta torn_vx, x
        jmp !t_sy+
!t_left:
        lda #$FF
        sta torn_vx, x
!t_sy:
        lda heli_wy_hi
        cmp torn_wy_hi, x
        bcc !t_up+
        bne !t_down+
        lda heli_wy_lo
        cmp torn_wy_lo, x
        bcc !t_down+
!t_up:
        lda #$FF
        sta torn_vy, x
        jmp !t_move+
!t_down:
        lda #$01
        sta torn_vy, x

!t_move:
        lda torn_wx_lo, x
        clc
        adc torn_vx, x
        sta torn_wx_lo, x
        lda torn_vx, x
        bmi !tvx_n+
        lda torn_wx_hi, x
        adc #$00
        sta torn_wx_hi, x
        cmp #$03
        bcc !t_my+
        bne !tvx_b+
        lda torn_wx_lo, x
        cmp #$DF
        bcc !t_my+
!tvx_b:
        lda #$FF
        sta torn_vx, x
        jmp !t_my+
!tvx_n:
        lda torn_wx_hi, x
        sbc #$00
        sta torn_wx_hi, x
        bpl !t_my+
        lda #$20
        sta torn_wx_lo, x
        lda #$00
        sta torn_wx_hi, x
        lda #$01
        sta torn_vx, x

!t_my:
        lda torn_wy_lo, x
        clc
        adc torn_vy, x
        sta torn_wy_lo, x
        lda torn_vy, x
        bmi !tvy_n+
        lda torn_wy_hi, x
        adc #$00
        sta torn_wy_hi, x
        cmp #$03
        bcc !t_next+
        bne !tvy_b+
        lda torn_wy_lo, x
        cmp #$DF
        bcc !t_next+
!tvy_b:
        lda #$FF
        sta torn_vy, x
        jmp !t_next+
!tvy_n:
        lda torn_wy_hi, x
        sbc #$00
        sta torn_wy_hi, x
        bpl !t_next+
        lda #$20
        sta torn_wy_lo, x
        lda #$00
        sta torn_wy_hi, x
        lda #$01
        sta torn_vy, x
!t_next:
        dex
        bmi !t_done+
        jmp !t_loop-
!t_done:
        rts

// ------------------------------------------------------------------------------
// Collisions: Crates, Helipad Refuel/Win, Cyclone & Sea Landing
// ------------------------------------------------------------------------------
check_collisions:
        lda #$00
        sta on_pad
        lda grab_timer          // caught or already exploding: nothing to check
        ora expl_timer
        beq !cc_go+
        rts
!cc_go:
        // Terrain under the heli's ground point (the middle of its shadow)
        lda heli_wx_lo
        clc
        adc #11
        sta tg_x
        lda heli_wx_hi
        adc #$00
        sta tg_x + 1
        lda heli_wy_lo
        clc
        adc #22
        sta tg_y
        lda heli_wy_hi
        adc #$00
        sta tg_y + 1
        lda tg_y                // the shadow lies elev_cur px higher on screen
        sec
        sbc elev_cur
        sta tg_y
        bcs !gy+
        dec tg_y + 1
!gy:
        // Flying into the control tower (level 3: too tall to climb over)
        lda heli_alt
        beq !no_tower+
        lda elev_lvl
        cmp #$03
        bcc !no_tower+
        jmp !crash_now+
!no_tower:
        jsr terrain_at
        tax
        lda terrain_flags, x
        sta zp_tmp              // TF_LAND=1, TF_BASE=2, TF_HAZARD=4

        // If landed (alt == 0): safe on LAND/BASE, crash in SEA (0) or HAZARD (4)
        lda heli_alt
        bne !not_landed+
        lda zp_tmp
        and #TF_HAZARD
        beq !not_haz+
        jmp !crash_now+
!not_haz:
        lda zp_tmp
        and #(TF_LAND | TF_BASE)
        bne !land_ok+
        jmp !crash_now+
!land_ok:
        // Refuel slowly if on BASE (TF_BASE tile or within Helipad area tx 2..5, ty 54..57)
        lda zp_tmp              // landed on the H
        and #TF_BASE
        beq !on_land+
        lda #$01
        sta on_pad
        lda crates_got
        cmp n_people
        bcc !refuel_pad+
        lda #$04                // MISSION COMPLETE!
        sta msg_state
        rts
!refuel_pad:
        lda aboard              // people getting out, or refuelling
        ora run_state
        beq !rf+
        lda #$08                // DROP OFF!
        .byte $2C
!rf:    lda #$01                // REFUELING!
        sta msg_state
        lda fuel
        cmp #64
        bcc !inc_f+
        jmp !chk_torn+
!inc_f:
        inc fuel_sub
        lda fuel_sub
        cmp #$06                // Slowly replenish 1 unit every 6 frames
        bcs !do_refuel+
        jmp !chk_torn+
!do_refuel:
        lda #$00
        sta fuel_sub
        inc fuel
        jmp !chk_torn+
!on_land:
        lda #$00
        sta msg_state
        jmp !chk_torn+

!not_landed:
        lda winch_state
        beq !chk_gale_msg+
        lda #$06                // WINCHING!
        sta msg_state
        jmp !chk_crates+
!chk_gale_msg:
        lda torn_near
        beq !chk_ret_msg+
        lda #$07                // GALE TURB!
        sta msg_state
        jmp !chk_crates+
!chk_ret_msg:
        lda crates_got          // everyone picked up: head for the base
        clc
        adc aboard
        cmp n_people
        bcc !normal_msg+
        lda #$03                // RETURN TO BASE!
        sta msg_state
        jmp !chk_crates+
!normal_msg:
        lda #$00
        sta msg_state

!chk_crates:
        // If winch is active, advance lowering (1) or slow lifting (2)
        lda winch_state
        beq !find_survivor+
        jmp !do_winch+

!find_survivor:
        // Start the winch when a survivor stands within WINCH_TOL px of the
        // spot on the ground straight below the hovering helicopter.
        // Sprite-anchor maths (all sprites share one anchor): the heli's ground
        // point is (heli_wx, heli_wy + 12), a survivor's feet sit 3 px above
        // their anchor's ground row, so the target is (heli_wx, heli_wy + 9).
        lda heli_land
        bne !c_none+
        lda heli_alt
        cmp #6
        bcc !c_none+
        ldx #(MAX_PEOPLE - 1)
!c_lp:
        lda crate_active, x
        beq !c_next+
        ldy #WINCH_TOL
        jsr survivor_offset
        bcc !c_next+
        stx winch_idx
        lda #$01                // Lowering hook
        sta winch_state
        lda #$00
        sta winch_y
        sta winch_dx
        sta winch_sub
        lda #$06
        sta msg_state
        jmp !chk_torn+
!c_next:
        dex
        bpl !c_lp-
!c_none:
        jmp !chk_torn+

!do_winch:
        ldx winch_idx
        lda winch_state
        cmp #$02
        bne !winch_lower+
        jmp !winch_lift+

!winch_lower:
        // Hook goes down (and sideways) until its tip is at the survivor's
        // hands; cancelled if the heli lands or drifts off the survivor.
        lda heli_land
        bne !winch_cancel+
        ldy #WINCH_HOLD
        jsr survivor_offset     // also leaves the X offset in w_tx
        bcs !wl_track+
!winch_cancel:
        lda #$00
        sta winch_state
        jmp !chk_torn+
!wl_track:
        // Rope length to the hands: the hook tip (heli drawn Y + 14 + n) meets
        // the hands (survivor Y + 10); heli drawn Y = heli_wy + 12 - heli_alt,
        // so n = (crate_wy - heli_wy) - 16 + heli_alt, kept in 0..WINCH_MAX.
        lda crate_wy_lo, x
        sec
        sbc heli_wy_lo
        sec
        sbc #16
        clc
        adc heli_alt
        clc
        adc elev_cur
        bpl !lt_pos+
        lda #$00
!lt_pos:
        cmp #WINCH_MAX + 1
        bcc !lt_ok+
        lda #WINCH_MAX
!lt_ok: sta w_lt
        // Step the hook 1 px every 3rd frame on each axis
        inc winch_sub
        lda winch_sub
        cmp #$03
        bcs !wl_step+
        jmp !w_done+
!wl_step:
        lda #$00
        sta winch_sub
        lda winch_dx
        cmp w_tx
        beq !wl_y+
        sec
        sbc w_tx
        bmi !wl_xr+
        dec winch_dx
        jmp !wl_y+
!wl_xr: inc winch_dx
!wl_y:
        lda winch_y
        cmp w_lt
        beq !wl_at+
        bcc !wl_down+
        dec winch_y
        jmp !w_done+
!wl_down:
        inc winch_y
        jmp !w_done+
!wl_at:
        lda winch_dx
        cmp w_tx
        bne !w_done+
        lda #$02                // Hooked: short pause, then the lift
        sta winch_state
        lda #(256 - 11)         // winch_sub counts up to 5: ~16 frames
        sta winch_sub
        jmp !w_done+

!winch_lift:
        // Reel the survivor up into the heli (1 px every 5th frame) while
        // they swing in under it.
        inc winch_sub
        lda winch_sub
        cmp #$05
        bne !w_done+
        lda #$00
        sta winch_sub
        lda winch_dx
        beq !wf_y+
        bmi !wf_r+
        dec winch_dx
        jmp !wf_y+
!wf_r:  inc winch_dx
!wf_y:
        lda winch_y
        beq !w_aboard+
        dec winch_y
        bne !w_done+
!w_aboard:
        // Survivor safely aboard!
        ldx winch_idx
        lda #$00
        sta crate_active, x
        sta winch_state
        sta winch_dx
        inc aboard              // on board: saved only when dropped off at the H
        lda #$02
        sta msg_state
        jsr play_sfx_pickup
!w_done:

!chk_torn:
        // Find minimum tile distance across all 3 cyclones
        lda #$FF
        sta zp_row              // best_dist = 255
        ldx #(NUM_TORNS - 1)
!ct_lp:
        lda torn_wx_lo, x
        lsr
        lsr
        lsr
        lsr
        sta zp_tmp
        lda torn_wx_hi, x
        asl
        asl
        asl
        asl
        ora zp_tmp
        sec
        sbc zp_tx
        bcs !tdx_pos+
        eor #$FF
        adc #$01
!tdx_pos:
        sta zp_dx

        lda torn_wy_lo, x
        lsr
        lsr
        lsr
        lsr
        sta zp_tmp
        lda torn_wy_hi, x
        asl
        asl
        asl
        asl
        ora zp_tmp
        sec
        sbc zp_ty
        bcs !tdy_pos+
        eor #$FF
        adc #$01
!tdy_pos:
        // Max(|dx|, |dy|)
        cmp zp_dx
        bcs !use_dy+
        lda zp_dx
!use_dy:
        cmp zp_row
        bcs !ct_next+
        sta zp_row
        stx torn_near_idx
!ct_next:
        dex
        bpl !ct_lp-

        lda zp_row
        cmp #$02
        bcc !hit_torn+
        cmp gale_r              // wind radius grows with the mission
        bcc !near_torn+
        lda #$00
        sta torn_near
        rts
!near_torn:
        lda #$01
        sta torn_near
        rts
!hit_torn:
        lda #$02
        sta torn_near
        lda heli_alt            // Safe if landed!
        beq !safe_ground+
        // Caught: the cyclone pulls the heli in, spins it, then it explodes
        lda #GRAB_TIME
        sta grab_timer
        lda torn_near_idx
        sta grab_idx
        lda #$00
        sta winch_state         // drop any rescue in progress
        sta heli_land
        sta heli_vx
        sta heli_vy
!safe_ground:
        rts
!crash_now:                     // landed in the sea or on rocks
        lda #36
        sta expl_timer
        jsr play_sfx_boom
        rts


// ------------------------------------------------------------------------------
// Caught by a cyclone: pulled into the funnel, spun faster and faster while
// being lifted, then the heli explodes. Replaces update_heli while grab_timer > 0.
// ------------------------------------------------------------------------------
heli_grabbed:
        ldx grab_idx
        // Funnel middle: the 48x42 cyclone sprite's centre (24, 20) over the
        // heli body's centre (11, 10 + 12 - heli_alt)
        lda torn_wx_lo, x
        clc
        adc #12
        sta w_v
        lda torn_wx_hi, x
        adc #$00
        sta w_hi
        ldx #$00                // X axis
        jsr grab_step
        jsr grab_step           // 2 px per frame
        ldx grab_idx
        lda torn_wy_lo, x
        clc
        adc #8
        sta w_v
        lda torn_wy_hi, x
        adc #$00
        sta w_hi
        ldx #$02                // Y axis
        jsr grab_step
        jsr grab_step

        // Lifted up the funnel (altitude 12 -> 15)
        lda anim_cnt
        and #$07
        bne !g_spin+
        lda heli_alt
        cmp #15
        bcs !g_spin+
        inc heli_alt
!g_spin:
        // Spin: one direction step every 4, then 2, then every frame
        lda grab_timer
        cmp #(GRAB_TIME * 2 / 3)
        bcs !g_slow+
        cmp #(GRAB_TIME / 3)
        bcs !g_mid+
        jmp !g_turn+
!g_slow:
        lda anim_cnt
        and #$03
        bne !g_count+
        jmp !g_turn+
!g_mid:
        lda anim_cnt
        and #$01
        bne !g_count+
!g_turn:
        lda heli_dir
        clc
        adc #$01
        and #$07
        sta heli_dir
!g_count:
        dec grab_timer
        bne !g_done+
        lda #36                 // Torn apart
        sta expl_timer
        jsr play_sfx_boom
!g_done:
        rts

// Move heli world coord X=0 (x) / X=2 (y) 1 px toward the 16-bit w_v/w_hi
grab_step:
        lda heli_wx_lo, x
        cmp w_v
        lda heli_wx_hi, x
        sbc w_hi
        bcc !up+
        lda heli_wx_lo, x
        cmp w_v
        bne !down+
        lda heli_wx_hi, x
        cmp w_hi
        beq !done+
!down:  lda heli_wx_lo, x
        bne !nb+
        dec heli_wx_hi, x
!nb:    dec heli_wx_lo, x
        rts
!up:    inc heli_wx_lo, x
        bne !done+
        inc heli_wx_hi, x
!done:  rts

// ------------------------------------------------------------------------------
// Fuel Consumption
// ------------------------------------------------------------------------------
update_fuel:
        lda heli_alt
        beq !f_done+            // Landed uses no fuel
        inc fuel_sub
        lda fuel_sub
        cmp #42
        bcc !f_done+
        lda #$00
        sta fuel_sub
        lda fuel
        beq !out_fuel+
        dec fuel
        bne !f_done+
!out_fuel:
        lda #36
        sta expl_timer
        jsr play_sfx_boom
!f_done:
        rts

// Survivor X relative to the heli's ground point. In: X = survivor, Y = px
// tolerance. Out: C=1 if |crate_wx - heli_wx| <= Y and
// |crate_wy - (heli_wy + 9)| <= Y; w_tx = crate_wx - heli_wx (signed byte).
survivor_offset:
        sty w_tol
        lda crate_wx_lo, x
        sec
        sbc heli_wx_lo
        sta w_tx
        sta w_v
        lda crate_wx_hi, x
        sbc heli_wx_hi
        jsr in_tol
        bcc !out+
        lda crate_wy_lo, x
        sec
        sbc heli_wy_lo
        sta w_v
        lda crate_wy_hi, x
        sbc heli_wy_hi
        sta w_hi
        lda w_v
        sec
        sbc #9
        sta w_v
        lda w_hi
        sbc #$00
        sta w_hi
        lda w_v                 // ground point is elev_cur px higher on screen
        clc
        adc elev_cur
        sta w_v
        lda w_hi
        adc #$00
        jsr in_tol
!out:   rts

// In: A = high byte, w_v = low byte of a signed 16-bit value.
// Out: C=1 if |value| <= w_tol.
in_tol:
        beq !pos+
        cmp #$FF
        bne !no+
        lda w_v
        beq !no+                // -256
        eor #$FF
        clc
        adc #$01
        jmp !cmp+
!pos:   lda w_v
!cmp:   cmp w_tol
        beq !yes+
        bcc !yes+
!no:    clc
        rts
!yes:   sec
        rts

// ------------------------------------------------------------------------------
// Sprites Update (World -> Screen Mapping)
// ------------------------------------------------------------------------------
update_sprites:
        // Camera pixel origin = (cam_px_lo/hi, cam_py_lo/hi)
        // Sprite X = world_x - cam_px + 31; Sprite Y = world_y - cam_py + 55
        // Sprite 0: Helicopter
        lda heli_wx_lo
        sec
        sbc cam_px_lo
        sta zp_ptr
        lda heli_wx_hi
        sbc cam_px_hi
        sta zp_tmp
        lda zp_ptr
        clc
        adc #31
        sta vic_sh + $00
        lda zp_tmp
        adc #$00
        sta zp_tmp              // bit 0 = MSB for heli & shadow

        // heli_wy is where the heli is over the ground; the shadow is drawn
        // there (+12) and the heli sits heli_alt px above it, so landing
        // brings the heli down onto a shadow that stays put.
        lda heli_wy_lo
        sec
        sbc cam_py_lo
        clc
        adc #55 + 12
        sec
        sbc elev_cur            // on top of hills and roofs
        sta vic_sh + $0F        // shadow Y (ground)
        sec
        sbc heli_alt
        sta vic_sh + $01        // heli Y

        // Heli frame
        lda anim_cnt
        and #$02
        lsr
        clc
        adc heli_dir
        adc heli_dir
        clc
        adc #SPRPTR0 + SPR_HELI
        sta SPRPTR + 0

        // Sprite 7: Shadow on the ground, pushed sideways by the sun more the
        // higher the heli is (0 px landed .. 4 px at full altitude). Sprite 7
        // has the lowest priority, so survivors and the hook show on top of it.
        ldx heli_alt
        lda vic_sh + $00
        clc
        adc shadow_dx, x
        sta vic_sh + $0E
        lda heli_dir
        clc
        adc #SPRPTR0 + SPR_SHADOW
        sta SPRPTR + 7

        // SpriteEnable mask
        lda #$81
        sta zp_cx               // enable 0 (heli) & 7 (shadow)
        lda zp_tmp
        beq !no_msb01+
        lda #$81
        jmp !msb_set01+
!no_msb01:
        lda #$00
!msb_set01:
        sta zp_cy               // vic_sh + $10 MSB accumulator

        // Sprites 2, 5, 6: 3 Cyclones (zero-flash 16-bit viewport check)
        ldx #(NUM_TORNS - 1)
!torn_spr_lp:
        stx torn_cur_idx
        lda torn_wx_lo, x
        sec
        sbc cam_px_lo
        sta zp_ptr
        lda torn_wx_hi, x
        sbc cam_px_hi
        sta zp_tmp              // rx_hi
        // sx = rx + 31 (16-bit)
        lda zp_ptr
        clc
        adc #31
        sta zp_ptr              // sx_lo
        lda zp_tmp
        adc #$00
        sta zp_tmp              // sx_hi
        beq !tsx_ok+            // sx_hi == 0 -> visible (1..255)
        cmp #$01
        bne !torn_spr_next+
        lda zp_ptr
        cmp #95                 // 256 + 95 = 351 (right edge)
        bcs !torn_spr_next+
!tsx_ok:
        lda torn_wy_lo, x
        sec
        sbc cam_py_lo
        pha
        lda torn_wy_hi, x
        sbc cam_py_hi
        sta zp_dy               // ry_hi
        pla
        clc
        adc #55
        pha
        lda zp_dy
        adc #$00
        bne !torn_spr_next_p+   // sy_hi != 0 -> offscreen
        pla
        cmp #18
        bcc !torn_spr_next+
        cmp #196
        bcs !torn_spr_next+
        // Visible! Write vic_sh + $00+slot*2, vic_sh + $01+slot*2, MSB, PTR, Enable
        ldy torn_spr_slot, x
        sta vic_sh + $01, y
        lda zp_ptr
        sta vic_sh + $00, y
        lda zp_tmp
        beq !ts_no_msb+
        lda zp_cy
        ora torn_spr_bit, x
        sta zp_cy
!ts_no_msb:
        txa
        clc
        adc anim_cnt
        lsr
        lsr
        and #$03
        clc
        adc #SPRPTR0 + SPR_TORNADO
        ldy torn_spr_idx, x
        sta SPRPTR, y
        lda zp_cx
        ora torn_spr_bit, x
        sta zp_cx
        jmp !torn_spr_next+
!torn_spr_next_p:
        pla
!torn_spr_next:
        dex
        bmi !torn_spr_done+
        jmp !torn_spr_lp-
!torn_spr_done:

!do_crate_spr:
        lda run_state           // a survivor running from the H to the hangar
        beq !no_run+
        lda run_x
        sec
        sbc cam_px_lo
        sta zp_ptr
        lda #$00
        sbc cam_px_hi
        sta zp_tmp
        lda zp_ptr
        clc
        adc #31
        sta vic_sh + $06
        lda zp_tmp
        adc #$00
        beq !rn_lo+
        lda zp_cy
        ora #$08
        sta zp_cy
!rn_lo: lda run_y
        clc
        adc #<($300 + 55)
        sec
        sbc cam_py_lo
        sta vic_sh + $07
        jmp !cs_frame+
!no_run:
        // Sprite 4: winch hook hanging from the heli's centre (row 10). For a
        // rope of n = winch_y px: frame n>>2 (cable 4*(n>>2) px), moved down
        // n&3 px, so the hook tip is at heli Y + 14 + n and the cable always
        // starts under the heli's body. X = heli X + winch_dx.
        lda winch_state
        beq !cs_scan+
        ldy #$00
        lda winch_dx
        bpl !hk_p+
        dey
!hk_p:  clc
        adc vic_sh + $00
        sta vic_sh + $08
        tya
        adc #$00
        sta zp_tmp
        lda zp_cy               // heli MSB (bit 0)
        and #$01
        clc
        adc zp_tmp
        and #$01
        beq !hk_no_msb+
        lda zp_cy
        ora #$10
        sta zp_cy
!hk_no_msb:
        lda winch_y
        cmp #WINCH_MAX + 1
        bcc !hk_len+
        lda #WINCH_MAX
!hk_len:
        sta zp_tmp
        and #$03
        clc
        adc #10
        adc vic_sh + $01
        sta vic_sh + $09
        lda zp_tmp
        lsr
        lsr
        clc
        adc #SPRPTR0 + SPR_HOOK
        sta SPRPTR + 4
        lda zp_cx
        ora #$10
        sta zp_cx

        lda winch_state
        cmp #$02
        bne !cs_winch+
        // Survivor on the hook: hands (row 10) on the hook tip (heli Y + 14 + n)
        lda vic_sh + $08
        sta vic_sh + $06
        lda vic_sh + $01
        clc
        adc #$04
        adc zp_tmp
        sta vic_sh + $07
        lda zp_cy
        and #$10
        beq !cs_lift_msb+
        lda zp_cy
        ora #$08
        sta zp_cy
!cs_lift_msb:
        jmp !cs_frame+
!cs_winch:
        ldx winch_idx           // show the survivor being winched
        jmp !cs_act+

!cs_scan:
        // Find first active crate inside viewport
        ldx #(MAX_PEOPLE - 1)
!cs_lp:
        lda crate_active, x
        bne !cs_act+
        jmp !cs_next+
!cs_act:
        lda crate_wx_lo, x
        sec
        sbc cam_px_lo
        sta zp_ptr
        lda crate_wx_hi, x
        sbc cam_px_hi
        bmi !cs_next+
        cmp #$02
        bcs !cs_next+
        cmp #$01
        bne !cs_x_ok+
        lda zp_ptr
        cmp #64
        bcs !cs_next+
!cs_x_ok:
        sta zp_tmp
        lda crate_wy_lo, x
        sec
        sbc cam_py_lo
        pha
        lda crate_wy_hi, x
        sbc cam_py_hi
        bne !cs_next_p+
        pla
        cmp #168
        bcs !cs_next+
        clc
        adc #55
        sta vic_sh + $07
        lda zp_ptr
        clc
        adc #31
        sta vic_sh + $06
        lda zp_tmp
        adc #$00
        beq !cs_frame+
        lda zp_cy
        ora #$08
        sta zp_cy
!cs_frame:
        lda anim_cnt
        lsr
        lsr
        and #$03
        clc
        adc #SPRPTR0 + SPR_PERSON
        sta SPRPTR + 3
        lda zp_cx
        ora #$08
        sta zp_cx
        jmp !apply_spr+
!cs_next_p:
        pla
!cs_next:
        dex
        bmi !apply_spr+
        jmp !cs_lp-

!apply_spr:
        // Mirror sprite pointers to second screen page ($47F8)
        ldx #$07
!spr_mir:
        lda SPRPTR, x
        sta SPRPTR + $0400, x
        dex
        bpl !spr_mir-
        lda zp_cy
        sta vic_sh + $10
        lda zp_cx
        sta vic_sh + $15
        rts

update_sprites_expl:
        lda #$01
        sta vic_sh + $15
        lda #36
        sec
        sbc expl_timer
        lsr
        lsr
        lsr
        cmp #$06
        bcc !ef_ok+
        lda #$05
!ef_ok:
        clc
        adc #SPRPTR0 + SPR_EXPLOSION
        sta SPRPTR + 0
        sta SPRPTR + $0400 + 0  // both pages (the shown one alternates)
        lda #$08                // Orange explosion
        sta $D027
        rts

// ------------------------------------------------------------------------------
// Playfield rendering (double-buffered chars, colour RAM from a colour map)
//
// The world is isometric (tools/isotiles/iso_tool.py): 32x16 px diamonds in
// staggered rows 8 px apart. Character (cx, cy) sits between diamond U =
// iso_map[cy][i + (q >> 1)] and L = iso_map[cy + 1][i + s], where s = cy & 1,
// a = cx + 4 - 2s, q = a & 3, i = a >> 2; its screen code is
// iso_chr[q*256 + Uhalf*16 + Lhalf] and its colour char_col[code].
//
// Chars: the back page is built while the front page is shown. When the camera
// crosses one char (any of 8 directions) the front page is copied into the back
// page shifted by one char (~8k cycles) and only the new edge row/column is
// drawn. A full redraw is only used for jumps (start, respawn, tactical map).
// Colour RAM: COLMAP holds the colour of every world char (128 x 128, built at
// boot). On a page flip the raster IRQ copies the 21 visible rows from it.
// ------------------------------------------------------------------------------
.const COLMAP = $A000           // first COLMAP row (cc_pass operands start here)
.function cmRow(r) {
    .if (r < 96) .return $A000 + r * 128      // $A000-$CFFF (RAM under BASIC)
    .return $E000 + (r - 96) * 128            // $E000-$EFFF (RAM under KERNAL)
}

// Full redraw of the back page for (cam_cx, cam_cy)
draw_map:
        lda #$00
        sta zp_row
!lp:
        jsr draw_row
        inc zp_row
        lda zp_row
        cmp #21
        bcc !lp-
        jmp finish_back

// Camera moved by (step_dx, step_dy) chars: shift the front page into the back
// page and draw the new edges.
scroll_map:
        lda flip_pend           // back page already rebuilt but not shown yet
        bne draw_map
        lda step_dx
        clc
        adc #$01
        cmp #$03
        bcs draw_map
        sta zp_tmp              // dx + 1
        lda step_dy
        clc
        adc #$01
        cmp #$03
        bcs draw_map
        sta zp_dx
        asl
        adc zp_dx               // (dy + 1) * 3
        adc zp_tmp              // + (dx + 1)
        ldx back_page
        beq !p0+
        adc #9                  // back page $4400 variants
!p0:    tax
        lda shift_lo, x
        sta jvec
        lda shift_hi, x
        sta jvec + 1
        jsr !jump+

        lda step_dx
        beq !no_col+
        bmi !left+
        lda #39
        .byte $2C               // BIT abs: skip the next lda
!left:  lda #$00
        jsr draw_col
!no_col:
        lda step_dy
        beq finish_back
        bmi !top+
        lda #20
        .byte $2C
!top:   lda #$00
        sta zp_row
        jsr draw_row
finish_back:
        lda #$01
        sta flip_pend
        rts
!jump:  jmp (jvec)

// Draw screen row zp_row (0..20) of the back page
draw_row:
        lda cam_cy
        clc
        adc zp_row
        sta rc_cy
        lda cam_cx
        sta rc_cx
        lda #40
        sta rc_n
        ldx zp_row
        lda full_row_lo, x
        sta zp_dst
        lda full_row_hi, x
        clc
        adc back_page
        sta zp_dst + 1
        jmp row_chr

// One world char row -> rc_n screen codes at (zp_dst), from world char
// (rc_cx, rc_cy). Map bytes hold two half types (left << 4 | right); q0/q1
// characters use U's right half and L's left half, q2/q3 U's left and L's
// right: index q*256 + U*16 + L into iso_chr. ~36 cycles per char.
row_chr:
        ldx rc_cy
        lda iso_row_lo, x
        sta rc_pu
        lda iso_row_hi, x
        sta rc_pu + 1
        txa
        and #$01
        sta rc_s
        clc
        adc iso_row_lo + 1, x   // L row pointer, already offset by s
        sta rc_pl
        lda iso_row_hi + 1, x
        adc #$00
        sta rc_pl + 1
        lda rc_s                // a = cx + 4 - 2s
        asl
        eor #$FF
        sec
        adc rc_cx
        clc
        adc #$04
        pha
        lsr
        lsr
        sta rc_i
        tay
        lda (rc_pl), y
        sta rc_l
        lda #$00
        sta rc_c
        pla
        and #$03
        beq !q0+
        cmp #$02
        beq !q2x+
        bcs !e3+
        lda rc_l                // start on q1
        lsr
        lsr
        lsr
        lsr
        sta rc_lh
        ldy rc_i
        lda (rc_pu), y
        asl
        asl
        asl
        asl
        ora rc_lh
        tax
        ldy #$00
        jmp !q1+
!e3:    ldy rc_i                // start on q3
        iny
        lda (rc_pu), y
        and #$F0
        sta rc_lh
        lda rc_l
        and #$0F
        ora rc_lh
        tax
        ldy #$00
        jmp !q3+
!q0:    ldy rc_i
        lda (rc_pl), y
        sta rc_l
        lsr
        lsr
        lsr
        lsr
        sta rc_lh               // L left half
        lda (rc_pu), y
        asl
        asl
        asl
        asl                     // U right half << 4
        ora rc_lh
        tax
        ldy rc_c
        lda iso_chr, x
        sta (zp_dst), y
        iny
        cpy rc_n
        bcs !done+
!q1:    lda iso_chr + $100, x
        sta (zp_dst), y
        iny
        cpy rc_n
        bcs !done+
        sty rc_c
!q2x:   ldy rc_i
        iny
        lda (rc_pu), y
        and #$F0                // U left half << 4
        sta rc_lh
        lda rc_l
        and #$0F                // L right half
        ora rc_lh
        tax
        ldy rc_c
        lda iso_chr + $200, x
        sta (zp_dst), y
        iny
        cpy rc_n
        bcs !done+
!q3:    lda iso_chr + $300, x
        sta (zp_dst), y
        iny
        cpy rc_n
        bcs !done+
        sty rc_c
        inc rc_i
        jmp !q0-
!done:  rts

// Draw screen column A (0 or 39) of the back page, rows 0..20
draw_col:
        sta dc_scol
        clc
        adc cam_cx
        sta dc_tx               // world char column
        // Per row parity s: a = cx + 4 - 2s, q = a & 3, i = a >> 2
        ldx #$01
!pre:   txa
        asl
        eor #$FF
        sec
        adc dc_tx
        clc
        adc #$04
        pha
        and #$03
        tay
        tya
        sta dc_q, x
        tya
        lsr
        sta zp_tmp              // q >> 1
        pla
        lsr
        lsr                     // i
        pha
        clc
        adc zp_tmp
        sta dc_u, x             // U index: i + (q >> 1)
        stx zp_tmp
        pla
        clc
        adc zp_tmp
        sta dc_l, x             // L index: i + s
        dex
        bpl !pre-

        lda back_page
        clc
        adc #>SCREEN
        sta zp_dst + 1
        lda dc_scol
        sta zp_dst
        lda #$00
        sta zp_cx               // screen row
!lp:
        lda cam_cy
        clc
        adc zp_cx
        tax
        lda iso_row_lo, x
        sta rc_pu
        lda iso_row_hi, x
        sta rc_pu + 1
        lda iso_row_lo + 1, x
        sta rc_pl
        lda iso_row_hi + 1, x
        sta rc_pl + 1
        txa
        and #$01
        tax                     // s
        lda dc_q, x
        cmp #$02
        bcs !hq+
        ldy dc_l, x             // q0/q1: U right half, L left half
        lda (rc_pl), y
        lsr
        lsr
        lsr
        lsr
        sta rc_lh
        ldy dc_u, x
        lda (rc_pu), y
        asl
        asl
        asl
        asl
        ora rc_lh
        tay
        lda dc_q, x
        bne !p1+
        lda iso_chr, y
        jmp !st+
!p1:    lda iso_chr + $100, y
        jmp !st+
!hq:    ldy dc_l, x             // q2/q3: U left half, L right half
        lda (rc_pl), y
        and #$0F
        sta rc_lh
        ldy dc_u, x
        lda (rc_pu), y
        and #$F0
        ora rc_lh
        tay
        lda dc_q, x
        cmp #$03
        beq !p3+
        lda iso_chr + $200, y
        jmp !st+
!p3:    lda iso_chr + $300, y
!st:    ldy #$00
        sta (zp_dst), y
        lda zp_dst
        clc
        adc #40
        sta zp_dst
        bcc !nc+
        inc zp_dst + 1
!nc:    inc zp_cx
        lda zp_cx
        cmp #21
        bcc !lp-
        rts

// Shifted page copies: back[r][c] = front[r + dy][c + dx] for rows 0..20.
// The edge row/column reads junk that draw_row/draw_col then overwrite.
.macro ShiftCopy(src, dst, off) {
        ldx #39
lp:
    .for (var r = 0; r < 21; r++) {
        lda src + r * 40 + off, x
        sta dst + r * 40, x
    }
        dex
        bmi done
        jmp lp
done:   rts
}
.const SHIFT_SIZE = 135          // bytes per ShiftCopy variant
// variant index = page * 9 + (dy + 1) * 3 + (dx + 1); index 4 / 13 = no move
.function shiftAddr(i) {
    .var k = mod(i, 9)
    .if (k == 4) .return shift_none
    .var n = floor(i / 9) * 8 + k
    .if (k > 4) .eval n = n - 1
    .return shift_base + n * SHIFT_SIZE
}
shift_base:
.for (var pg = 0; pg < 2; pg++) {
    .for (var dy = -1; dy <= 1; dy++) {
        .for (var dx = -1; dx <= 1; dx++) {
            .if (dx != 0 || dy != 0) {
                .if (pg == 0) {
                    ShiftCopy(SCREEN + $0400, SCREEN, dy * 40 + dx)
                } else {
                    ShiftCopy(SCREEN, SCREEN + $0400, dy * 40 + dx)
                }
            }
        }
    }
}
.errorif (* - shift_base) != 16 * SHIFT_SIZE, "ShiftCopy size changed"
shift_none: rts
shift_lo: .fill 18, <shiftAddr(i)
shift_hi: .fill 18, >shiftAddr(i)

// Colour RAM rebuild, run by the raster IRQ on a page flip. The lda operands
// are patched by patch_colsrc to point at the right COLMAP rows.
// address of the lda operand that reads COLMAP for screen row r
.function ccOp(r) {
    .if (r < 7) .return cc_pass1 + 3 + r * 6
    .if (r < 14) .return cc_pass2 + 3 + (r - 7) * 6
    .return cc_pass3 + 3 + (r - 14) * 6
}
cc_pass1:
        ldx #39
!lp:
    .for (var r = 0; r < 7; r++) {
        lda COLMAP, x
        sta COLRAM + r * 40, x
    }
        dex
        bpl !lp-
        rts
cc_pass2:
        ldx #39
!lp:
    .for (var r = 7; r < 14; r++) {
        lda COLMAP, x
        sta COLRAM + r * 40, x
    }
        dex
        bpl !lp-
cc_pass3:
        ldx #39
!lp:
    .for (var r = 14; r < 21; r++) {
        lda COLMAP, x
        sta COLRAM + r * 40, x
    }
        dex
        bpl !lp-
        rts

// Point the colour copy at COLMAP rows for (cam_cx, cam_cy)
patch_colsrc:
    .for (var r = 0; r < 21; r++) {
        lda cam_cy
        clc
        adc #r
        tay
        lda cm_row_lo, y
        clc
        adc cam_cx
        sta ccOp(r)
        lda cm_row_hi, y
        sta ccOp(r) + 1
    }
        rts
night_col: .byte $00, $01, $02, $03, $04, $05, $06, $07
           .byte $08, $09, $0A, $0E, $0C, $0D, $0E, $0F
cm_row_lo: .fill 128, <cmRow(i)
cm_row_hi: .fill 128, >cmRow(i)

// Build COLMAP: the colour of every world char (once, at boot; ~0.5 s)
build_colmap:
        lda #$00
        sta zp_row
!row:
        ldx zp_row
        stx rc_cy
        lda cm_row_lo, x
        sta zp_dst
        lda cm_row_hi, x
        sta zp_dst + 1
        lda #$00
        sta rc_cx
        lda #128
        sta rc_n
        jsr row_chr             // screen codes ...
        ldy #127
!cv:    lda (zp_dst), y         // ... turned into their colours
        tax
        lda char_col, x
        bit col_night
        bpl !day+
        tax
        lda night_col, x        // moonlit: waves go dark blue
!day:   sta (zp_dst), y
        dey
        bpl !cv-
        inc zp_row
        bpl !row-               // rows 0..127
        rts

// The diamond under world pixel (tg_x, tg_y): X = iso row, Y = stored index
// (with the margin diamond), tg_half = 0 if the pixel is in its left half,
// 1 if in its right half.
cell_at:
        lda tg_y + 1
        sta zp_tmp
        lda tg_y
        lsr zp_tmp
        ror
        lsr zp_tmp
        ror
        lsr zp_tmp
        ror                     // cy
        cmp #127
        bcc !cy_ok+
        lda #127
!cy_ok: tax
        lda tg_y
        and #$07
        sta tg_yb
        lda tg_x + 1
        sta zp_tmp
        lda tg_x
        lsr zp_tmp
        ror
        lsr zp_tmp
        ror
        lsr zp_tmp
        ror                     // cx (0..127)
        sta tg_cx
        txa
        and #$01
        sta rc_s
        asl                     // a = cx + 4 - 2s
        eor #$FF
        sec
        adc tg_cx
        clc
        adc #$04
        pha
        and #$03
        sta tg_q
        asl
        asl
        asl
        sta zp_tmp
        lda tg_x
        and #$07
        ora zp_tmp
        tay
        pla
        lsr
        lsr
        sta rc_i                // i
        lda tg_yb
        cmp line_thr, y
        bcs !lower+
        // upper diamond U = row cy, index i + (q >> 1): right half for q0/q1
        lda tg_q
        lsr
        clc
        adc rc_i
        tay
        lda tg_q
        cmp #$02
        lda #$01
        bcc !h+
        lda #$00
!h:     sta tg_half
        rts
!lower: // lower diamond L = row cy + 1, index i + s: left half for q0/q1
        inx
        lda rc_i
        clc
        adc rc_s
        tay
        lda tg_q
        cmp #$02
        lda #$00
        bcc !h+
        lda #$01
!h:     sta tg_half
        rts

// Terrain shown at world pixel (tg_x, tg_y) -> A = half type (TR_*)
terrain_at:
        jsr cell_at
        lda iso_row_lo, x
        sta rc_pu
        lda iso_row_hi, x
        sta rc_pu + 1
        lda (rc_pu), y
        ldx tg_half
        bne !right+
        lsr
        lsr
        lsr
        lsr
        rts
!right: and #$0F
        rts

// Ground level (0-3, 16 px each) of the ground diamond at (tg_x, tg_y)
height_at:
        jsr cell_at
        dey                     // stored index -> diamond index
        cpy #ISO_W
        bcs !zero+              // margin diamonds are sea
        lda iso_hrow_lo, x
        sta rc_pu
        lda iso_hrow_hi, x
        sta rc_pu + 1
        tya
        and #$03
        sta ht_sh
        tya
        lsr
        lsr
        tay
        lda (rc_pu), y
        ldy ht_sh
        beq !lo+
!sh:    lsr
        lsr
        dey
        bne !sh-
!lo:    and #$03
        rts
!zero:  lda #$00
        rts

// Terrain following: elev_cur (px) eases 2 px a frame toward 16 px per level of
// the ground under the heli, so it climbs over hills and roofs. The heli is
// drawn heli_alt px above it and its shadow lies on it.
update_elev:
        lda cam_dirty           // the screen shifts this frame: look up next frame
        bne !ease+
        lda heli_wx_lo
        clc
        adc #11
        sta tg_x
        lda heli_wx_hi
        adc #$00
        sta tg_x + 1
        lda heli_wy_lo
        clc
        adc #22
        sta tg_y
        lda heli_wy_hi
        adc #$00
        sta tg_y + 1
        jsr height_at
        sta elev_lvl
!ease:  lda elev_lvl
        asl
        asl
        asl
        asl
        sta zp_tmp              // target px
        ldx #$02                // up to 2 px a frame
!step:  lda elev_cur
        cmp zp_tmp
        beq !done+
        bcc !up+
        dec elev_cur
        jmp !nx+
!up:    inc elev_cur
!nx:    dex
        bne !step-
!done:  rts

// Pixel rows of a q-char that belong to U, by q*8 + x (0..7)
line_thr:
        .byte 8, 7, 7, 6, 6, 5, 5, 4
        .byte 4, 3, 3, 2, 2, 1, 1, 0
        .byte 0, 1, 1, 2, 2, 3, 3, 4
        .byte 4, 5, 5, 6, 6, 7, 7, 8

// ------------------------------------------------------------------------------
// Cyclone Instrument HUD (screen rows 21-23, shown at raster lines 223-246)
// ------------------------------------------------------------------------------
draw_hud_frame:
        ldx #39
!clr:
        lda #H_HLINE
        sta SCREEN + HUD_DIV * 40, x
        sta SCREEN + $0400 + HUD_DIV * 40, x
        lda #$03                // Cyan divider
        sta COLRAM + HUD_DIV * 40, x
        lda #$20
        sta SCREEN + HUD_ROW1 * 40, x
        sta SCREEN + HUD_ROW2 * 40, x
        lda #$01                // White hires text
        sta COLRAM + HUD_ROW1 * 40, x
        sta COLRAM + HUD_ROW2 * 40, x
        dex
        bpl !clr-

        // Static labels on HUD row 1 & 24 (mirrored to both screen pages)
        ldx #39
!lbl:
        lda hud_r23, x
        sta SCREEN + HUD_ROW1 * 40, x
        sta SCREEN + $0400 + HUD_ROW1 * 40, x
        lda hud_r24, x
        sta SCREEN + HUD_ROW2 * 40, x
        sta SCREEN + $0400 + HUD_ROW2 * 40, x
        dex
        bpl !lbl-

        // Colorize FUEL label cyan, CRATES yellow, LIVES green
        ldx #$03
!cf:    lda #$03
        sta COLRAM + HUD_ROW1 * 40, x
        dex
        bpl !cf-
        ldx #$05
!cc:    lda #$07
        sta COLRAM + HUD_ROW2 * 40, x
        dex
        bpl !cc-
        rts

update_hud:
        // Fuel bar at HUD row 1 cols 5..12 (8 chars, each 8 units = 64 max)
        lda fuel
        sta zp_tmp
        ldx #$00
!f_lp:
        lda zp_tmp
        cmp #$08
        bcc !f_part+
        lda #H_SOLID
        sta SCREEN + HUD_ROW1 * 40 + 5, x
        lda zp_tmp
        sec
        sbc #$08
        sta zp_tmp
        jmp !f_col+
!f_part:
        cmp #$00
        beq !f_empty+
        clc
        adc #(H_BAR1 - 1)
        sta SCREEN + HUD_ROW1 * 40 + 5, x
        lda #$00
        sta zp_tmp
        jmp !f_col+
!f_empty:
        lda #$20
        sta SCREEN + HUD_ROW1 * 40 + 5, x
!f_col:
        lda fuel
        cmp #16
        bcc !f_red+
        lda #$05                // Green
        jmp !f_scol+
!f_red:
        lda #$02                // Red low fuel
!f_scol:
        sta COLRAM + HUD_ROW1 * 40 + 5, x
        inx
        cpx #$08
        bcc !f_lp-

        // Altitude at HUD row 1 col 18..19 (00..12)
        lda heli_alt
        jsr byte_to_2dec
        stx SCREEN + HUD_ROW1 * 40 + 18
        sta SCREEN + HUD_ROW1 * 40 + 19

        // Cyclone warning at HUD row 1 cols 22..30
        ldx #$08
        lda torn_near
        beq !no_warn+
        lda anim_cnt
        and #$08
        beq !warn_txt+
!no_warn:
        lda #$20
!nw_lp: sta SCREEN + HUD_ROW1 * 40 + 22, x
        dex
        bpl !nw_lp-
        jmp !hud_r24+
!warn_txt:
        lda txt_cyclone, x
        sta SCREEN + HUD_ROW1 * 40 + 22, x
        lda #$02                // Red alert
        sta COLRAM + HUD_ROW1 * 40 + 22, x
        dex
        bpl !warn_txt-

!hud_r24:
        // Saved / to save at HUD row 2 cols 7-8 / 10-11
        lda crates_got
        jsr byte_to_2dec
        stx SCREEN + HUD_ROW2 * 40 + 7
        sta SCREEN + HUD_ROW2 * 40 + 8
        lda n_people
        jsr byte_to_2dec
        stx SCREEN + HUD_ROW2 * 40 + 10
        sta SCREEN + HUD_ROW2 * 40 + 11

        // Lives at col 16, mission at cols 20-21
        lda lives
        clc
        adc #'0'
        sta SCREEN + HUD_ROW2 * 40 + 16
        lda level
        jsr byte_to_2dec
        stx SCREEN + HUD_ROW2 * 40 + 20
        sta SCREEN + HUD_ROW2 * 40 + 21

        // On board: figure x n at cols 37-39
        lda #H_MAN
        sta SCREEN + HUD_ROW2 * 40 + 37
        lda #'X'
        sta SCREEN + HUD_ROW2 * 40 + 38
        lda aboard
        clc
        adc #'0'
        sta SCREEN + HUD_ROW2 * 40 + 39

        // Status message at HUD row 2 cols 23..33 (11 chars)
        lda msg_state
        asl
        asl
        asl
        asl
        tax
        ldy #$00
!ms_lp:
        lda msg_table, x
        sta SCREEN + HUD_ROW2 * 40 + 23, y
        lda #$07
        sta COLRAM + HUD_ROW2 * 40 + 23, y
        inx
        iny
        cpy #11
        bcc !ms_lp-

        // Score (4 hex-like/BCD digits) at HUD row 1 cols 36..39
        lda score_hi
        jsr byte_to_hex
        stx SCREEN + HUD_ROW1 * 40 + 36
        sta SCREEN + HUD_ROW1 * 40 + 37
        lda score_lo
        jsr byte_to_hex
        stx SCREEN + HUD_ROW1 * 40 + 38
        sta SCREEN + HUD_ROW1 * 40 + 39

        // Mirror dynamic HUD Rows 23-24 (80 bytes) to second screen page ($4400)
        ldx #79
!hud_mir:
        lda SCREEN + HUD_ROW1 * 40, x
        sta SCREEN + $0400 + HUD_ROW1 * 40, x
        dex
        bpl !hud_mir-
        rts

// ------------------------------------------------------------------------------
// Tactical Map (M Key)
// Islands at 2x2 blocks per character (the base in yellow), survivors blinking,
// and the heli and the cyclones as their own sprites moving live: the game keeps
// running on the map (fly, winch, land) until M is pressed again.
// World -> map: x / 4 (cols 4-35), y * 3 / 16 (rows 1-24).
// ------------------------------------------------------------------------------
show_tactical_map:
        sei
        lda #$00
        sta $D01A               // no raster split on the map
        lda #$01
        sta $D019
        cli
        lda #$1B
        sta $D011
        lda #$08                // hires text
        sta $D016
        lda #$02
        sta $D018
        sta d018_val
        lda #$04
        sta back_page
        lda #$06
        sta $D021
        lda #$00
        sta $D020
        sta $D017               // sprites at normal size on the map
        sta $D01D
        sta $D015
        jsr map_draw
!rel:   jsr wait_vbl            // let go of M first
        lda #$EF
        sta $DC00
        lda $DC01
        and #$10
        beq !rel-

!loop:  jsr wait_vbl
        jsr update_sfx
        inc anim_cnt
        jsr read_input
        jsr update_heli
        jsr update_camera
        lda #$00
        sta cam_dirty
        jsr update_elev
        jsr update_tornado
        jsr check_collisions
        jsr update_unload
        jsr update_fuel
        jsr map_marks
        lda expl_timer          // crashed or mission done: back to the game view
        bne !exit+
        lda msg_state
        cmp #$04
        beq !exit+
        lda #$EF
        sta $DC00
        lda $DC01
        and #$10
        bne !loop-
!rel2:  jsr wait_vbl            // M again: let go, then back
        lda #$EF
        sta $DC00
        lda $DC01
        and #$10
        beq !rel2-

!exit:  lda #$FF
        sta $DC00
        lda #$00
        sta map_prev
        lda #$64                // cyclones double size again
        sta $D017
        sta $D01D
        jsr set_palette
        jsr draw_hud_frame
        jsr draw_map
        jsr update_hud

        // Install 2-split raster IRQ for smooth playfield scroll + fixed HUD
        sei
        lda #<raster_irq
        sta $FFFE
        lda #>raster_irq
        sta $FFFF
        lda #$00
        sta irq_phase
        lda #HUD_SPLIT
        sta $D012
        lda #$01
        sta $D019
        sta $D01A
        cli
        rts

// Clear the screen, title row, and the islands as 32x24 quarter-block characters
map_draw:
        ldx #$00
!cl:    lda #$20
        sta SCREEN + $000, x
        sta SCREEN + $100, x
        sta SCREEN + $200, x
        sta SCREEN + $2E8, x
        lda #$01
        sta COLRAM + $000, x
        sta COLRAM + $100, x
        sta COLRAM + $200, x
        sta COLRAM + $2E8, x
        inx
        bne !cl-
        ldx #(MAP_MARKS - 1)
        lda #$00
!md:    sta map_drawn, x
        dex
        bpl !md-
        ldx #31
!hd:    lda txt_map_hdr, x
        sta SCREEN + 4, x
        lda #$07
        sta COLRAM + 4, x
        dex
        bpl !hd-

        lda #$00
        sta map_r
!row:   ldx map_r
        inx
        lda full_row_lo, x
        clc
        adc #$04
        sta zp_dst
        sta zp_col
        php                     // carry of the low byte, for both high bytes
        lda full_row_hi, x
        adc #$00
        sta zp_dst + 1
        plp
        lda full_col_hi, x
        adc #$00
        sta zp_col + 1
        lda map_r
        asl
        tax
        lda map_qy_j, x
        sta map_j0
        lda map_qy_j + 1, x
        sta map_j1
        lda #$00
        sta map_c
!col:   lda #$00
        sta map_mask
        sta map_base
        lda map_c               // the four quarter pixels of this character
        asl
        ldx map_j0
        jsr map_land
        lsr map_f
        rol map_mask
        lda map_c
        asl
        ora #$01
        ldx map_j0
        jsr map_land
        lsr map_f
        rol map_mask
        lda map_c
        asl
        ldx map_j1
        jsr map_land
        lsr map_f
        rol map_mask
        lda map_c
        asl
        ora #$01
        ldx map_j1
        jsr map_land
        lsr map_f
        rol map_mask            // bits 3..0 = TL, TR, BL, BR
        ldx map_mask
        lda map_qb, x
        ldy map_c
        sta (zp_dst), y
        lda map_base
        beq !g+
        lda #$07                // the home base
        .byte $2C
!g:     lda #$05                // land
        sta (zp_col), y
        inc map_c
        lda map_c
        cmp #32
        bne !col-
        inc map_r
        lda map_r
        cmp #24
        beq !mdone+
        jmp !row-
!mdone: rts

// Terrain flags of iso diamond (row X, quarter pixel column A), both halves;
// out: map_f bit 0 = land, map_base set if it is the base
map_land:
        sta zp_tmp
        txa
        and #$01
        sta map_par
        lda zp_tmp
        clc
        adc #$02
        sec
        sbc map_par
        lsr                     // stored diamond index (with margin)
        tay
        lda iso_row_lo, x
        sta rc_pu
        lda iso_row_hi, x
        sta rc_pu + 1
        lda (rc_pu), y
        pha
        lsr
        lsr
        lsr
        lsr
        tax
        lda terrain_flags, x
        sta map_f
        pla
        and #$0F
        tax
        lda terrain_flags, x
        ora map_f
        sta map_f
        and #TF_BASE
        ora map_base
        sta map_base
        rts

// Every frame on the map: sprites for the heli and cyclones, blinking survivors,
// the counters in the title row
map_marks:
        lda #$00
        sta map_msb
        // heli: sprite 0, its own frame and direction
        lda heli_wx_lo
        clc
        adc #11
        sta tg_x
        lda heli_wx_hi
        adc #$00
        sta tg_x + 1
        lda heli_wy_lo
        clc
        adc #22
        sta tg_y
        lda heli_wy_hi
        adc #$00
        sta tg_y + 1
        ldy #$00
        lda #$01
        jsr map_spr
        lda anim_cnt
        and #$02
        lsr
        clc
        adc heli_dir
        adc heli_dir
        clc
        adc #SPRPTR0 + SPR_HELI
        sta SPRPTR + 0
        // cyclones: sprites 2, 5, 6, spinning
        ldx #(NUM_TORNS - 1)
!tl:    stx torn_cur_idx
        lda torn_wx_lo, x
        clc
        adc #24
        sta tg_x
        lda torn_wx_hi, x
        adc #$00
        sta tg_x + 1
        lda torn_wy_lo, x
        clc
        adc #30
        sta tg_y
        lda torn_wy_hi, x
        adc #$00
        sta tg_y + 1
        ldy torn_spr_slot, x
        lda torn_spr_bit, x
        jsr map_spr
        ldx torn_cur_idx
        txa
        clc
        adc anim_cnt
        lsr
        lsr
        and #$03
        clc
        adc #SPRPTR0 + SPR_TORNADO
        ldy torn_spr_idx, x
        sta SPRPTR, y
        dex
        bpl !tl-
        lda map_msb
        sta $D010
        lda #$65                // sprites 0, 2, 5, 6
        sta $D015

        // survivors: blinking figures; a rescued one gives its island back
        ldx #(MAP_MARKS - 1)
!sl:    lda crate_active, x
        bne !act+
        lda map_drawn, x
        beq !sn+
        lda map_alo, x          // rescued: restore what was under the figure
        sta zp_ptr
        lda map_ahi, x
        sta zp_ptr + 1
        ldy #$00
        lda map_uc, x
        sta (zp_ptr), y
        lda zp_ptr + 1
        clc
        adc #(>COLRAM) - (>SCREEN)
        sta zp_ptr + 1
        lda map_ucol, x
        sta (zp_ptr), y
        lda #$00
        sta map_drawn, x
        jmp !sn+
!act:   lda map_drawn, x
        bne !draw+
        jsr map_cell            // first time: find the cell, keep what is there
        ldy #$00
        lda (zp_ptr), y
        sta map_uc, x
        lda zp_ptr
        sta map_alo, x
        lda zp_ptr + 1
        sta map_ahi, x
        clc
        adc #(>COLRAM) - (>SCREEN)
        sta zp_ptr + 1
        lda (zp_ptr), y
        sta map_ucol, x
        lda #$01
        sta map_drawn, x
!draw:  lda map_alo, x
        sta zp_ptr
        lda map_ahi, x
        sta zp_ptr + 1
        ldy #$00
        lda #H_MAN
        sta (zp_ptr), y
        lda zp_ptr + 1
        clc
        adc #(>COLRAM) - (>SCREEN)
        sta zp_ptr + 1
        lda anim_cnt
        and #$10
        beq !wh+
        lda #$0A                // blink light red / white
        .byte $2C
!wh:    lda #$01
        sta (zp_ptr), y
!sn:    dex
        bpl !sl-

        // title row counters: level, saved / to save
        lda level
        jsr byte_to_2dec
        stx SCREEN + 4 + 6
        sta SCREEN + 4 + 7
        lda crates_got
        jsr byte_to_2dec
        stx SCREEN + 4 + 16
        sta SCREEN + 4 + 17
        lda n_people
        jsr byte_to_2dec
        stx SCREEN + 4 + 19
        sta SCREEN + 4 + 20
        rts

// Survivor X's map cell -> zp_ptr (screen address); keeps X
map_cell:
        lda crate_wy_lo, x      // row = 1 + ((y + 16) * 3) >> 7
        clc
        adc #16
        sta map_t0
        lda crate_wy_hi, x
        adc #$00
        sta map_t1
        lda map_t0
        asl
        sta map_t2
        lda map_t1
        rol
        sta map_t3
        lda map_t2
        clc
        adc map_t0
        sta map_t2
        lda map_t3
        adc map_t1
        sta map_t3
        lda map_t2
        asl
        lda map_t3
        rol
        tay
        iny
        lda full_row_lo, y
        sta zp_ptr
        lda full_row_hi, y
        sta zp_ptr + 1
        lda crate_wx_lo, x      // col = 4 + (x + 11) >> 5
        clc
        adc #11
        sta map_t0
        lda crate_wx_hi, x
        adc #$00
        asl
        asl
        asl
        sta map_t1
        lda map_t0
        lsr
        lsr
        lsr
        lsr
        lsr
        ora map_t1
        clc
        adc #$04
        clc
        adc zp_ptr
        sta zp_ptr
        bcc !nc+
        inc zp_ptr + 1
!nc:    rts

// Place sprite (VIC offset Y = 2 * n, MSB bit A) at the map position of world
// pixel (tg_x, tg_y): x = 44 + X / 4, y = 48 + 3 * Y / 16 (sprite centred)
map_spr:
        sta map_bit
        lda tg_x + 1
        sta map_t1
        lda tg_x
        lsr map_t1
        ror
        lsr map_t1
        ror
        clc
        adc #44
        sta $D000, y
        bcc !lo+
        lda map_msb
        ora map_bit
        sta map_msb
!lo:    lda tg_y                // 3 * Y
        asl
        sta map_t0
        lda tg_y + 1
        rol
        sta map_t1
        lda map_t0
        clc
        adc tg_y
        sta map_t0
        lda map_t1
        adc tg_y + 1
        sta map_t1
        lda map_t0              // / 16
        lsr map_t1
        ror
        lsr map_t1
        ror
        lsr map_t1
        ror
        lsr map_t1
        ror
        clc
        adc #48
        sta $D001, y
        rts

// ------------------------------------------------------------------------------
// Drop-off: landed on the H with people on board, they climb out one at a time
// and run into the hangar; each counts as saved when they get there.
// ------------------------------------------------------------------------------
update_unload:
        lda run_state
        bne !run+
        lda on_pad
        beq !out+
        lda aboard
        beq !out+
        lda run_delay
        beq !go+
        dec run_delay
!out:   rts
!go:    dec aboard
        lda #RUN_X0
        sta run_x
        lda #RUN_Y0
        sta run_y
        lda #$01
        sta run_state
        rts
!run:   lda run_x               // 1 px a frame toward the hangar door
        cmp #RUN_TX
        beq !rx+
        inc run_x
!rx:    lda run_y
        cmp #RUN_TY
        beq !ry+
        dec run_y
!ry:    lda run_x
        cmp #RUN_TX
        bne !out-
        lda run_y
        cmp #RUN_TY
        bne !out-
        lda #$00                // inside: saved
        sta run_state
        inc crates_got
        lda #20
        sta run_delay
        jsr add_score_500
        jmp play_sfx_pickup

// ------------------------------------------------------------------------------
// Helpers, SFX & Banners
// ------------------------------------------------------------------------------
wait_vbl:
        lda #$FB
!w1:    cmp $D012
        bne !w1-
!w2:    cmp $D012
        beq !w2-
        rts

add_score_500:
        sed
        lda score_lo
        clc
        adc #$50
        sta score_lo
        lda score_hi
        adc #$00
        sta score_hi
        cld
        rts

byte_to_2dec:
        ldx #'0'
!d10:   cmp #10
        bcc !d1+
        sbc #10
        inx
        jmp !d10-
!d1:    clc
        adc #'0'
        rts

byte_to_hex:
        pha
        lsr
        lsr
        lsr
        lsr
        tay
        lda hex_chars, y
        tax
        pla
        and #$0F
        tay
        lda hex_chars, y
        rts

play_sfx_pickup:
        lda #$20
        sta $D40E
        lda #$38
        sta $D40F
        lda #$09
        sta $D413
        lda #$80
        sta $D414
        lda #$11
        sta $D412
        lda #12
        sta sfx_timer
        rts

play_sfx_boom:
        lda #$00
        sta $D40E
        lda #$0C
        sta $D40F
        lda #$0A
        sta $D413
        lda #$C0
        sta $D414
        lda #$81
        sta $D412
        lda #24
        sta sfx_timer
        rts

update_sfx:
        // Priority 1: One-shot pickup/explosion SFX timer
        lda sfx_timer
        beq !sfx_cont+
        dec sfx_timer
        bne !sx_ret+
        lda #$00
        sta $D412
!sx_ret:
        rts

!sfx_cont:
        // If exploding, keep quiet after boom timer
        lda expl_timer
        bne !sx_ret-

        // Priority 2: Tornado gale wind sound when affecting airborne helicopter
        lda heli_alt
        bne !sfx_air+
        jmp !sfx_off+
!sfx_air:
        lda torn_near
        beq !sfx_winch+
        lda anim_cnt
        and #$1F
        cmp #$10
        bcc !wind_up+
        eor #$1F
!wind_up:
        clc
        adc #$08                // howling noise pitch $08..$17
        sta $D40F
        lda #$00
        sta $D40E
        lda #$25
        sta $D413
        lda #$A0
        sta $D414
        lda #$81                // Noise waveform
        sta $D412
        rts

!sfx_winch:
        // Priority 3: Winch hook / lifting survivor sound
        lda winch_state
        beq !sfx_heli+
        cmp #$02
        beq !sfx_lift+
        // Lowering hook: gentle descending pulse
        lda #$24
        sec
        sbc winch_y
        sta $D40F
        lda #$00
        sta $D40E
        lda #$04
        sta $D413
        lda #$60
        sta $D414
        lda anim_cnt
        and #$02
        beq !w_gate_off+
        lda #$41                // Pulse
        sta $D412
        rts
!w_gate_off:
        lda #$40
        sta $D412
        rts

!sfx_lift:
        // Lifting person slowly: rising hydraulic pitch ($10 -> $30)
        lda #16
        sec
        sbc winch_y
        asl
        clc
        adc #$10
        sta $D40F
        lda #$00
        sta $D40E
        lda #$06
        sta $D413
        lda #$A8
        sta $D414
        lda #$11                // Triangle waveform
        sta $D412
        rts

!sfx_heli:
        // Priority 4: Helicopter rotor thump while airborne (every 4 frames)
        lda #$80
        sta $D40E
        lda #$04
        sta $D40F
        lda #$03
        sta $D413
        lda #$00
        sta $D414
        lda anim_cnt
        and #$03
        cmp #$02
        bcc !rotor_on+
        lda #$80                // Gate off
        sta $D412
        rts
!rotor_on:
        lda #$81                // Noise rotor thump
        sta $D412
        rts

!sfx_off:
        lda #$00                // no music during play: release voice 3
        sta $D412
        rts

show_banner_win:
        ldx #19
!bw:    lda txt_win, x
        sta SCREEN + 10 * 40 + 10, x
        sta SCREEN + $0400 + 10 * 40 + 10, x
        lda #$05
        sta COLRAM + 10 * 40 + 10, x
        dex
        bpl !bw-
        rts

show_banner_over:
        ldx #19
!bo:    lda txt_over, x
        sta SCREEN + 10 * 40 + 10, x
        sta SCREEN + $0400 + 10 * 40 + 10, x
        lda #$02
        sta COLRAM + 10 * 40 + 10, x
        dex
        bpl !bo-
        rts

// ------------------------------------------------------------------------------
// Data Tables
// ------------------------------------------------------------------------------
hex_chars: .text "0123456789ABCDEF"

// joy_bits (U=1,D=2,L=4,R=8) -> dir 0..7 (N,NE,E,SE,S,SW,W,NW)
dir_lut:
        .byte $FF, 0, 4, $FF, 6, 7, 5, $FF, 2, 1, 3, $FF, $FF, $FF, $FF, $FF

// 3 Cyclones across the 64x64 archipelago (one starts near SW/Central so visible early)
torn_init_x_lo: .byte $E0, $20, $60
torn_init_x_hi: .byte $00, $02, $03
torn_init_y_lo: .byte $20, $40, $80
torn_init_y_hi: .byte $03, $01, $02
torn_init_vx:   .byte $FF, $01, $FF
torn_init_vy:   .byte $FF, $01, $FF
torn_spr_slot:  .byte 4, 10, 12         // $D004/$D005, $D00A/$D00B, $D00C/$D00D
torn_spr_idx:   .byte 2, 5, 6           // SPRPTR + 2, 5, 6
torn_spr_bit:   .byte $04, $20, $40     // $D010 / $D015 bits

// 5 Stranded Survivors across the 64x64 archipelago (all on island land)
//   0: tile (5, 50) = ($0050, $0320) [Home Base N peninsula]
//   1: tile (12, 10) = ($00C0, $00A0) [NW island]
//   2: tile (30, 19) = ($01E0, $0130) [Central island]
//   3: tile (52, 11) = ($0340, $00B0) [NE island]
//   4: tile (52, 56) = ($0340, $0380) [SE island]
// Sprite register shadow ($D000-$D015): update_sprites writes here and the
// raster IRQ copies it to the VIC together with the scroll registers.
vic_sh:      .fill $16, 0
shadow_dx:   .fill 16, min(4, floor((i + 1) / 3))   // by heli_alt 0..12 (+gust headroom)
kla_idle_save: .byte 0

crate_active: .fill MAX_PEOPLE, 0      // set per mission by place_people
crate_wx_lo:  .fill MAX_PEOPLE, 0
crate_wx_hi:  .fill MAX_PEOPLE, 0
crate_wy_lo:  .fill MAX_PEOPLE, 0
crate_wy_hi:  .fill MAX_PEOPLE, 0
map_drawn:    .fill MAP_MARKS, 0        // tactical map: survivor figure drawn
map_uc:       .fill MAP_MARKS, 0        //   character and colour under it
map_ucol:     .fill MAP_MARKS, 0
map_alo:      .fill MAP_MARKS, 0        //   its screen address
map_ahi:      .fill MAP_MARKS, 0
// quarter-block characters by mask (bit 3 TL, 2 TR, 1 BL, 0 BR)
map_qb:       .byte H_QB0, H_QB8, H_QB4, H_QB12, H_QB2, H_QB10, H_QB6, H_QB14
              .byte H_QB1, H_QB9, H_QB5, H_QB13, H_QB3, H_QB11, H_QB7, H_QB15
// quarter pixel row -> iso diamond row (y = qy * 64 / 3 + 10)
map_qy_j:     .fill 48, min(127, round((i * 64 / 3 + 10) / 8))

hud_r23:     .text "FUEL          ALT 00            SCR 0000"
hud_r24:     .text "RESCUE 00/00 LIV3 LV00                 "
txt_cyclone: .text "TORNADO! "
txt_map_hdr: .text "LEVEL 00  SAVED 00/00     M=EXIT"
txt_win:     .text "  MISSION COMPLETE! "
txt_over:    .text "     GAME OVER!     "

msg_table:
        .text "FLYING          "
        .text "REFUELING!      "
        .text "ABOARD!         "
        .text "TO BASE!        "
        .text "YOU WIN!        "
        .text "GAME OVER!      "
        .text "WINCHING!       "
        .text "GALE TURB!      "
        .text "DROP OFF!       "

scr_row_lo:  .fill VIEW_TH, <(SCREEN + i * 80)
scr_row_hi:  .fill VIEW_TH, >(SCREEN + i * 80)
col_row_hi:  .fill VIEW_TH, >(COLRAM + i * 80)
full_row_lo: .fill 25, <(SCREEN + i * 40)
full_row_hi: .fill 25, >(SCREEN + i * 40)
full_col_hi: .fill 25, >(COLRAM + i * 40)

// ------------------------------------------------------------------------------
// Levels (free gap after the music)
// ------------------------------------------------------------------------------
* = $1508 "Levels"
#import "levels.asm"

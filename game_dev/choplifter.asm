// ==============================================================================
// CHOPLIFTER: RESCUE PROTOCOL
// Advanced Modern Commodore 64 / C64U Tactical Rescue Game
// Target Assembler: KickAssembler v5.x
// Architecture: MOS 6510 CPU / VIC-II Video / SID 6581/8580 Audio
// ==============================================================================

BasicUpstart2(entry_point)

* = $0810 "Choplifter Engine"

// ==============================================================================
// HARDWARE CONSTANTS
// ==============================================================================
.const SCREEN_RAM       = $0400
.const COLOR_RAM        = $D800
.const SPRITE_PTR_BASE  = SCREEN_RAM + $03F8  // $07F8 - $07FF

// VIC-II Registers
.const VIC_SP0_X        = $D000
.const VIC_SP0_Y        = $D001
.const VIC_SP1_X        = $D002
.const VIC_SP1_Y        = $D003
.const VIC_SP2_X        = $D004
.const VIC_SP2_Y        = $D005
.const VIC_SP3_X        = $D006
.const VIC_SP3_Y        = $D007
.const VIC_SP4_X        = $D008
.const VIC_SP4_Y        = $D009
.const VIC_SP5_X        = $D00A
.const VIC_SP5_Y        = $D00B
.const VIC_SP6_X        = $D00C
.const VIC_SP6_Y        = $D00D
.const VIC_SP7_X        = $D00E
.const VIC_SP7_Y        = $D00F
.const VIC_MSB_X        = $D010
.const VIC_CTRL1        = $D011
.const VIC_RASTER       = $D012
.const VIC_SP_ENABLE    = $D015
.const VIC_CTRL2        = $D016
.const VIC_SP_EXP_Y     = $D017
.const VIC_MEMORY_SETUP = $D018
.const VIC_IRQ_STATUS   = $D019
.const VIC_IRQ_CONTROL  = $D01A
.const VIC_SP_PRIORITY  = $D01B
.const VIC_SP_MC_ENABLE = $D01C
.const VIC_SP_EXP_X     = $D01D
.const VIC_BORDER_COLOR = $D020
.const VIC_BG_COLOR0    = $D021
.const VIC_SP_MC_COLOR0 = $D025
.const VIC_SP_MC_COLOR1 = $D026
.const VIC_SP0_COLOR    = $D027

// SID Registers ($D400-$D41C)
.const SID_V1_FREQ_LO   = $D400
.const SID_V1_FREQ_HI   = $D401
.const SID_V1_PW_LO     = $D402
.const SID_V1_PW_HI     = $D403
.const SID_V1_CTRL      = $D404
.const SID_V1_AD        = $D405
.const SID_V1_SR        = $D406

.const SID_V2_FREQ_LO   = $D407
.const SID_V2_FREQ_HI   = $D408
.const SID_V2_PW_LO     = $D409
.const SID_V2_PW_HI     = $D40A
.const SID_V2_CTRL      = $D40B
.const SID_V2_AD        = $D40C
.const SID_V2_SR        = $D40D

.const SID_V3_FREQ_LO   = $D40E
.const SID_V3_FREQ_HI   = $D40F
.const SID_V3_PW_LO     = $D410
.const SID_V3_PW_HI     = $D411
.const SID_V3_CTRL      = $D412
.const SID_V3_AD        = $D413
.const SID_V3_SR        = $D414

.const SID_FILTER_CUT_LO= $D415
.const SID_FILTER_CUT_HI= $D416
.const SID_FILTER_RES   = $D417
.const SID_VOLUME       = $D418

// CIA & Kernal
.const CIA1_DATA_A      = $DC00      // Joystick Port 2 / Keyboard Rows
.const CIA1_DATA_B      = $DC01      // Joystick Port 1 / Keyboard Cols
.const CIA1_INT_CTRL    = $DC0D
.const KERNAL_GETIN     = $FFE4
.const KERNAL_SCNKEY    = $FF9F

// Colors
.const COLOR_BLACK      = 0
.const COLOR_WHITE      = 1
.const COLOR_RED        = 2
.const COLOR_CYAN       = 3
.const COLOR_PURPLE     = 4
.const COLOR_GREEN      = 5
.const COLOR_BLUE       = 6
.const COLOR_YELLOW     = 7
.const COLOR_ORANGE     = 8
.const COLOR_BROWN      = 9
.const COLOR_LIGHT_RED  = 10
.const COLOR_DARK_GREY  = 11
.const COLOR_GREY       = 12
.const COLOR_LIGHT_GREEN= 13
.const COLOR_LIGHT_BLUE = 14
.const COLOR_LIGHT_GREY = 15

// Game Constants
.const GROUND_Y         = 206        // Pixel Y coordinate of desert ground
.const BASE_X_MAX       = 84         // Airfield landing pad X boundary
.const CEILING_Y        = 60         // Maximum altitude (just under HUD)
.const BARRACKS1_X      = 176        // Compound 1 X position
.const BARRACKS2_X      = 280        // Compound 2 X position

// Sprite Pointer Offsets ($3000 / 64 = $C0)
.const SP_BASE_PTR      = $C0
.const SP_CHOPPER_R     = SP_BASE_PTR + 0
.const SP_CHOPPER_L     = SP_BASE_PTR + 1
.const SP_CHOPPER_C     = SP_BASE_PTR + 2
.const SP_ROTOR_BASE    = SP_BASE_PTR + 3    // 4 frames: +0..+3
.const SP_HOSTAGE_R     = SP_BASE_PTR + 7    // 4 frames: +0..+3
.const SP_HOSTAGE_L     = SP_BASE_PTR + 11   // 4 frames: +0..+3
.const SP_HOSTAGE_WAVE  = SP_BASE_PTR + 15
.const SP_HOSTAGE_BOARD = SP_BASE_PTR + 16
.const SP_TANK_BODY     = SP_BASE_PTR + 17   // 2 frames
.const SP_TANK_TURRET   = SP_BASE_PTR + 19   // 3 frames (L, C, R)
.const SP_JET_L         = SP_BASE_PTR + 22
.const SP_JET_R         = SP_BASE_PTR + 23
.const SP_AFTERBURNER   = SP_BASE_PTR + 24   // 2 frames
.const SP_BULLET_P      = SP_BASE_PTR + 26
.const SP_SHELL_E       = SP_BASE_PTR + 27
.const SP_EXPLODE_BASE  = SP_BASE_PTR + 28   // 4 frames

// ==============================================================================
// ZERO PAGE GAME VARIABLES ($02 - $50)
// ==============================================================================
* = $02 "Game Zero Page" virtual
zp_game_state:      .byte 0      // 0=Title, 1=Playing, 2=Over, 3=Victory
zp_frame_counter:   .byte 0      // Increments every VBLANK
zp_rotor_frame:     .byte 0      // 0..3
zp_hostage_anim:    .byte 0      // 0..3 walking frame

// Player Chopper Coordinates & Physics
zp_chop_x_lo:       .byte 0
zp_chop_x_hi:       .byte 0      // 0 or 1 (9th bit)
zp_chop_y:          .byte 0
zp_chop_sub_x:      .byte 0      // Fractional sub-pixel X
zp_chop_sub_y:      .byte 0      // Fractional sub-pixel Y
zp_chop_vx:         .byte 0      // Signed 8-bit velocity X
zp_chop_vy:         .byte 0      // Signed 8-bit velocity Y
zp_chop_facing:     .byte 0      // 0=Right, 1=Center/Hover, 2=Left
zp_chop_landed:     .byte 0      // 0=Flying, 1=Landed, 2=Crashed
zp_chop_shield:     .byte 0      // 0..8
zp_chop_cargo:      .byte 0      // 0..16
zp_rescued_count:   .byte 0      // Total rescued at base

// Hostage Entity 1
zp_h1_active:       .byte 0
zp_h1_x_lo:         .byte 0
zp_h1_x_hi:         .byte 0
zp_h1_y:            .byte 0
zp_h1_state:        .byte 0      // 0=Trapped, 1=Waving, 2=Running, 3=Safe
zp_h1_dir:          .byte 0      // 0=Right, 1=Left

// Hostage Entity 2
zp_h2_active:       .byte 0
zp_h2_x_lo:         .byte 0
zp_h2_x_hi:         .byte 0
zp_h2_y:            .byte 0
zp_h2_state:        .byte 0
zp_h2_dir:          .byte 0

// Enemy Tank
zp_tank_active:     .byte 0
zp_tank_x_lo:       .byte 0
zp_tank_x_hi:       .byte 0
zp_tank_y:          .byte 0
zp_tank_dir:        .byte 0      // 0=Left, 1=Right
zp_tank_reload:     .byte 0      // Firing timer

// Enemy Jet
zp_jet_active:      .byte 0
zp_jet_x_lo:        .byte 0
zp_jet_x_hi:        .byte 0
zp_jet_y:           .byte 0
zp_jet_dir:         .byte 0      // 0=Left, 1=Right
zp_jet_timer:       .byte 0

// Projectiles
zp_bullet_active:   .byte 0
zp_bullet_x_lo:     .byte 0
zp_bullet_x_hi:     .byte 0
zp_bullet_y:        .byte 0
zp_bullet_vx:       .byte 0
zp_bullet_vy:       .byte 0

zp_shell_active:    .byte 0
zp_shell_x_lo:      .byte 0
zp_shell_x_hi:      .byte 0
zp_shell_y:         .byte 0
zp_shell_vx:        .byte 0
zp_shell_vy:        .byte 0

// Barracks Hitpoints
zp_barracks1_hp:    .byte 0
zp_barracks2_hp:    .byte 0

// Music & SFX pointers
zp_music_step:      .byte 0
zp_music_speed:     .byte 0
zp_sfx_type:        .byte 0      // 0=None, 1=Fire, 2=Explode, 3=Chime
zp_sfx_timer:       .byte 0

// Pointers for general drawing
zp_ptr_lo:          .byte 0
zp_ptr_hi:          .byte 0
zp_tmp:             .byte 0

// ==============================================================================
// ENTRY POINT & INITIALIZATION
// ==============================================================================
* = $0810 "Main Game Code"

entry_point:
    sei                         // Disable interrupts during setup
    cld                         // Clear decimal mode

    // Standard memory configuration ($37: BASIC + Kernal + I/O)
    lda #$37
    sta $01

    // Reset SID sound chip
    jsr sid_reset

    // Set border and background
    lda #COLOR_BLACK
    sta VIC_BORDER_COLOR
    sta VIC_BG_COLOR0

    // Setup Raster IRQ for rock-solid 50Hz timing
    lda #$7F
    sta CIA1_INT_CTRL           // Disable CIA1 timer interrupts
    lda CIA1_INT_CTRL           // Acknowledge any pending CIA interrupts

    lda #$01
    sta VIC_IRQ_CONTROL         // Enable VIC-II Raster IRQ
    lda #$1B                    // Clear high bit of raster line
    sta VIC_CTRL1
    lda #$80                    // Trigger IRQ at raster line 128
    sta VIC_RASTER

    lda #<irq_handler
    sta $0314
    lda #>irq_handler
    sta $0315

    cli                         // Re-enable interrupts

    // Switch to Title State
    jsr show_title_screen

main_loop:
    // Check current state
    lda zp_game_state
    bne game_running_check

    // In Title Screen: Check for input to start
    jsr check_title_input
    jmp main_loop

game_running_check:
    cmp #1
    bne check_ended
    
    // In Game: Execute logic every frame (synced with frame counter)
    lda zp_frame_counter
frame_wait:
    cmp zp_frame_counter
    beq frame_wait

    jsr update_player_input
    jsr update_chopper_physics
    jsr update_weapons
    jsr update_barracks
    jsr update_hostages
    jsr update_tank
    jsr update_jet
    jsr check_collisions
    jsr update_hud
    jsr update_hardware_sprites
    jmp main_loop

check_ended:
    // Game over / Victory display loop
    jsr check_title_input
    jmp main_loop

// ==============================================================================
// RASTER IRQ HANDLER (50/60 Hz Frame Driver)
// ==============================================================================
irq_handler:
    pha
    txa
    pha
    tya
    pha

    // Acknowledge VIC-II raster interrupt
    asl VIC_IRQ_STATUS

    // Increment global frame counter
    inc zp_frame_counter

    // Update Music and SFX
    jsr sid_play_frame

    // Update animated sprite frames
    lda zp_frame_counter
    and #$01
    bne irq_skip_rotor
    // Advance rotor frame (0..3)
    inc zp_rotor_frame
    lda zp_rotor_frame
    and #$03
    sta zp_rotor_frame

irq_skip_rotor:
    // Advance walking animation at lower rate
    lda zp_frame_counter
    and #$07
    bne irq_done
    inc zp_hostage_anim
    lda zp_hostage_anim
    and #$03
    sta zp_hostage_anim

irq_done:
    pla
    tay
    pla
    tax
    pla
    rti

// ==============================================================================
// TITLE & BRIEFING SCREEN
// ==============================================================================
show_title_screen:
    lda #0
    sta zp_game_state
    jsr clear_screen

    // Turn off all sprites
    lda #$00
    sta VIC_SP_ENABLE

    // Draw Title Logo and Briefing Box
    ldx #0
title_print_loop:
    lda title_text_0, x
    beq title_next_1
    sta SCREEN_RAM + 40 * 2 + 3, x
    lda #COLOR_YELLOW
    sta COLOR_RAM + 40 * 2 + 3, x
    inx
    bne title_print_loop

title_next_1:
    ldx #0
title_sub_loop:
    lda title_sub_text, x
    beq title_next_2
    sta SCREEN_RAM + 40 * 4 + 7, x
    lda #COLOR_LIGHT_BLUE
    sta COLOR_RAM + 40 * 4 + 7, x
    inx
    bne title_sub_loop

title_next_2:
    // Print Mission Briefing Box
    ldx #0
brief_loop:
    lda brief_line_1, x
    beq brief_done_1
    sta SCREEN_RAM + 40 * 7 + 4, x
    lda #COLOR_WHITE
    sta COLOR_RAM + 40 * 7 + 4, x
    inx
    bne brief_loop

brief_done_1:
    ldx #0
brief_loop2:
    lda brief_line_2, x
    beq brief_done_2
    sta SCREEN_RAM + 40 * 9 + 4, x
    lda #COLOR_LIGHT_GREEN
    sta COLOR_RAM + 40 * 9 + 4, x
    inx
    bne brief_loop2

brief_done_2:
    ldx #0
brief_loop3:
    lda brief_line_3, x
    beq brief_done_3
    sta SCREEN_RAM + 40 * 11 + 4, x
    lda #COLOR_CYAN
    sta COLOR_RAM + 40 * 11 + 4, x
    inx
    bne brief_loop3

brief_done_3:
    ldx #0
ctrl_loop1:
    lda ctrl_text_1, x
    beq ctrl_done_1
    sta SCREEN_RAM + 40 * 14 + 2, x
    lda #COLOR_GREY
    sta COLOR_RAM + 40 * 14 + 2, x
    inx
    bne ctrl_loop1

ctrl_done_1:
    ldx #0
ctrl_loop2:
    lda ctrl_text_2, x
    beq ctrl_done_2
    sta SCREEN_RAM + 40 * 16 + 2, x
    lda #COLOR_LIGHT_GREY
    sta COLOR_RAM + 40 * 16 + 2, x
    inx
    bne ctrl_loop2

ctrl_done_2:
    ldx #0
ctrl_loop3:
    lda ctrl_text_3, x
    beq title_init_music
    sta SCREEN_RAM + 40 * 18 + 2, x
    lda #COLOR_LIGHT_GREY
    sta COLOR_RAM + 40 * 18 + 2, x
    inx
    bne ctrl_loop3

title_init_music:
    // Start Title SID Music
    lda #0
    sta zp_music_step
    sta zp_music_speed
    rts

// Check keyboard or joystick fire button to start game
check_title_input:
    // Flash the "PRESS ANY KEY OR FIRE" prompt with cycling color
    lda zp_frame_counter
    lsr
    lsr
    lsr
    and #$07
    tax
    lda flash_colors, x
    ldy #0
flash_loop:
    sta COLOR_RAM + 40 * 22 + 4, y
    iny
    cpy #32
    bne flash_loop

    ldx #0
prompt_print:
    lda prompt_text, x
    beq check_key_press
    sta SCREEN_RAM + 40 * 22 + 4, x
    inx
    bne prompt_print

check_key_press:
    // Read Joystick 2 Fire Button (Bit 4 of $DC00 is 0 when pressed)
    lda CIA1_DATA_A
    and #$10
    beq start_new_game

    // Check keyboard key via Kernal GETIN
    jsr KERNAL_GETIN
    cmp #0
    bne start_new_game
    rts

start_new_game:
    jsr init_game_variables
    jsr draw_gameplay_screen
    lda #1
    sta zp_game_state
    rts

flash_colors:
    .byte COLOR_RED, COLOR_ORANGE, COLOR_YELLOW, COLOR_WHITE, COLOR_CYAN, COLOR_LIGHT_BLUE, COLOR_GREY, COLOR_LIGHT_RED

title_text_0:
    .text "=== C H O P L I F T E R ==="
    .byte 0

title_sub_text:
    .text "ULTIMATE RESCUE PROTOCOL"
    .byte 0

brief_line_1:
    .text "MISSION: INFILTRATE HOSTILE DESERT."
    .byte 0

brief_line_2:
    .text "OBJECTIVE: BREACH COMPOUNDS & RESCUE POWS."
    .byte 0

brief_line_3:
    .text "AVOID TANK FLAK AND SUPERSONIC JETS!"
    .byte 0

ctrl_text_1:
    .text "JOYSTICK 2: FLIGHT (UP/DN/L/R) + FIRE"
    .byte 0

ctrl_text_2:
    .text "KEYS: W/S/A/D OR CURSORS + SPACE FIRE"
    .byte 0

ctrl_text_3:
    .text "HOVER (FACING CENTER) & DECELERATE TO LAND"
    .byte 0

prompt_text:
    .text ">>> PRESS ANY KEY OR FIRE <<<"
    .byte 0

// ==============================================================================
// GAMEPLAY ENVIRONMENT INITIALIZATION
// ==============================================================================
init_game_variables:
    // Initial Chopper position: Home base landing pad
    lda #40
    sta zp_chop_x_lo
    lda #0
    sta zp_chop_x_hi
    lda #GROUND_Y - 4
    sta zp_chop_y
    lda #0
    sta zp_chop_sub_x
    sta zp_chop_sub_y
    sta zp_chop_vx
    sta zp_chop_vy
    sta zp_chop_facing          // Facing Right
    lda #1
    sta zp_chop_landed          // Landed at base pad
    lda #8
    sta zp_chop_shield          // Full shield (8 bars)
    lda #0
    sta zp_chop_cargo           // Empty cargo bay
    sta zp_rescued_count        // 0 rescued

    // Barracks HP
    lda #4
    sta zp_barracks1_hp
    sta zp_barracks2_hp

    // Hostages initially trapped
    lda #1
    sta zp_h1_active
    lda #BARRACKS1_X + 10
    sta zp_h1_x_lo
    lda #0
    sta zp_h1_x_hi
    lda #GROUND_Y
    sta zp_h1_y
    lda #0                      // Trapped
    sta zp_h1_state
    sta zp_h1_dir

    lda #1
    sta zp_h2_active
    lda #BARRACKS2_X + 10
    sta zp_h2_x_lo
    lda #1                      // Over 255 X
    sta zp_h2_x_hi
    lda #GROUND_Y
    sta zp_h2_y
    lda #0                      // Trapped
    sta zp_h2_state
    sta zp_h2_dir

    // Tank initially active in patrol zone
    lda #1
    sta zp_tank_active
    lda #200
    sta zp_tank_x_lo
    lda #0
    sta zp_tank_x_hi
    lda #GROUND_Y - 2
    sta zp_tank_y
    lda #0                      // Moving left
    sta zp_tank_dir
    lda #60
    sta zp_tank_reload

    // Jet initially inactive
    lda #0
    sta zp_jet_active
    lda #120
    sta zp_jet_timer

    // Projectiles
    lda #0
    sta zp_bullet_active
    sta zp_shell_active

    rts

// ==============================================================================
// DRAW GAMEPLAY SCREEN (HUD, Terrain, Base, Barracks)
// ==============================================================================
draw_gameplay_screen:
    jsr clear_screen

    // Set background to dusk blue, border to black
    lda #COLOR_BLACK
    sta VIC_BORDER_COLOR
    lda #COLOR_BLUE
    sta VIC_BG_COLOR0

    // Draw HUD Rows (Row 0..2)
    ldx #0
hud_print_loop:
    lda hud_line_1, x
    beq hud_next_2
    sta SCREEN_RAM, x
    lda #COLOR_WHITE
    sta COLOR_RAM, x
    inx
    bne hud_print_loop

hud_next_2:
    ldx #0
hud_print_loop2:
    lda hud_line_2, x
    beq hud_done
    sta SCREEN_RAM + 40, x
    lda #COLOR_CYAN
    sta COLOR_RAM + 40, x
    inx
    bne hud_print_loop2

hud_done:
    // Draw separator bar at row 2
    ldx #0
sep_loop:
    lda #$40                    // Horizontal line character
    sta SCREEN_RAM + 80, x
    lda #COLOR_LIGHT_BLUE
    sta COLOR_RAM + 80, x
    inx
    cpx #40
    bne sep_loop

    // Draw Sky Stars / Distant Clouds (Rows 3..17)
    // Mountain Horizon at Row 18
    ldx #0
mountain_loop:
    lda #$4E                    // Angled mountain slopes
    sta SCREEN_RAM + 40 * 18, x
    lda #COLOR_DARK_GREY
    sta COLOR_RAM + 40 * 18, x
    inx
    cpx #40
    bne mountain_loop

    // Ground Level (Rows 19..24) - Desert Sand
    ldy #19
ground_row_loop:
    lda screen_row_offsets_lo, y
    sta zp_ptr_lo
    lda screen_row_offsets_hi, y
    sta zp_ptr_hi

    ldx #0
ground_col_loop:
    lda #$A0                    // Solid filled block
    sta (zp_ptr_lo), x

    // Color RAM equivalent
    lda zp_ptr_hi
    clc
    adc #$D4                    // $D800 - $0400 = $D400 offset
    sta zp_tmp

    lda #COLOR_ORANGE
    cpx #10
    bcs set_sand_color
    lda #COLOR_GREY             // Friendly base concrete tarmac
set_sand_color:
    tay
    lda zp_tmp
    sta zp_ptr_hi
    tya
    sta (zp_ptr_lo), x

    // Restore pointer hi
    lda zp_ptr_hi
    sec
    sbc #$D4
    sta zp_ptr_hi

    inx
    cpx #40
    bne ground_col_loop

    ldy zp_tmp                  // dummy restore
    iny                         // Next row
    cpy #25
    bne ground_row_loop

    // Draw Friendly Base Structures (Left: Columns 1..8, Row 17..18)
    // Hospital Triage Bunker: [ + H O S P I T A L + ]
    ldx #0
base_print_loop:
    lda base_text, x
    beq draw_barracks_initial
    sta SCREEN_RAM + 40 * 17 + 1, x
    lda #COLOR_LIGHT_GREEN
    sta COLOR_RAM + 40 * 17 + 1, x
    inx
    bne base_print_loop

draw_barracks_initial:
    jsr draw_barracks_structures
    rts

draw_barracks_structures:
    // Compound 1 at column 20..24, Row 17..18
    lda zp_barracks1_hp
    beq b1_destroyed
    ldx #0
b1_loop:
    lda barracks_text, x
    beq draw_b2
    sta SCREEN_RAM + 40 * 17 + 20, x
    lda #COLOR_LIGHT_RED
    sta COLOR_RAM + 40 * 17 + 20, x
    inx
    bne b1_loop

b1_destroyed:
    // Show rubble
    ldx #0
b1_rubble:
    lda rubble_text, x
    beq draw_b2
    sta SCREEN_RAM + 40 * 17 + 20, x
    lda #COLOR_BROWN
    sta COLOR_RAM + 40 * 17 + 20, x
    inx
    bne b1_rubble

draw_b2:
    // Compound 2 at column 32..36, Row 17..18
    lda zp_barracks2_hp
    beq b2_destroyed
    ldx #0
b2_loop:
    lda barracks_text, x
    beq barracks_done
    sta SCREEN_RAM + 40 * 17 + 32, x
    lda #COLOR_LIGHT_RED
    sta COLOR_RAM + 40 * 17 + 32, x
    inx
    bne b2_loop

b2_destroyed:
    ldx #0
b2_rubble:
    lda rubble_text, x
    beq barracks_done
    sta SCREEN_RAM + 40 * 17 + 32, x
    lda #COLOR_BROWN
    sta COLOR_RAM + 40 * 17 + 32, x
    inx
    bne b2_rubble

barracks_done:
    rts

hud_line_1:
    .text "SCORE:00000  RESCUED:00  CARGO:00/16"
    .byte 0

hud_line_2:
    .text "SHIELD:[||||||||]  RADAR:[B....T..J.P]"
    .byte 0

base_text:
    .text "[+MEDIC+]"
    .byte 0

barracks_text:
    .text "[#POW#]"
    .byte 0

rubble_text:
    .text "...:... "
    .byte 0

// ==============================================================================
// PLAYER INPUT HANDLING (JOYSTICK PORT 2 + KEYBOARD)
// ==============================================================================
update_player_input:
    // Read Joystick 2 from CIA1 Port A ($DC00)
    // Bits: 0=Up, 1=Down, 2=Left, 3=Right, 4=Fire (0 = Pressed)
    lda CIA1_DATA_A
    sta zp_tmp

    // Also check keyboard for W/S/A/D / Cursors / Space
    jsr KERNAL_GETIN
    cmp #'W'
    bne not_key_w
    lda zp_tmp
    and #$FE                    // Force Up pressed
    sta zp_tmp
not_key_w:
    cmp #'S'
    bne not_key_s
    lda zp_tmp
    and #$FD                    // Force Down pressed
    sta zp_tmp
not_key_s:
    cmp #'A'
    bne not_key_a
    lda zp_tmp
    and #$FB                    // Force Left pressed
    sta zp_tmp
not_key_a:
    cmp #'D'
    bne not_key_d
    lda zp_tmp
    and #$F7                    // Force Right pressed
    sta zp_tmp
not_key_d:
    cmp #' '
    bne not_key_space
    lda zp_tmp
    and #$EF                    // Force Fire pressed
    sta zp_tmp
not_key_space:

    // 1. Check UP (Thrust)
    lda zp_tmp
    and #$01
    bne no_thrust_up
    // Accelerate upward
    lda zp_chop_vy
    sec
    sbc #2
    cmp #$F0                    // Max upward speed cap (-16)
    bcs set_vy_up
    lda #$F0
set_vy_up:
    sta zp_chop_vy
    lda #0
    sta zp_chop_landed          // Lift off!
no_thrust_up:

    // 2. Check DOWN (Descent)
    lda zp_tmp
    and #$02
    bne no_thrust_down
    lda zp_chop_vy
    clc
    adc #2
    cmp #14                     // Max downward speed cap (+14)
    bcc set_vy_down
    lda #14
set_vy_down:
    sta zp_chop_vy
no_thrust_down:

    // 3. Check LEFT
    lda zp_tmp
    and #$04
    bne no_thrust_left
    lda #2                      // Facing Left
    sta zp_chop_facing
    lda zp_chop_vx
    sec
    sbc #2
    cmp #$F2                    // Max leftward speed cap (-14)
    bcs set_vx_left
    lda #$F2
set_vx_left:
    sta zp_chop_vx
    lda #0
    sta zp_chop_landed
    jmp check_fire

no_thrust_left:
    // 4. Check RIGHT
    lda zp_tmp
    and #$08
    bne no_thrust_right
    lda #0                      // Facing Right
    sta zp_chop_facing
    lda zp_chop_vx
    clc
    adc #2
    cmp #14                     // Max rightward speed cap (+14)
    bcc set_vx_right
    lda #14
set_vx_right:
    sta zp_chop_vx
    lda #0
    sta zp_chop_landed
    jmp check_fire

no_thrust_right:
    // Neither Left nor Right pressed: Transition to Hover if speed is low
    lda zp_chop_vx
    beq set_center_hover
    // Friction: smoothly slow down horizontal speed
    bpl slow_down_right
    // Negative vx: add 1
    inc zp_chop_vx
    jmp check_fire
slow_down_right:
    dec zp_chop_vx
    jmp check_fire
set_center_hover:
    lda #1                      // Facing Center / Hover
    sta zp_chop_facing

check_fire:
    // 5. Check FIRE button
    lda zp_tmp
    and #$10
    bne fire_done
    // Fire Vulcan Cannon or Bomb!
    jsr player_fire_weapon
fire_done:
    rts

// ==============================================================================
// HELICOPTER INERTIAL PHYSICS & TOUCHDOWN LOGIC
// ==============================================================================
update_chopper_physics:
    lda zp_chop_landed
    beq chopper_in_flight
    // If landed, zero velocities
    lda #0
    sta zp_chop_vx
    sta zp_chop_vy
    rts

chopper_in_flight:
    // Apply gentle gravity downwards
    inc zp_chop_vy

    // Integrate Horizontal Velocity (Sub-pixel math)
    lda zp_chop_sub_x
    clc
    adc zp_chop_vx
    sta zp_chop_sub_x
    // Sign-extend high byte movement
    lda zp_chop_vx
    bpl vx_pos
    // Negative vx
    lda zp_chop_sub_x
    bcc x_dec_now
    rts
x_dec_now:
    lda zp_chop_x_lo
    bne dec_x_lo
    // Crossing 256 boundary
    dec zp_chop_x_hi
dec_x_lo:
    dec zp_chop_x_lo
    jmp clamp_x_min

vx_pos:
    // Positive vx
    lda zp_chop_sub_x
    bcs x_inc_now
    jmp apply_y_physics
x_inc_now:
    inc zp_chop_x_lo
    bne clamp_x_max
    inc zp_chop_x_hi

clamp_x_max:
    // Right screen limit ~330 (MSB=1, Lo=74)
    lda zp_chop_x_hi
    beq apply_y_physics
    lda zp_chop_x_lo
    cmp #80
    bcc apply_y_physics
    lda #80
    sta zp_chop_x_lo
    lda #0
    sta zp_chop_vx
    jmp apply_y_physics

clamp_x_min:
    // Left screen limit (X >= 24)
    lda zp_chop_x_hi
    bne apply_y_physics
    lda zp_chop_x_lo
    cmp #24
    bcs apply_y_physics
    lda #24
    sta zp_chop_x_lo
    lda #0
    sta zp_chop_vx

apply_y_physics:
    // Integrate Vertical Velocity
    lda zp_chop_sub_y
    clc
    adc zp_chop_vy
    sta zp_chop_sub_y
    lda zp_chop_vy
    bpl vy_pos
    // Moving up
    lda zp_chop_sub_y
    bcc y_dec_now
    jmp check_ceiling
y_dec_now:
    dec zp_chop_y
    jmp check_ceiling

vy_pos:
    // Moving down
    lda zp_chop_sub_y
    bcs y_inc_now
    jmp check_ground
y_inc_now:
    inc zp_chop_y

check_ground:
    // Check Touchdown / Ground Collision
    lda zp_chop_y
    cmp #GROUND_Y
    bcc check_ceiling

    // Reached ground level!
    lda #GROUND_Y
    sta zp_chop_y

    // Check landing conditions:
    // Must be facing Center/Hover (or slight angle) and low vertical velocity
    lda zp_chop_vy
    cmp #6
    bcs chopper_crashed         // Too fast downward: CRASH!

    lda zp_chop_vx
    cmp #$FE
    bcc chopper_crashed         // Moving left too fast
    cmp #3
    bcs chopper_crashed         // Moving right too fast

    // Successful soft landing!
    lda #1
    sta zp_chop_landed
    lda #0
    sta zp_chop_vx
    sta zp_chop_vy
    lda #1
    sta zp_chop_facing          // Center on skids

    // Trigger boarding / unboarding check
    jsr check_landing_interactions
    rts

chopper_crashed:
    // Crash explosion and shield deduction
    dec zp_chop_shield
    dec zp_chop_shield
    lda #2                      // SFX: Explosion
    sta zp_sfx_type
    lda #30
    sta zp_sfx_timer
    lda #GROUND_Y - 8
    sta zp_chop_y
    lda #0
    sta zp_chop_vy
    sta zp_chop_vx
    rts

check_ceiling:
    lda zp_chop_y
    cmp #CEILING_Y
    bcs y_ok
    lda #CEILING_Y
    sta zp_chop_y
    lda #0
    sta zp_chop_vy
y_ok:
    rts

// ==============================================================================
// LANDING INTERACTIONS (Hostage Boarding & Rescue at Base)
// ==============================================================================
check_landing_interactions:
    // Check if landed at friendly home base
    lda zp_chop_x_hi
    bne field_landing
    lda zp_chop_x_lo
    cmp #BASE_X_MAX
    bcs field_landing

    // Landed at Base! Disembark any hostages onboard
    lda zp_chop_cargo
    beq base_done

    // Transfer cargo to rescued count
    clc
    adc zp_rescued_count
    sta zp_rescued_count
    lda #0
    sta zp_chop_cargo

    // Play Victory Fanfare / Chime
    lda #3                      // SFX: Hostage rescue chime
    sta zp_sfx_type
    lda #40
    sta zp_sfx_timer

    // Check if all 16 hostages rescued -> VICTORY!
    lda zp_rescued_count
    cmp #16
    bcc base_done
    lda #3                      // Victory state
    sta zp_game_state

base_done:
    rts

field_landing:
    // Landed in hostile field: Signal any escaping hostages to run & board
    lda zp_h1_state
    cmp #1                      // Escaped / Waving
    bne check_h2_land
    lda #2                      // Set to RUNNING to chopper
    sta zp_h1_state

check_h2_land:
    lda zp_h2_state
    cmp #1
    bne field_done
    lda #2
    sta zp_h2_state

field_done:
    rts

// ==============================================================================
// WEAPONS & COMBAT SYSTEM
// ==============================================================================
player_fire_weapon:
    lda zp_bullet_active
    bne fire_already_active

    // Fire sound effect
    lda #1                      // SFX: Vulcan cannon
    sta zp_sfx_type
    lda #10
    sta zp_sfx_timer

    // Activate bullet
    lda #1
    sta zp_bullet_active

    // Position bullet at chopper nose/belly
    lda zp_chop_x_lo
    sta zp_bullet_x_lo
    lda zp_chop_x_hi
    sta zp_bullet_x_hi
    lda zp_chop_y
    clc
    adc #8
    sta zp_bullet_y

    // Bullet trajectory based on chopper facing
    lda zp_chop_facing
    bne check_facing_center
    // Facing Right: fires diagonally forward-down
    lda #5
    sta zp_bullet_vx
    lda #2
    sta zp_bullet_vy
    rts

check_facing_center:
    cmp #1
    bne facing_left_bullet
    // Facing Center / Hover: Drops bomb / strafes straight down
    lda #0
    sta zp_bullet_vx
    lda #5
    sta zp_bullet_vy
    rts

facing_left_bullet:
    // Facing Left: fires diagonally left-down
    lda #$FB                    // -5
    sta zp_bullet_vx
    lda #2
    sta zp_bullet_vy

fire_already_active:
    rts

update_weapons:
    // Update player bullet
    lda zp_bullet_active
    beq update_enemy_shell

    lda zp_bullet_y
    clc
    adc zp_bullet_vy
    sta zp_bullet_y

    // Apply X velocity
    lda zp_bullet_x_lo
    clc
    adc zp_bullet_vx
    sta zp_bullet_x_lo
    bcc bullet_ground_check
    inc zp_bullet_x_hi

bullet_ground_check:
    lda zp_bullet_y
    cmp #GROUND_Y + 4
    bcc update_enemy_shell
    // Hit ground: Deactivate
    lda #0
    sta zp_bullet_active

update_enemy_shell:
    lda zp_shell_active
    beq weapons_done

    lda zp_shell_y
    clc
    adc zp_shell_vy
    sta zp_shell_y

    lda zp_shell_x_lo
    clc
    adc zp_shell_vx
    sta zp_shell_x_lo

    // Despawn if out of bounds or hits ground
    lda zp_shell_y
    cmp #GROUND_Y + 4
    bcs shell_dead
    cmp #CEILING_Y - 10
    bcc shell_dead
    rts

shell_dead:
    lda #0
    sta zp_shell_active
weapons_done:
    rts

// ==============================================================================
// BARRACKS / POW COMPOUNDS
// ==============================================================================
update_barracks:
    // Check if player bullet hit Barracks 1
    lda zp_bullet_active
    beq check_b2_bullet

    lda zp_barracks1_hp
    beq check_b2_bullet
    lda zp_bullet_x_hi
    bne check_b2_bullet
    lda zp_bullet_x_lo
    cmp #BARRACKS1_X - 10
    bcc check_b2_bullet
    cmp #BARRACKS1_X + 24
    bcs check_b2_bullet
    lda zp_bullet_y
    cmp #GROUND_Y - 20
    bcc check_b2_bullet

    // Hit Barracks 1!
    dec zp_barracks1_hp
    lda #0
    sta zp_bullet_active
    lda #2                      // SFX: Explosion
    sta zp_sfx_type
    lda #20
    sta zp_sfx_timer
    jsr draw_barracks_structures

    // If destroyed, release Hostage 1!
    lda zp_barracks1_hp
    bne check_b2_bullet
    lda #1                      // Waving / Escaped state
    sta zp_h1_state

check_b2_bullet:
    lda zp_bullet_active
    beq barracks_done2

    lda zp_barracks2_hp
    beq barracks_done2
    lda zp_bullet_x_hi
    beq barracks_done2          // Barracks 2 is > 255 X
    lda zp_bullet_x_lo
    cmp #BARRACKS2_X - 256 - 10
    bcc barracks_done2
    cmp #BARRACKS2_X - 256 + 24
    bcs barracks_done2
    lda zp_bullet_y
    cmp #GROUND_Y - 20
    bcc barracks_done2

    // Hit Barracks 2!
    dec zp_barracks2_hp
    lda #0
    sta zp_bullet_active
    lda #2                      // SFX: Explosion
    sta zp_sfx_type
    lda #20
    sta zp_sfx_timer
    jsr draw_barracks_structures

    lda zp_barracks2_hp
    bne barracks_done2
    lda #1                      // Release Hostage 2!
    sta zp_h2_state

barracks_done2:
    rts

// ==============================================================================
// HOSTAGE AI (Waving, Running, Boarding)
// ==============================================================================
update_hostages:
    // Update Hostage 1
    lda zp_h1_active
    beq check_h2_ai
    lda zp_h1_state
    beq check_h2_ai             // Still trapped

    cmp #1
    beq h1_waving_ai
    cmp #2
    beq h1_running_ai
    jmp check_h2_ai

h1_waving_ai:
    // Escaped and waving, waiting for chopper to land
    jmp check_h2_ai

h1_running_ai:
    // Run toward helicopter position
    lda zp_h1_x_hi
    cmp zp_chop_x_hi
    bcc h1_run_right
    bne h1_run_left
    lda zp_h1_x_lo
    cmp zp_chop_x_lo
    bcc h1_run_right
    bne h1_run_left

    // Reached Helicopter! Board cargo bay
    lda zp_chop_cargo
    cmp #16
    bcs h1_full                 // Cargo full
    inc zp_chop_cargo
    lda #0                      // Inactive (now inside chopper)
    sta zp_h1_active
    sta zp_h1_state
    // Play Boarding Chime
    lda #3
    sta zp_sfx_type
    lda #15
    sta zp_sfx_timer
h1_full:
    jmp check_h2_ai

h1_run_right:
    inc zp_h1_x_lo
    bne h1_set_dir_r
    inc zp_h1_x_hi
h1_set_dir_r:
    lda #0
    sta zp_h1_dir
    jmp check_h2_ai

h1_run_left:
    lda zp_h1_x_lo
    bne h1_sub_l
    dec zp_h1_x_hi
h1_sub_l:
    dec zp_h1_x_lo
    lda #1
    sta zp_h1_dir

check_h2_ai:
    // Update Hostage 2
    lda zp_h2_active
    beq hostage_done
    lda zp_h2_state
    cmp #2
    bne hostage_done

    // Hostage 2 running to chopper
    lda zp_h2_x_hi
    cmp zp_chop_x_hi
    bcc h2_run_right
    bne h2_run_left
    lda zp_h2_x_lo
    cmp zp_chop_x_lo
    bcc h2_run_right
    bne h2_run_left

    // Reached helicopter! Board
    lda zp_chop_cargo
    cmp #16
    bcs hostage_done
    inc zp_chop_cargo
    lda #0
    sta zp_h2_active
    sta zp_h2_state
    lda #3
    sta zp_sfx_type
    lda #15
    sta zp_sfx_timer
    rts

h2_run_right:
    inc zp_h2_x_lo
    bne h2_set_dir_r
    inc zp_h2_x_hi
h2_set_dir_r:
    lda #0
    sta zp_h2_dir
    rts

h2_run_left:
    lda zp_h2_x_lo
    bne h2_sub_l
    dec zp_h2_x_hi
h2_sub_l:
    dec zp_h2_x_lo
    lda #1
    sta zp_h2_dir

hostage_done:
    rts

// ==============================================================================
// ENEMY TANK AI (Patrol & Anti-Air Flak)
// ==============================================================================
update_tank:
    lda zp_tank_active
    beq tank_done

    // Patrol movement (bounce between X=120 and X=240)
    lda zp_tank_dir
    bne tank_move_right

    // Moving left
    dec zp_tank_x_lo
    lda zp_tank_x_lo
    cmp #120
    bcs tank_fire_check
    lda #1
    sta zp_tank_dir
    jmp tank_fire_check

tank_move_right:
    inc zp_tank_x_lo
    lda zp_tank_x_lo
    cmp #240
    bcc tank_fire_check
    lda #0
    sta zp_tank_dir

tank_fire_check:
    // Decrement reload timer
    dec zp_tank_reload
    bne tank_done

    // Reset reload timer (60 frames)
    lda #60
    sta zp_tank_reload

    // If shell already active, don't fire
    lda zp_shell_active
    bne tank_done

    // Aim and fire shell upward at chopper!
    lda #1
    sta zp_shell_active
    lda zp_tank_x_lo
    sta zp_shell_x_lo
    lda zp_tank_x_hi
    sta zp_shell_x_hi
    lda zp_tank_y
    sec
    sbc #6
    sta zp_shell_y

    // Arc velocity
    lda #$FE                    // Moving up (-2)
    sta zp_shell_vy
    // Aim towards chopper X
    lda zp_chop_x_lo
    cmp zp_tank_x_lo
    bcc fire_left
    lda #2
    sta zp_shell_vx
    jmp fire_tank_sfx
fire_left:
    lda #$FE                    // -2
    sta zp_shell_vx

fire_tank_sfx:
    lda #2                      // Boom SFX
    sta zp_sfx_type
    lda #15
    sta zp_sfx_timer

tank_done:
    rts

// ==============================================================================
// ENEMY JET INTERCEPTOR (Supersonic Strafing)
// ==============================================================================
update_jet:
    lda zp_jet_active
    bne jet_flying

    // Inactive: countdown spawn timer
    dec zp_jet_timer
    bne jet_done

    // Spawn Jet!
    lda #1
    sta zp_jet_active
    lda #0
    sta zp_jet_dir              // Flying Left
    lda #80                     // High altitude
    sta zp_jet_y
    lda #60
    sta zp_jet_x_lo
    lda #1                      // Spawn at far right (X > 255)
    sta zp_jet_x_hi
    rts

jet_flying:
    // Supersonic speed (3 pixels per frame)
    lda zp_jet_x_lo
    sec
    sbc #4
    sta zp_jet_x_lo
    bcs jet_check_bounds
    dec zp_jet_x_hi

jet_check_bounds:
    lda zp_jet_x_hi
    bne jet_done
    lda zp_jet_x_lo
    cmp #16
    bcs jet_done

    // Jet flew past screen: reset timer
    lda #0
    sta zp_jet_active
    lda #150                    // Wait 150 frames before next pass
    sta zp_jet_timer

jet_done:
    rts

// ==============================================================================
// COLLISION DETECTION & DAMAGE
// ==============================================================================
check_collisions:
    // 1. Check if tank shell hits helicopter
    lda zp_shell_active
    beq check_jet_bomb_hit

    lda zp_shell_x_hi
    cmp zp_chop_x_hi
    bne check_jet_bomb_hit

    lda zp_shell_x_lo
    sec
    sbc zp_chop_x_lo
    clc
    adc #12                     // Centering
    cmp #24
    bcs check_jet_bomb_hit

    lda zp_shell_y
    sec
    sbc zp_chop_y
    clc
    adc #10
    cmp #20
    bcs check_jet_bomb_hit

    // Hit by shell!
    lda #0
    sta zp_shell_active
    dec zp_chop_shield
    lda #2                      // Explosion SFX
    sta zp_sfx_type
    lda #25
    sta zp_sfx_timer

check_jet_bomb_hit:
    // Check if player bullet hits tank
    lda zp_bullet_active
    beq check_player_shield_status

    lda zp_tank_active
    beq check_player_shield_status

    lda zp_bullet_x_hi
    cmp zp_tank_x_hi
    bne check_player_shield_status

    lda zp_bullet_x_lo
    sec
    sbc zp_tank_x_lo
    clc
    adc #10
    cmp #20
    bcs check_player_shield_status

    lda zp_bullet_y
    cmp #GROUND_Y - 14
    bcc check_player_shield_status

    // Tank destroyed!
    lda #0
    sta zp_bullet_active
    sta zp_tank_active
    lda #2
    sta zp_sfx_type
    lda #40
    sta zp_sfx_timer

check_player_shield_status:
    lda zp_chop_shield
    bne no_game_over
    // Shield depleted: Game Over!
    lda #2
    sta zp_game_state

no_game_over:
    rts

// ==============================================================================
// HUD DISPLAY UPDATE (Score, Hostages, Shield)
// ==============================================================================
update_hud:
    // Update Rescued Count display (Row 0, col 21)
    lda zp_rescued_count
    jsr convert_to_bcd
    pha
    lsr
    lsr
    lsr
    lsr
    ora #$30
    sta SCREEN_RAM + 21
    pla
    and #$0F
    ora #$30
    sta SCREEN_RAM + 22

    // Update Cargo Count display (Row 0, col 32)
    lda zp_chop_cargo
    jsr convert_to_bcd
    pha
    lsr
    lsr
    lsr
    lsr
    ora #$30
    sta SCREEN_RAM + 31
    pla
    and #$0F
    ora #$30
    sta SCREEN_RAM + 32

    // Update Shield Bar (Row 1, col 8..15)
    ldx #0
shield_bar_loop:
    cpx zp_chop_shield
    bcc show_shield_bar
    lda #$20                    // Blank space
    jmp write_shield_char
show_shield_bar:
    lda #$7C                    // Solid vertical bar character '|'
write_shield_char:
    sta SCREEN_RAM + 40 + 8, x
    inx
    cpx #8
    bne shield_bar_loop

    rts

convert_to_bcd:
    // Simple 8-bit binary to BCD (0..99)
    tax
    lda #0
    sed
bcd_loop:
    cpx #0
    beq bcd_done
    clc
    adc #1
    dex
    jmp bcd_loop
bcd_done:
    cld
    rts

// ==============================================================================
// VIC-II HARDWARE SPRITE MULTIPLEXER & REGISTERS
// ==============================================================================
update_hardware_sprites:
    // Enable Sprites 0..7
    lda #%11111111
    sta VIC_SP_ENABLE

    // Reset MSB of X coordinates
    lda #$00
    sta VIC_MSB_X

    // -------------------------------------------------------------------------
    // Sprite 0: Chopper Fuselage
    // -------------------------------------------------------------------------
    lda zp_chop_x_lo
    sta VIC_SP0_X
    lda zp_chop_y
    sta VIC_SP0_Y
    lda zp_chop_x_hi
    beq sp0_msb_done
    lda VIC_MSB_X
    ora #%00000001
    sta VIC_MSB_X
sp0_msb_done:

    // Select Fuselage Sprite Frame based on facing
    ldx #SP_CHOPPER_R
    lda zp_chop_facing
    beq set_sp0_ptr
    cmp #1
    bne sp0_facing_left
    ldx #SP_CHOPPER_C
    jmp set_sp0_ptr
sp0_facing_left:
    ldx #SP_CHOPPER_L
set_sp0_ptr:
    stx SPRITE_PTR_BASE + 0
    lda #COLOR_WHITE
    sta VIC_SP0_COLOR

    // -------------------------------------------------------------------------
    // Sprite 1: Chopper Rotor Blades (Positioned directly above fuselage)
    // -------------------------------------------------------------------------
    lda zp_chop_x_lo
    sta VIC_SP1_X
    lda zp_chop_y
    sec
    sbc #6                      // 6 pixels above fuselage
    sta VIC_SP1_Y
    lda zp_chop_x_hi
    beq sp1_msb_done
    lda VIC_MSB_X
    ora #%00000010
    sta VIC_MSB_X
sp1_msb_done:

    lda zp_rotor_frame
    clc
    adc #SP_ROTOR_BASE
    sta SPRITE_PTR_BASE + 1
    lda #COLOR_CYAN
    sta VIC_SP0_COLOR + 1

    // -------------------------------------------------------------------------
    // Sprite 2: Hostage 1
    // -------------------------------------------------------------------------
    lda zp_h1_active
    beq hide_sp2
    lda zp_h1_x_lo
    sta VIC_SP2_X
    lda zp_h1_y
    sta VIC_SP2_Y
    lda zp_h1_x_hi
    beq sp2_msb_done
    lda VIC_MSB_X
    ora #%00000100
    sta VIC_MSB_X
sp2_msb_done:

    // Frame logic
    lda zp_h1_state
    cmp #1
    bne sp2_check_running
    lda #SP_HOSTAGE_WAVE
    jmp set_sp2_frame
sp2_check_running:
    lda zp_h1_dir
    bne sp2_run_left
    lda zp_hostage_anim
    clc
    adc #SP_HOSTAGE_R
    jmp set_sp2_frame
sp2_run_left:
    lda zp_hostage_anim
    clc
    adc #SP_HOSTAGE_L
set_sp2_frame:
    sta SPRITE_PTR_BASE + 2
    lda #COLOR_YELLOW
    sta VIC_SP0_COLOR + 2
    jmp setup_sp3

hide_sp2:
    lda #0
    sta VIC_SP2_Y

setup_sp3:
    // -------------------------------------------------------------------------
    // Sprite 3: Hostage 2
    // -------------------------------------------------------------------------
    lda zp_h2_active
    beq hide_sp3
    lda zp_h2_x_lo
    sta VIC_SP3_X
    lda zp_h2_y
    sta VIC_SP3_Y
    lda zp_h2_x_hi
    beq sp3_msb_done
    lda VIC_MSB_X
    ora #%00001000
    sta VIC_MSB_X
sp3_msb_done:

    lda zp_h2_dir
    bne sp3_run_left
    lda zp_hostage_anim
    clc
    adc #SP_HOSTAGE_R
    jmp set_sp3_frame
sp3_run_left:
    lda zp_hostage_anim
    clc
    adc #SP_HOSTAGE_L
set_sp3_frame:
    sta SPRITE_PTR_BASE + 3
    lda #COLOR_YELLOW
    sta VIC_SP0_COLOR + 3
    jmp setup_sp4

hide_sp3:
    lda #0
    sta VIC_SP3_Y

setup_sp4:
    // -------------------------------------------------------------------------
    // Sprite 4: Enemy Tank
    // -------------------------------------------------------------------------
    lda zp_tank_active
    beq hide_sp4
    lda zp_tank_x_lo
    sta VIC_SP4_X
    lda zp_tank_y
    sta VIC_SP4_Y
    lda zp_tank_x_hi
    beq sp4_msb_done
    lda VIC_MSB_X
    ora #%00010000
    sta VIC_MSB_X
sp4_msb_done:

    lda #SP_TANK_BODY
    sta SPRITE_PTR_BASE + 4
    lda #COLOR_DARK_GREY
    sta VIC_SP0_COLOR + 4
    jmp setup_sp5

hide_sp4:
    lda #0
    sta VIC_SP4_Y

setup_sp5:
    // -------------------------------------------------------------------------
    // Sprite 5: Enemy Jet
    // -------------------------------------------------------------------------
    lda zp_jet_active
    beq hide_sp5
    lda zp_jet_x_lo
    sta VIC_SP5_X
    lda zp_jet_y
    sta VIC_SP5_Y
    lda zp_jet_x_hi
    beq sp5_msb_done
    lda VIC_MSB_X
    ora #%00100000
    sta VIC_MSB_X
sp5_msb_done:

    lda #SP_JET_L
    sta SPRITE_PTR_BASE + 5
    lda #COLOR_LIGHT_RED
    sta VIC_SP0_COLOR + 5
    jmp setup_sp6

hide_sp5:
    lda #0
    sta VIC_SP5_Y

setup_sp6:
    // -------------------------------------------------------------------------
    // Sprite 6: Player Bullet / Bomb
    // -------------------------------------------------------------------------
    lda zp_bullet_active
    beq hide_sp6
    lda zp_bullet_x_lo
    sta VIC_SP6_X
    lda zp_bullet_y
    sta VIC_SP6_Y
    lda zp_bullet_x_hi
    beq sp6_msb_done
    lda VIC_MSB_X
    ora #%01000000
    sta VIC_MSB_X
sp6_msb_done:

    lda #SP_BULLET_P
    sta SPRITE_PTR_BASE + 6
    lda #COLOR_LIGHT_GREEN
    sta VIC_SP0_COLOR + 6
    jmp setup_sp7

hide_sp6:
    lda #0
    sta VIC_SP6_Y

setup_sp7:
    // -------------------------------------------------------------------------
    // Sprite 7: Enemy Shell / Explosion
    // -------------------------------------------------------------------------
    lda zp_shell_active
    beq hide_sp7
    lda zp_shell_x_lo
    sta VIC_SP7_X
    lda zp_shell_y
    sta VIC_SP7_Y
    lda zp_shell_x_hi
    beq sp7_msb_done
    lda VIC_MSB_X
    ora #%10000000
    sta VIC_MSB_X
sp7_msb_done:

    lda #SP_SHELL_E
    sta SPRITE_PTR_BASE + 7
    lda #COLOR_ORANGE
    sta VIC_SP0_COLOR + 7
    rts

hide_sp7:
    lda #0
    sta VIC_SP7_Y
    rts

// ==============================================================================
// SID 6581/8580 SOUND & MUSIC ENGINE
// ==============================================================================
sid_reset:
    ldx #$18
    lda #0
clear_sid_loop:
    sta $D400, x
    dex
    bpl clear_sid_loop

    // Set Master Volume to 15 (Max)
    lda #$0F
    sta SID_VOLUME

    // Initialize Voice 1 (Lead Synth): Fast attack, medium decay
    lda #$08
    sta SID_V1_AD
    lda #$94
    sta SID_V1_SR

    // Initialize Voice 2 (Bass Synth): Pulse wave
    lda #$19
    sta SID_V2_AD
    lda #$83
    sta SID_V2_SR
    lda #$08
    sta SID_V2_PW_HI

    // Initialize Voice 3 (Percussion & SFX): Fast decay noise
    lda #$05
    sta SID_V3_AD
    lda #$00
    sta SID_V3_SR
    rts

sid_play_frame:
    // If an SFX is playing, handle SFX priority
    lda zp_sfx_timer
    beq play_sid_music

    dec zp_sfx_timer
    lda zp_sfx_type
    cmp #1                      // Vulcan fire
    beq sfx_vulcan
    cmp #2                      // Explosion
    beq sfx_explosion
    cmp #3                      // Chime
    beq sfx_chime
    jmp play_sid_music

sfx_vulcan:
    lda #$81                    // Noise + Gate
    sta SID_V3_CTRL
    lda #$24
    sta SID_V3_FREQ_HI
    lda #$00
    sta SID_V3_FREQ_LO
    rts

sfx_explosion:
    lda #$81                    // Deep noise
    sta SID_V3_CTRL
    lda zp_sfx_timer
    lsr
    sta SID_V3_FREQ_HI
    rts

sfx_chime:
    lda #$11                    // Triangle + Gate on Voice 1
    sta SID_V1_CTRL
    lda #$35                    // High C
    sta SID_V1_FREQ_HI
    rts

play_sid_music:
    // Update background SID music notes every 8 frames
    inc zp_music_speed
    lda zp_music_speed
    cmp #8
    bcc music_frame_done
    lda #0
    sta zp_music_speed

    // Advance note index (0..15)
    ldx zp_music_step
    inx
    txa
    and #$0F
    sta zp_music_step
    tax

    // Set Voice 1 (Melody)
    lda mel_freq_hi, x
    sta SID_V1_FREQ_HI
    lda mel_freq_lo, x
    sta SID_V1_FREQ_LO
    lda #$21                    // Sawtooth + Gate
    sta SID_V1_CTRL

    // Set Voice 2 (Bass arpeggio)
    lda bass_freq_hi, x
    sta SID_V2_FREQ_HI
    lda bass_freq_lo, x
    sta SID_V2_FREQ_LO
    lda #$41                    // Pulse + Gate
    sta SID_V2_CTRL

    // Set Voice 3 (Percussion beat)
    lda drum_pattern, x
    beq music_frame_done
    sta SID_V3_CTRL
    lda #$18
    sta SID_V3_FREQ_HI

music_frame_done:
    rts

// Music Note Tables (Military Theme)
mel_freq_hi:
    .byte $1C, $1C, $22, $28, $1C, $1C, $25, $22
    .byte $1E, $1E, $25, $2B, $28, $25, $22, $1C

mel_freq_lo:
    .byte $48, $48, $B8, $3E, $48, $48, $90, $B8
    .byte $60, $60, $90, $80, $3E, $90, $B8, $48

bass_freq_hi:
    .byte $0E, $0E, $11, $14, $0E, $0E, $12, $11
    .byte $0F, $0F, $12, $15, $14, $12, $11, $0E

bass_freq_lo:
    .byte $24, $24, $5C, $1F, $24, $24, $C8, $5C
    .byte $30, $30, $C8, $40, $1F, $C8, $5C, $24

drum_pattern:
    .byte $81, $00, $81, $00, $81, $81, $81, $00
    .byte $81, $00, $81, $00, $81, $81, $00, $81

// ==============================================================================
// UTILITY ROUTINES & TABLES
// ==============================================================================
clear_screen:
    ldx #0
clr_loop:
    lda #$20                    // Blank space
    sta SCREEN_RAM, x
    sta SCREEN_RAM + $100, x
    sta SCREEN_RAM + $200, x
    sta SCREEN_RAM + $2E8, x
    lda #COLOR_WHITE
    sta COLOR_RAM, x
    sta COLOR_RAM + $100, x
    sta COLOR_RAM + $200, x
    sta COLOR_RAM + $2E8, x
    inx
    bne clr_loop
    rts

screen_row_offsets_lo:
    .fill 25, <(SCREEN_RAM + i * 40)

screen_row_offsets_hi:
    .fill 25, >(SCREEN_RAM + i * 40)

// ==============================================================================
// HIGH-DEFINITION SPRITE DATA (32 Sprites, 64 Bytes Each)
// ==============================================================================
* = $3000 "Sprite Graphics"

// Sprite 0: Chopper Facing Right
sp_data_chopper_r:
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00011000, %00000000
    .byte %00000000, %00011000, %00000000
    .byte %00000011, %11111111, %11110000
    .byte %00111111, %11111111, %11111100
    .byte %11111111, %11000011, %11111110
    .byte %11111111, %11000011, %11111111
    .byte %00111111, %11111111, %11111111
    .byte %00001111, %11111111, %11111110
    .byte %00000011, %11111111, %11111100
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %01000010, %00000000
    .byte %00000000, %01000010, %00000000
    .byte %00000000, %01000010, %00000000
    .byte %00000011, %11111111, %11110000
    .byte %00000000, %00000000, %00000000
    .byte %00000000, %00000000, %00000000
    .byte %00000000, %00000000, %00000000
    .byte %00000000, %00000000, %00000000
    .byte %00000000, %00000000, %00000000
    .byte %00000000, %00000000, %00000000
    .byte 0

// Sprite 1: Chopper Facing Left
sp_data_chopper_l:
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00011000, %00000000
    .byte %00000000, %00011000, %00000000
    .byte %00001111, %11111111, %11000000
    .byte %00111111, %11111111, %11111100
    .byte %01111111, %11000011, %11111111
    .byte %11111111, %11000011, %11111111
    .byte %11111111, %11111111, %11111100
    .byte %01111111, %11111111, %11110000
    .byte %00111111, %11111111, %11000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %01000010, %00000000
    .byte %00000000, %01000010, %00000000
    .byte %00000000, %01000010, %00000000
    .byte %00001111, %11111111, %11110000
    .byte %00000000, %00000000, %00000000
    .byte %00000000, %00000000, %00000000
    .byte %00000000, %00000000, %00000000
    .byte %00000000, %00000000, %00000000
    .byte %00000000, %00000000, %00000000
    .byte %00000000, %00000000, %00000000
    .byte 0

// Sprite 2: Chopper Facing Center / Hover
sp_data_chopper_c:
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00011000, %00000000
    .byte %00000000, %01111110, %00000000
    .byte %00000011, %11111111, %11000000
    .byte %00000111, %11111111, %11100000
    .byte %00001111, %00111100, %11110000
    .byte %00001111, %00111100, %11110000
    .byte %00001111, %11111111, %11110000
    .byte %00000111, %11111111, %11100000
    .byte %00000011, %11111111, %11000000
    .byte %00000001, %10000001, %10000000
    .byte %00000001, %10000001, %10000000
    .byte %00000001, %10000001, %10000000
    .byte %00000111, %11000011, %11100000
    .byte %00000000, %00000000, %00000000
    .byte %00000000, %00000000, %00000000
    .byte %00000000, %00000000, %00000000
    .byte %00000000, %00000000, %00000000
    .byte %00000000, %00000000, %00000000
    .byte %00000000, %00000000, %00000000
    .byte %00000000, %00000000, %00000000
    .byte 0

// Sprites 3..6: Rotor Blade Animation (4 Rotational Frames)
sp_data_rotor_0:
    .byte %11111111, %11111111, %11111111
    .byte %01111111, %11111111, %11111110
    .fill 19 * 3, 0
    .byte 0

sp_data_rotor_1:
    .byte %00000011, %11111111, %11100000
    .byte %00001111, %11111111, %11110000
    .fill 19 * 3, 0
    .byte 0

sp_data_rotor_2:
    .byte %00000000, %11111111, %00000000
    .byte %00000001, %11111111, %10000000
    .fill 19 * 3, 0
    .byte 0

sp_data_rotor_3:
    .byte %00000111, %11111111, %11000000
    .byte %00001111, %11111111, %11110000
    .fill 19 * 3, 0
    .byte 0

// Sprites 7..10: Hostage Running Right (4 Frames)
sp_data_hostage_r0:
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00011000, %00000000
    .byte %00000000, %01111110, %00000000
    .byte %00000000, %11111111, %00000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %01100110, %00000000
    .byte %00000000, %11000011, %00000000
    .fill 13 * 3, 0
    .byte 0

sp_data_hostage_r1:
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00011000, %00000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %01111110, %00000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00111100, %00000000
    .fill 13 * 3, 0
    .byte 0

sp_data_hostage_r2:
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00011000, %00000000
    .byte %00000000, %01111110, %00000000
    .byte %00000000, %11111111, %00000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00110011, %00000000
    .byte %00000000, %01100001, %10000000
    .fill 13 * 3, 0
    .byte 0

sp_data_hostage_r3:
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00011000, %00000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %01111110, %00000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00111100, %00000000
    .fill 13 * 3, 0
    .byte 0

// Sprites 11..14: Hostage Running Left (4 Frames)
sp_data_hostage_l0:
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00011000, %00000000
    .byte %00000000, %01111110, %00000000
    .byte %00000000, %11111111, %00000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %01100110, %00000000
    .byte %00000000, %11000011, %00000000
    .fill 13 * 3, 0
    .byte 0

sp_data_hostage_l1:
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00011000, %00000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %01111110, %00000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00111100, %00000000
    .fill 13 * 3, 0
    .byte 0

sp_data_hostage_l2:
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00011000, %00000000
    .byte %00000000, %01111110, %00000000
    .byte %00000000, %11111111, %00000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %11001100, %00000000
    .byte %00000001, %10000110, %00000000
    .fill 13 * 3, 0
    .byte 0

sp_data_hostage_l3:
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00011000, %00000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %01111110, %00000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00111100, %00000000
    .fill 13 * 3, 0
    .byte 0

// Sprite 15: Hostage Waving ("HELP!")
sp_data_hostage_wave:
    .byte %00000110, %00111100, %01100000
    .byte %00000011, %00111100, %11000000
    .byte %00000001, %11111111, %10000000
    .byte %00000000, %01111110, %00000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %01100110, %00000000
    .byte %00000000, %01100110, %00000000
    .fill 13 * 3, 0
    .byte 0

// Sprite 16: Hostage Boarding
sp_data_hostage_board:
    .byte %00000000, %01111110, %00000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %11111111, %00000000
    .byte %00000001, %11111111, %10000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00111100, %00000000
    .fill 13 * 3, 0
    .byte 0

// Sprites 17..18: Tank Body & Animated Treads
sp_data_tank_0:
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %01111110, %00000000
    .byte %00000000, %11111111, %00000000
    .byte %00000011, %11111111, %11000000
    .byte %00011111, %11111111, %11111000
    .byte %01111111, %11111111, %11111110
    .byte %11101110, %11101110, %11101111
    .byte %01111111, %11111111, %11111110
    .fill 13 * 3, 0
    .byte 0

sp_data_tank_1:
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %01111110, %00000000
    .byte %00000000, %11111111, %00000000
    .byte %00000011, %11111111, %11000000
    .byte %00011111, %11111111, %11111000
    .byte %01111111, %11111111, %11111110
    .byte %11011101, %11011101, %11011101
    .byte %01111111, %11111111, %11111110
    .fill 13 * 3, 0
    .byte 0

// Sprites 19..21: Tank Turret
sp_data_turret_0:
    .byte %00000000, %00000000, %00000000
    .byte %00000000, %01111100, %00000000
    .byte %00000001, %11111110, %00000000
    .fill 18 * 3, 0
    .byte 0

sp_data_turret_1:
    .byte %00000000, %00000000, %00000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %01111110, %00000000
    .fill 18 * 3, 0
    .byte 0

sp_data_turret_2:
    .byte %00000000, %00000000, %00000000
    .byte %00000000, %00111110, %00000000
    .byte %00000000, %01111111, %00000000
    .fill 18 * 3, 0
    .byte 0

// Sprite 22: Jet Interceptor Left
sp_data_jet_l:
    .byte %00000000, %00000000, %00000001
    .byte %00000000, %00000000, %00000011
    .byte %00000000, %00000000, %00000111
    .byte %00000000, %00000000, %00001111
    .byte %00000000, %00000000, %00011111
    .byte %11111111, %11111111, %11111111
    .byte %01111111, %11111111, %11111110
    .byte %00000000, %00000000, %00011111
    .byte %00000000, %00000000, %00001111
    .byte %00000000, %00000000, %00000111
    .byte %00000000, %00000000, %00000011
    .byte %00000000, %00000000, %00000001
    .fill 9 * 3, 0
    .byte 0

// Sprite 23: Jet Interceptor Right
sp_data_jet_r:
    .byte %10000000, %00000000, %00000000
    .byte %11000000, %00000000, %00000000
    .byte %11100000, %00000000, %00000000
    .byte %11110000, %00000000, %00000000
    .byte %11111000, %00000000, %00000000
    .byte %11111111, %11111111, %11111111
    .byte %01111111, %11111111, %11111110
    .byte %11111000, %00000000, %00000000
    .byte %11110000, %00000000, %00000000
    .byte %11100000, %00000000, %00000000
    .byte %11000000, %00000000, %00000000
    .byte %10000000, %00000000, %00000000
    .fill 9 * 3, 0
    .byte 0

// Sprites 24..25: Afterburner Flame
sp_data_afterburner_0:
    .byte %00000000, %00000000, %00000000
    .byte %00000000, %00000000, %00000000
    .byte %00000000, %00000000, %00000000
    .byte %00000000, %00000000, %00000000
    .byte %00000000, %00000000, %00000000
    .byte %00000000, %00000000, %01111111
    .fill 15 * 3, 0
    .byte 0

sp_data_afterburner_1:
    .byte %00000000, %00000000, %00000000
    .byte %00000000, %00000000, %00000000
    .byte %00000000, %00000000, %00000000
    .byte %00000000, %00000000, %00000000
    .byte %00000000, %00000000, %00000000
    .byte %00000000, %00000000, %11111111
    .fill 15 * 3, 0
    .byte 0

// Sprite 26: Player Vulcan Bullet / Bomb
sp_data_bullet:
    .byte %00000000, %00000000, %00000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %01111110, %00000000
    .byte %00000000, %00111100, %00000000
    .fill 17 * 3, 0
    .byte 0

// Sprite 27: Enemy Flak Shell
sp_data_shell:
    .byte %00000000, %00000000, %00000000
    .byte %00000000, %00011000, %00000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00011000, %00000000
    .fill 17 * 3, 0
    .byte 0

// Sprites 28..31: Multi-Stage Explosions
sp_data_explode_0:
    .byte %00000000, %00011000, %00000000
    .byte %00000000, %00111100, %00000000
    .byte %00000000, %00011000, %00000000
    .fill 18 * 3, 0
    .byte 0

sp_data_explode_1:
    .byte %00000000, %01111110, %00000000
    .byte %00000011, %11111111, %11000000
    .byte %00000000, %01111110, %00000000
    .fill 18 * 3, 0
    .byte 0

sp_data_explode_2:
    .byte %00000110, %01111110, %01100000
    .byte %00111111, %11111111, %11111100
    .byte %00000110, %01111110, %01100000
    .fill 18 * 3, 0
    .byte 0

sp_data_explode_3:
    .byte %00000010, %00000000, %01000000
    .byte %01000001, %00111100, %10000010
    .byte %00000010, %00000000, %01000000
    .fill 18 * 3, 0
    .byte 0

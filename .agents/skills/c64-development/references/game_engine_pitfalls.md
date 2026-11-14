# Game Engine Pitfalls: What Went Wrong Building a Full Game (and the Fixes)

Lessons from building TORNADO (`game_dev/tornado/`): a smooth 8-way scroller
with a raster-split HUD, isometric terrain, sprites, SID music + sound effects,
levels and a bitmap title screen. Every item below was a real bug a player saw.
Each entry gives the **symptom**, the **cause**, and the **rule / pattern** that
prevents it. `tools/gamecheck/game_check.py` (studio: **GAME CHECK**) finds
several of these automatically in any PRG.

---

## 1. Smooth scrolling and the frame pipeline

### 1.1 Fine scroll and the screen move must change together
* **Symptom**: scrolling jitters: the picture jumps back ~6 px, freezes, then
  jumps 8 px every time the camera crosses a character.
* **Cause**: `fine_x/fine_y` were written to `$D016/$D011` straight away, but the
  redrawn (coarse-shifted) screen only appeared one or two frames later.
* **Rule**: treat fine scroll, the screen page (`$D018`) and the sprite
  positions as **one published frame state**. The main loop builds the frame,
  then *publishes* it (`st_ready = 1`) and waits; the raster IRQ applies all of
  it at one safe raster line (in the border) and clears `st_ready`. Never write
  scroll or screen-base registers from the main loop while an IRQ owns them.

```asm
publish_frame:                  // main loop, end of every pass
        lda fine_y
        ora #$10
        sta nx_d011
        lda fine_x
        ora #$10
        sta nx_d016
        lda d018_val
        sta nx_d018
        lda #1
        sta st_ready
!w:     lda st_ready            // the IRQ consumes it once per frame
        bne !w-
        rts
// in the raster IRQ (line ~252):  if st_ready: copy nx_* + sprite shadow to the VIC
```

### 1.2 Sprites must be latched with the scroll
* **Symptom**: sprites wobble 1-2 px against the background while scrolling.
* **Cause**: the main loop wrote `$D000-$D010` immediately; the background moved
  one frame later.
* **Rule**: write sprite X/Y/MSB/enable into a **shadow table** and let the IRQ
  copy it to the VIC together with the scroll registers.

### 1.3 A full redraw is too slow: shift and draw edges
* **Symptom**: the game drops to 25 fps whenever the screen scrolls a character.
* **Cause**: redrawing 840 characters from a tile map cost ~39,000 cycles (two frames).
* **Rule**: double-buffer the screen. On a one-character move, copy the visible
  page into the hidden one shifted by one character (unrolled `lda src+off,x /
  sta dst,x`, ~8k cycles) and draw only the new edge row/column. Keep the full
  redraw for jumps (start, respawn, returning from another screen).

### 1.4 Colour RAM cannot be double-buffered
* **Rule**: precompute a colour map in RAM (e.g. under BASIC/KERNAL ROM, built at
  boot) and have the IRQ copy the visible rows into `$D800` right after the page
  flip, top rows first so it stays ahead of the beam.

### 1.5 Measure the frame budget
* **Rule**: record the raster line at which the main loop publishes on its
  heaviest frames (scroll steps on both axes, map edges, many sprites). Keep at
  least ~10 raster lines of margin before the IRQ deadline. When it gets tight,
  defer non-visual work (e.g. a height lookup) to frames that did not scroll.
* **Diagonals**: a character step on X and another on Y in consecutive frames
  can blow the budget. Let the camera lag the player by a few pixels so the two
  axes do not step on back-to-back frames.

---

## 2. Raster splits (HUD under a scrolling playfield)

### 2.1 Write `$D011` before the bad line can start
* **Symptom**: the HUD flickers only while scrolling vertically.
* **Cause**: with `YSCROLL = 0`, the split line itself was a bad line; the IRQ's
  `$D011` write arrived ~25 cycles into the line, after the VIC had already
  started a new character row.
* **Rule**: do the `$D011` write **first** in the split handler (before saving X/Y),
  and choose a split line where no fine-scroll value makes it a bad line.

### 2.2 Never let a partial character row sit between playfield and HUD
* **Symptom**: the HUD jumps by a whole row every few frames while scrolling.
* **Cause**: a gap row was cut short for some `fine_y` values. When a row ends
  before RC reaches 7 the VIC does not advance its row counter (VCBASE), so the
  HUD showed different screen rows from frame to frame.
* **Rule**: between the last playfield row and the HUD, keep the VIC **idle**
  for every `fine_y`. Step `$D011` to a YSCROLL value that matches none of the
  following lines (e.g. YSCROLL 6 at line 215), then to the HUD's YSCROLL (7 at
  line 219, so the HUD starts at line 223), then switch `$D016` at the start of
  the HUD's first line. Work it out for all 8 `fine_y` values on paper.

### 2.3 The idle byte shows in gaps
* **Cause**: in idle state the VIC shows byte `$3FFF` of the current bank (`$39FF`
  with ECM). Garbage there draws stripes in the gap.
* **Rule**: set it to 0 while the game runs. If it belongs to other data (e.g. the
  Koala picture), save it at boot and restore it before showing that data.

---

## 3. Switching screens (title, briefing, map, game over)

### 3.1 Turn the game's raster IRQ off before any other screen
* **Symptom**: after game over, the title picture is a jumble of game characters;
  the music still plays.
* **Cause**: the game's raster IRQ kept running and rewrote `$D011/$D016/$D018`
  every frame, forcing text mode over the bitmap title.
* **Rule**: every screen that sets its own VIC mode (title, briefing, tactical
  map, banners on another screen) starts with:

```asm
        sei
        lda #$00
        sta $D01A               // no raster IRQ
        lda #$0F
        sta $D019               // ack anything pending
        lda #<rti_stub          // vector to a plain rti
        sta $FFFE
        lda #>rti_stub
        sta $FFFF
        cli
```
  and the game re-installs its IRQ when play starts. Check **every** path into
  the screen: game over, mission complete, last level done, map exit.

### 3.2 Double buffers: write to both pages
* **Symptom**: a "MISSION COMPLETE" banner or the explosion sprite sometimes
  does not appear.
* **Cause**: it was written only to screen page 1 (or only its sprite pointer),
  while page 2 was on show.
* **Rule**: anything that is not redrawn by the scroller (banners, HUD rows,
  sprite pointers at `$xxF8`) goes to **both** screen pages.

---

## 4. Sound

### 4.1 Keep sound effects running, or silence them, before blocking loops
* **Symptom**: a pickup beep stays on until the next screen.
* **Cause**: the sound-effect timer only counts down in the game loop; the
  "MISSION COMPLETE" wait loop never called it, so the gate stayed open.
* **Rule**: before any banner / wait-for-fire loop, either keep calling the SFX
  update until its timer ends, or silence the SID (gate off all three voices,
  keep `$D418`).

### 4.2 Music only where it belongs
* **Rule**: decide which screens play music. Silence all voices when leaving
  them; re-init the tune (`jsr init`) when returning so it starts from the top.
  If a toggle key exists, read it only on the screens that play music.

---

## 5. Gameplay data must be reachable

### 5.1 Validate spawn and target positions against the player's limits
* **Symptom**: a survivor at the top edge of the map could never be picked up.
* **Cause**: the player's position is clamped (here 16..1007 px) and pickup needs
  the player within a few pixels of a hover point; that point lay outside.
* **Rule**: generate spawn points with a check that the interaction point is
  inside the movement limits **with a margin**, not under walls/roofs, not on the
  player's base. Do it at build time in the generator, then test the extremes in
  the simulator (top, bottom, left, right spot).

### 5.2 Spreading things over N islands/areas
* **Rule**: when stepping through N areas with a fixed stride, the stride must
  share no factor with N or areas repeat. Derive the stride from N in the
  generator instead of hard-coding it.

### 5.3 Count rewards when they are really delivered
* Pattern used: picked-up people are "on board"; they count only when dropped
  off on the landing pad; a crash loses them and new ones spawn elsewhere so the
  level stays completable.

---

## 6. Multicolor characters and colours

* A character cell has **one** colour-RAM colour. Plan which colours are shared
  (`$D021/$D022/$D023`) and which come from colour RAM, so neighbouring terrain
  types never need two colour-RAM colours in one cell.
* Give every terrain a *fallback* pixel for when another colour wins the cell
  (otherwise you get stray black dashes, e.g. wave crests next to grass).
* Night/day: change the shared colours and run the colour map through a mapping
  table when building it.

## 7. Bitmap title screens (Koala)

* Use `FULL_RES = True` in the scene for 160x200 instead of 160x100.
* Give each area its own 3-colour palette (+ black) so 4x8 cells do not clash;
  outline important objects (vehicles, people) in black so their cells keep their
  colours apart from the background. Small figures read better as hand-drawn
  pixel art than as formula shapes.

## 8. Isometric terrain (`tools/isotiles/iso_tool.py`)

* Heights come in 16 px levels (the only step that fits the staggered grid).
* Walls are opaque half-diamonds: tall see-through objects (tree trunks) paint
  over whatever is behind them. Keep tall things for buildings.
* Keep landing areas flat; place spawn points with `world.ground_level() == 0`
  and visible open terrain (`EXTRA_ASM`).

## 9. Memory and KickAssembler

* A PRG that BASIC loads and `SYS`es should end below `$A000`. Large runtime
  tables (colour maps) can live under the ROMs if built at boot with `$01 = $35`.
* Put extra code in free gaps with their own segments (`* = $1508 "Levels"`);
  `-showmem` reports overlaps. Track what is left after each feature.
* `relative address is illegal`: a branch over more than 127 bytes; invert it
  and `jmp`.
* `.var` lists cannot be used across passes; compute addresses with
  `.function`s or labels instead.
* `!label+` looks forward, `!label-` backward; a wrong direction is "Unknown symbol".

## 10. Verifying with the headless simulator (`tools/c64sim`)

* `tools/gamecheck/game_check.py <prg>` runs the game and reports: main code and
  IRQ fighting over display registers, stuck SID voices, fine scroll wrapping
  without the screen moving.
* For scrollers, log the displayed scroll position each frame (registers sampled
  just before the first playfield line) and look for anything but steady steps.
* Compare the shown screen and colour RAM with what the map says, sampling each
  row just before the beam reaches it.
* `c64sim` is instruction-level, not cycle-exact: confirm raster splits on VICE
  or the real machine.

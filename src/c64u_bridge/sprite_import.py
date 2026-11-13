"""
AI & Pasted Sprite Image "Tidy Up", De-Fading, Sprite Sheet Slicer, and
Perceptual CIELAB Hardware Constraint Quantizer.

Solves common artifacts in AI-generated or pasted sprite images:
1. Soft / anti-aliased edge fading (halos blending into background color or alpha gradients)
2. Non-uniform "fat pixel" grids that blur under standard bilinear downsampling
3. Off-palette intermediate colors and hardware attribute constraints:
   - C64 Multicolor (3 opaque colors + transparent per sprite, 2:1 double-wide pixels)
   - C64 Overlay (3 multicolor slots + 1 hires outline slot)
   - ZX Spectrum ULA (max 2 colors [INK+PAPER] sharing 1 BRIGHT state per 8x8 cell)
   - ZX Spectrum Next (8-bit 256-color RGB332/RGB333 with $E3 transparent, or 4-bit 16-color)
   - BBC Micro (Mode 2: 8 colors double-wide; Mode 1: 3 opaque + bg from 8; Mode 4: 1 opaque + bg)
"""

from __future__ import annotations

import base64
import io
import math
from collections import Counter, deque
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image

from .sprite import (
    BBC_MICRO_PALETTE,
    C64_PALETTE,
    MultiPlatformSpriteFrame,
    ZX_NEXT_PALETTE,
    ZX_SPECTRUM_PALETTE,
    get_platform_palette,
    hex_to_rgb,
)


# =============================================================================
# Perceptual CIELAB Color Space Math
# =============================================================================

def rgb_to_lab(r: int, g: int, b: int) -> Tuple[float, float, float]:
    """Convert sRGB (0..255) to CIE L*a*b* perceptual color space (D65 illuminant)."""
    def pivot_rgb(val: float) -> float:
        v = val / 255.0
        return ((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92

    rl, gl, bl = pivot_rgb(r), pivot_rgb(g), pivot_rgb(b)
    x = (rl * 0.4124564 + gl * 0.3575761 + bl * 0.1804375) / 0.95047
    y = (rl * 0.2126729 + gl * 0.7151522 + bl * 0.0721750) / 1.00000
    z = (rl * 0.0193339 + gl * 0.1191920 + bl * 0.9503041) / 1.08883

    def pivot_xyz(t: float) -> float:
        return t ** (1.0 / 3.0) if t > 0.008856 else (7.787 * t) + (16.0 / 116.0)

    fx, fy, fz = pivot_xyz(x), pivot_xyz(y), pivot_xyz(z)
    L = (116.0 * fy) - 16.0
    a = 500.0 * (fx - fy)
    b_val = 200.0 * (fy - fz)
    return (L, a, b_val)


def delta_e_lab(lab1: Tuple[float, float, float], lab2: Tuple[float, float, float]) -> float:
    """Compute perceptual color distance in CIELAB space."""
    dL = lab1[0] - lab2[0]
    da = lab1[1] - lab2[1]
    db = lab1[2] - lab2[2]
    return math.sqrt(dL * dL + da * da + db * db)


def rgb_distance(c1: Tuple[int, int, int], c2: Tuple[int, int, int]) -> float:
    """Redmean-weighted sRGB Euclidean distance for fast background/halo comparisons."""
    rmean = (c1[0] + c2[0]) * 0.5
    dr = c1[0] - c2[0]
    dg = c1[1] - c2[1]
    db = c1[2] - c2[2]
    return math.sqrt((2.0 + rmean / 256.0) * dr * dr + 4.0 * dg * dg + (2.0 + (255.0 - rmean) / 256.0) * db * db)


# =============================================================================
# Step 1: Background Detection & AI Edge De-Fading ("Tidy Up")
# =============================================================================

def detect_background_color(img: Image.Image) -> Optional[Tuple[int, int, int]]:
    """
    Auto-detect solid or near-solid background color from image corners & border pixels.
    Returns None if the image already has transparent corners.
    """
    rgba = img.convert("RGBA")
    w, h = rgba.size
    if w == 0 or h == 0:
        return None
    px = rgba.load()

    border_samples: List[Tuple[int, int, int, int]] = []
    for x in range(w):
        border_samples.append(px[x, 0])
        border_samples.append(px[x, h - 1])
    for y in range(1, h - 1):
        border_samples.append(px[0, y])
        border_samples.append(px[w - 1, y])

    transparent_count = sum(1 for r, g, b, a in border_samples if a < 32)
    if transparent_count > len(border_samples) * 0.4:
        return None

    # Quantize RGB slightly (to 4-pixel steps) to find dominant background cluster
    opaque_rgb = [((r >> 2) << 2, (g >> 2) << 2, (b >> 2) << 2) for r, g, b, a in border_samples if a >= 32]
    if not opaque_rgb:
        return None
    most_common, _ = Counter(opaque_rgb).most_common(1)[0]
    return most_common


def detect_and_strip_background(
    img: Image.Image,
    bg_tolerance: float = 38.0,
    alpha_cutoff: int = 128,
    defade_strength: float = 0.65,
    bg_color: Optional[Tuple[int, int, int]] = None,
    auto_crop: bool = True,
) -> Image.Image:
    """
    Clean an AI-generated or pasted sprite image:
    1. Flood-fills from image borders (and removes interior islands within `bg_tolerance`)
       to convert solid/gradient AI backgrounds into true alpha=0 transparency.
    2. Strips faded/anti-aliased edge halos (`defade_strength` 0.0..1.0):
       - Pixels with alpha < `alpha_cutoff` become fully transparent (0, 0, 0, 0).
       - Opaque boundary pixels that are color-blended between the background color and
         an interior sprite color are either eroded if mostly background or snapped to
         the nearest clean interior pixel color so no dark/light halo ring remains!
    3. Optionally crops excess empty border margins while preserving aspect alignment.
    """
    rgba = img.convert("RGBA")
    w, h = rgba.size
    if w == 0 or h == 0:
        return rgba

    det_bg = bg_color if bg_color is not None else detect_background_color(rgba)
    px = rgba.load()

    # 1. Border flood-fill background removal when a background color is detected
    if det_bg is not None and bg_tolerance > 0:
        visited = [[False] * w for _ in range(h)]
        queue: deque[Tuple[int, int]] = deque()
        for x in range(w):
            queue.append((x, 0))
            queue.append((x, h - 1))
        for y in range(h):
            queue.append((0, y))
            queue.append((w - 1, y))

        while queue:
            cx, cy = queue.popleft()
            if not (0 <= cx < w and 0 <= cy < h) or visited[cy][cx]:
                continue
            visited[cy][cx] = True
            r, g, b, a = px[cx, cy]
            if a < alpha_cutoff or rgb_distance((r, g, b), det_bg) <= bg_tolerance * 1.4:
                px[cx, cy] = (0, 0, 0, 0)
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < w and 0 <= ny < h and not visited[ny][nx]:
                        queue.append((nx, ny))

    # 2. Hard alpha cutoff (removes semi-transparent AI glow/shadow fades)
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < alpha_cutoff:
                px[x, y] = (0, 0, 0, 0)
            else:
                px[x, y] = (r, g, b, 255)

    # 3. De-fading edge halo sharpener:
    # Identify opaque pixels adjacent to transparent pixels. If they are blended toward
    # `det_bg` or significantly faded compared to interior pixels (distance >= 2 from edge),
    # either strip them (if very close to bg) or snap their RGB to the nearest interior pixel!
    if defade_strength > 0.05 and w >= 4 and h >= 4:
        is_opaque = [[px[x, y][3] > 0 for x in range(w)] for y in range(h)]
        is_interior = [[False] * w for _ in range(h)]
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                if is_opaque[y][x]:
                    if is_opaque[y - 1][x] and is_opaque[y + 1][x] and is_opaque[y][x - 1] and is_opaque[y][x + 1]:
                        is_interior[y][x] = True

        halo_cutoff = bg_tolerance * (1.0 + defade_strength * 1.6)
        updates: List[Tuple[int, int, Tuple[int, int, int, int]]] = []
        for y in range(h):
            for x in range(w):
                if not is_opaque[y][x] or is_interior[y][x]:
                    continue
                r, g, b, _ = px[x, y]
                # Check if this edge pixel is a faded blend with background
                if det_bg is not None and rgb_distance((r, g, b), det_bg) <= halo_cutoff:
                    updates.append((x, y, (0, 0, 0, 0)))
                    continue

                # Find nearest interior pixel within radius 3 to snap anti-aliased edge color
                best_rgb = None
                best_dist = 999999.0
                for dy in range(-3, 4):
                    for dx in range(-3, 4):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < w and 0 <= ny < h and is_interior[ny][nx]:
                            ir, ig, ib, _ = px[nx, ny]
                            spatial_d = dx * dx + dy * dy
                            if spatial_d < best_dist:
                                best_dist = spatial_d
                                best_rgb = (ir, ig, ib)
                if best_rgb is not None:
                    # Blend toward crisp interior color according to defade_strength
                    nr = int(round(r * (1.0 - defade_strength) + best_rgb[0] * defade_strength))
                    ng = int(round(g * (1.0 - defade_strength) + best_rgb[1] * defade_strength))
                    nb = int(round(b * (1.0 - defade_strength) + best_rgb[2] * defade_strength))
                    updates.append((x, y, (nr, ng, nb, 255)))

        for ux, uy, rgba_val in updates:
            px[ux, uy] = rgba_val

    if auto_crop:
        bbox = rgba.getbbox()
        if bbox:
            # Keep a tiny 1px margin if possible, or exact bounding box
            rgba = rgba.crop(bbox)

    return rgba


# =============================================================================
# Step 2: Smart Grid Downsampling (Preserving Crisp Pixel Art Edges)
# =============================================================================

def smart_grid_downsample(
    img: Image.Image,
    target_w: int,
    target_h: int,
    step_x: int = 1,
    sample_mode: str = "dominant",
    preserve_aspect: bool = True,
) -> List[List[Optional[Tuple[int, int, int]]]]:
    """
    Downsample a cleaned RGBA image into a `(target_h, target_w)` grid of `(R, G, B)` or `None` (transparent).
    If `step_x == 2` (C64 Multicolor or BBC Mode 2), samples `target_w // 2` double-wide cells and duplicates
    each pair horizontally so the grid aligns to hardware double-pixels.
    """
    rgba = img.convert("RGBA")
    src_w, src_h = rgba.size
    logical_w = max(1, target_w // step_x)
    logical_h = max(1, target_h)

    # Fit image into canvas while preserving aspect ratio if requested
    canvas = Image.new("RGBA", (src_w, src_h), (0, 0, 0, 0))
    if preserve_aspect and src_w > 0 and src_h > 0:
        target_aspect = float(target_w) / float(target_h)
        src_aspect = float(src_w) / float(src_h)
        if src_aspect > target_aspect:
            pad_h = int(round(src_w / target_aspect))
            canvas = Image.new("RGBA", (src_w, max(src_h, pad_h)), (0, 0, 0, 0))
            canvas.paste(rgba, (0, (canvas.height - src_h) // 2))
        elif src_aspect < target_aspect:
            pad_w = int(round(src_h * target_aspect))
            canvas = Image.new("RGBA", (max(src_w, pad_w), src_h), (0, 0, 0, 0))
            canvas.paste(rgba, ((canvas.width - src_w) // 2, 0))
        else:
            canvas = rgba
    else:
        canvas = rgba

    cw, ch = canvas.size
    px = canvas.load()
    grid_rgb: List[List[Optional[Tuple[int, int, int]]]] = [[None for _ in range(target_w)] for _ in range(target_h)]

    for ly in range(logical_h):
        y0 = int(ly * ch / logical_h)
        y1 = max(y0 + 1, int((ly + 1) * ch / logical_h))
        for lx in range(logical_w):
            x0 = int(lx * cw / logical_w)
            x1 = max(x0 + 1, int((lx + 1) * cw / logical_w))

            if sample_mode == "center":
                cx = min(cw - 1, (x0 + x1) // 2)
                cy = min(ch - 1, (y0 + y1) // 2)
                r, g, b, a = px[cx, cy]
                chosen = (r, g, b) if a >= 128 else None
            else:
                opaque_samples: List[Tuple[int, int, int]] = []
                total_samples = 0
                for sy in range(y0, min(ch, y1)):
                    for sx in range(x0, min(cw, x1)):
                        total_samples += 1
                        r, g, b, a = px[sx, sy]
                        if a >= 128:
                            opaque_samples.append((r, g, b))

                if not opaque_samples or len(opaque_samples) < total_samples * 0.35:
                    chosen = None
                elif sample_mode == "average":
                    n = len(opaque_samples)
                    chosen = (
                        sum(c[0] for c in opaque_samples) // n,
                        sum(c[1] for c in opaque_samples) // n,
                        sum(c[2] for c in opaque_samples) // n,
                    )
                else:  # "dominant" (quantized cluster medoid to resist edge blur)
                    buckets: Dict[Tuple[int, int, int], List[Tuple[int, int, int]]] = {}
                    for r, g, b in opaque_samples:
                        key = (r >> 3, g >> 3, b >> 3)
                        buckets.setdefault(key, []).append((r, g, b))
                    best_cluster = max(buckets.values(), key=len)
                    n = len(best_cluster)
                    chosen = (
                        sum(c[0] for c in best_cluster) // n,
                        sum(c[1] for c in best_cluster) // n,
                        sum(c[2] for c in best_cluster) // n,
                    )

            for dx in range(step_x):
                gx = lx * step_x + dx
                if gx < target_w:
                    grid_rgb[ly][gx] = chosen

    return grid_rgb


# =============================================================================
# Step 3: Perceptual CIELAB Palette Quantizer & Hardware Constraint Solver
# =============================================================================

def quantize_to_platform(
    grid_rgb: List[List[Optional[Tuple[int, int, int]]]],
    platform: str = "c64",
    mode: str = "multicolor",
    locked_slots: Optional[List[Optional[int]]] = None,
    frame_name: str = "imported_0",
) -> MultiPlatformSpriteFrame:
    """
    Convert a `(height, width)` grid of RGB tuples into a legal `MultiPlatformSpriteFrame`
    by solving the target hardware's palette and cell constraints in perceptual CIELAB space.
    """
    height = len(grid_rgb)
    width = len(grid_rgb[0]) if height > 0 else 24
    pal = get_platform_palette(platform)
    pal_rgb = [hex_to_rgb(c["hex"]) for c in pal]
    pal_lab = [rgb_to_lab(*rgb) for rgb in pal_rgb]

    def nearest_palette_id(rgb: Tuple[int, int, int], allowed_ids: Optional[Sequence[int]] = None) -> int:
        lab = rgb_to_lab(*rgb)
        candidates = allowed_ids if allowed_ids is not None else range(len(pal))
        best_id = 0
        best_d = 1e9
        for cid in candidates:
            if platform == "zx_next" and mode == "next_8bit" and cid == 0xE3:
                continue  # Reserve $E3 for transparent
            d = delta_e_lab(lab, pal_lab[cid])
            if d < best_d:
                best_d = d
                best_id = cid
        return best_id

    # Map every opaque pixel to its unconstrained nearest hardware palette ID first
    raw_cids: List[List[Optional[int]]] = [[None for _ in range(width)] for _ in range(height)]
    cid_counts: Counter[int] = Counter()
    for y in range(height):
        for x in range(width):
            rgb = grid_rgb[y][x]
            if rgb is not None:
                cid = nearest_palette_id(rgb)
                raw_cids[y][x] = cid
                cid_counts[cid] += 1

    frame = MultiPlatformSpriteFrame(
        platform=platform,
        mode=mode,
        width=width,
        height=height,
        name=frame_name,
    )

    bg_id = locked_slots[0] if (locked_slots and locked_slots[0] is not None) else 0

    # --- Platform Case A: C64 (Hires, Multicolor, Overlay) ---
    if platform == "c64":
        if mode == "hires":
            # 1 opaque color (slot 2 / slot 1)
            if locked_slots and len(locked_slots) > 2 and locked_slots[2] is not None:
                main_cid = int(locked_slots[2])
            else:
                non_bg = [cid for cid, _ in cid_counts.most_common() if cid != bg_id]
                main_cid = non_bg[0] if non_bg else 1
            frame.color_slots = [bg_id, 2, main_cid, 6, 1]
            for y in range(height):
                for x in range(width):
                    frame.grid[y][x] = 1 if grid_rgb[y][x] is not None else 0
            return frame

        # Multicolor (3 opaque slots: 1=MC1, 2=Sprite, 3=MC2) or Overlay (+ slot 4=Hires outline)
        num_opaque_slots = 4 if mode == "overlay" else 3
        chosen_cids: List[int] = []
        if locked_slots:
            for s_idx in range(1, num_opaque_slots + 1):
                if s_idx < len(locked_slots) and locked_slots[s_idx] is not None:
                    chosen_cids.append(int(locked_slots[s_idx]))

        for cid, _ in cid_counts.most_common():
            if cid not in chosen_cids and len(chosen_cids) < num_opaque_slots:
                chosen_cids.append(cid)

        defaults = [2, 15, 6, 1]
        for d_cid in defaults:
            if len(chosen_cids) < num_opaque_slots and d_cid not in chosen_cids:
                chosen_cids.append(d_cid)
        while len(chosen_cids) < 4:
            chosen_cids.append(1)

        frame.color_slots = [bg_id] + chosen_cids[:4]
        active_cids = frame.color_slots[1 : num_opaque_slots + 1]

        for y in range(height):
            for x in range(width):
                rgb = grid_rgb[y][x]
                if rgb is None:
                    frame.grid[y][x] = 0
                else:
                    best_cid = nearest_palette_id(rgb, allowed_ids=active_cids)
                    slot_idx = active_cids.index(best_cid) + 1
                    frame.set_pixel(x, y, slot_idx)
        return frame

    # --- Platform Case B: ZX Spectrum (attr_8x8 or mono_mask) ---
    if platform == "zx_spectrum":
        if mode == "mono_mask":
            top_cid = cid_counts.most_common(1)[0][0] if cid_counts else 15
            frame.color_slots = [0, top_cid]
            for y in range(height):
                for x in range(width):
                    frame.grid[y][x] = 1 if grid_rgb[y][x] is not None else 0
            return frame

        # attr_8x8: 16 slots = 16 ULA colors, enforce 2 colors + 1 BRIGHT state per 8x8 cell
        frame.color_slots = list(range(16))
        cells_x = (width + 7) // 8
        cells_y = (height + 7) // 8
        for cy in range(cells_y):
            for cx in range(cells_x):
                cell_counts: Counter[int] = Counter()
                for dy in range(8):
                    for dx in range(8):
                        px_x, px_y = cx * 8 + dx, cy * 8 + dy
                        if px_x < width and px_y < height and raw_cids[px_y][px_x] is not None:
                            cell_counts[raw_cids[px_y][px_x]] += 1

                if not cell_counts:
                    frame.zx_attributes[f"{cx},{cy}"] = {"ink": 7, "paper": 0, "bright": 1}
                    continue

                # Determine whether Normal (0..7) or Bright (8..15) minimizes error in this 8x8 cell
                top_cid = cell_counts.most_common(1)[0][0]
                bright_flag = 1 if top_cid >= 8 else 0
                bank_ids = list(range(8, 16)) if bright_flag else list(range(0, 8))

                # Pick up to 2 colors in this brightness bank for this 8x8 block
                bank_counts: Counter[int] = Counter()
                for dy in range(8):
                    for dx in range(8):
                        px_x, px_y = cx * 8 + dx, cy * 8 + dy
                        if px_x < width and px_y < height and grid_rgb[px_y][px_x] is not None:
                            bcid = nearest_palette_id(grid_rgb[px_y][px_x], allowed_ids=bank_ids)
                            bank_counts[bcid] += 1

                top_two = [cid for cid, _ in bank_counts.most_common(2)]
                ink_cid = top_two[0] if top_two else (15 if bright_flag else 7)
                paper_cid = top_two[1] if len(top_two) > 1 else (8 if bright_flag else 0)
                allowed_cell = [ink_cid, paper_cid] if len(top_two) > 1 else [ink_cid]

                frame.zx_attributes[f"{cx},{cy}"] = {
                    "ink": ZX_SPECTRUM_PALETTE[ink_cid]["ink"],
                    "paper": ZX_SPECTRUM_PALETTE[paper_cid]["ink"],
                    "bright": bright_flag,
                }

                for dy in range(8):
                    for dx in range(8):
                        px_x, px_y = cx * 8 + dx, cy * 8 + dy
                        if px_x < width and px_y < height:
                            rgb = grid_rgb[px_y][px_x]
                            if rgb is None:
                                frame.grid[px_y][px_x] = 0
                            else:
                                chosen = nearest_palette_id(rgb, allowed_ids=allowed_cell)
                                frame.grid[px_y][px_x] = chosen if chosen > 0 else 8
        return frame

    # --- Platform Case C: ZX Spectrum Next (next_8bit or next_4bit) ---
    if platform == "zx_next":
        if mode == "next_4bit":
            # 15 opaque colors + slot 0 transparent
            top_15 = [cid for cid, _ in cid_counts.most_common(15) if cid != 0xE3]
            while len(top_15) < 15:
                for fallback in (0xFF, 0xE0, 0x1C, 0x03, 0xFC, 0x1F, 0x92, 0x49):
                    if fallback not in top_15 and len(top_15) < 15:
                        top_15.append(fallback)
                break
            frame.color_slots = [0xE3] + top_15[:15]
            active_cids = frame.color_slots[1:]
            for y in range(height):
                for x in range(width):
                    rgb = grid_rgb[y][x]
                    if rgb is None:
                        frame.grid[y][x] = 0
                    else:
                        best_cid = nearest_palette_id(rgb, allowed_ids=active_cids)
                        frame.grid[y][x] = active_cids.index(best_cid) + 1
            return frame

        # next_8bit: 256 colors available! Populate color_slots with top colors for quick brush access,
        # and store either slot index or direct palette index.
        top_slots = [cid for cid, _ in cid_counts.most_common(15) if cid != 0xE3]
        for fallback in (0xFF, 0xE0, 0x1C, 0x03, 0xFC, 0x1F, 0x00):
            if fallback not in top_slots and len(top_slots) < 15:
                top_slots.append(fallback)
        # In next_8bit, make color_slots 256 entries so slot N == Next palette ID N (with slot 0 = $E3 transparent)
        frame.color_slots = [0xE3] + [i for i in range(1, 256)]
        for y in range(height):
            for x in range(width):
                rgb = grid_rgb[y][x]
                if rgb is None:
                    frame.grid[y][x] = 0
                else:
                    cid = nearest_palette_id(rgb)
                    frame.grid[y][x] = cid if cid > 0 else 1
        return frame

    # --- Platform Case D: BBC Micro (mode2, mode1, mode4) ---
    if platform == "bbc_micro":
        if mode == "mode2":
            # All 8 BBC colors available, double-wide pixels (step_x=2)
            frame.color_slots = [0, 1, 2, 3, 4, 5, 6, 7]
            for y in range(height):
                for x in range(0, width, 2):
                    rgb = grid_rgb[y][x]
                    if rgb is None:
                        frame.set_pixel(x, y, 0)
                    else:
                        cid = nearest_palette_id(rgb)
                        # If nearest is 0 (Black) on an opaque pixel, map to slot 1..7 or keep 1
                        slot_val = cid if cid > 0 else 7
                        frame.set_pixel(x, y, slot_val)
            return frame

        if mode == "mode1":
            # 4 colors total: slot 0 = transparent/bg, slots 1..3 = 3 selectable physical BBC colors
            chosen_bbc: List[int] = []
            if locked_slots:
                for s_idx in range(1, 4):
                    if s_idx < len(locked_slots) and locked_slots[s_idx] is not None:
                        chosen_bbc.append(int(locked_slots[s_idx]) & 7)
            for cid, _ in cid_counts.most_common():
                if cid not in chosen_bbc and len(chosen_bbc) < 3 and cid != bg_id:
                    chosen_bbc.append(cid)
            for d_cid in (1, 3, 7, 6, 2):
                if len(chosen_bbc) < 3 and d_cid not in chosen_bbc:
                    chosen_bbc.append(d_cid)
            frame.color_slots = [bg_id & 7] + chosen_bbc[:3]
            active_cids = frame.color_slots[1:4]
            for y in range(height):
                for x in range(width):
                    rgb = grid_rgb[y][x]
                    if rgb is None:
                        frame.grid[y][x] = 0
                    else:
                        best_cid = nearest_palette_id(rgb, allowed_ids=active_cids)
                        frame.grid[y][x] = active_cids.index(best_cid) + 1
            return frame

        # mode4: 1bpp (slot 0 = bg, slot 1 = foreground)
        fg_cid = cid_counts.most_common(1)[0][0] if cid_counts else 7
        if fg_cid == bg_id:
            fg_cid = 7 if bg_id != 7 else 3
        frame.color_slots = [bg_id & 7, fg_cid & 7]
        for y in range(height):
            for x in range(width):
                frame.grid[y][x] = 1 if grid_rgb[y][x] is not None else 0
        return frame

    return frame


# =============================================================================
# Step 4: Sprite Sheet Slicer (Grid & Connected-Island Auto-Detector)
# =============================================================================

def slice_sprite_sheet(
    img: Image.Image,
    rows: int = 1,
    cols: int = 1,
    auto_detect_islands: bool = False,
) -> List[Image.Image]:
    """
    Slice a sprite sheet into individual frame images.
    - If `auto_detect_islands=True`, finds non-empty connected bounding boxes (ordered left-to-right, top-to-bottom).
    - Otherwise slices uniformly into `rows x cols` cells.
    """
    rgba = img.convert("RGBA")
    w, h = rgba.size
    if not auto_detect_islands and rows <= 1 and cols <= 1:
        return [rgba]

    if auto_detect_islands:
        px = rgba.load()
        visited = [[False] * w for _ in range(h)]
        boxes: List[Tuple[int, int, int, int]] = []
        for y in range(h):
            for x in range(w):
                if not visited[y][x] and px[x, y][3] >= 64:
                    q: deque[Tuple[int, int]] = deque([(x, y)])
                    visited[y][x] = True
                    min_x = max_x = x
                    min_y = max_y = y
                    while q:
                        cx, cy = q.popleft()
                        min_x = min(min_x, cx)
                        max_x = max(max_x, cx)
                        min_y = min(min_y, cy)
                        max_y = max(max_y, cy)
                        for dx in (-2, -1, 0, 1, 2):
                            for dy in (-2, -1, 0, 1, 2):
                                nx, ny = cx + dx, cy + dy
                                if 0 <= nx < w and 0 <= ny < h and not visited[ny][nx] and px[nx, ny][3] >= 64:
                                    visited[ny][nx] = True
                                    q.append((nx, ny))
                    if (max_x - min_x + 1) >= 4 and (max_y - min_y + 1) >= 4:
                        boxes.append((min_x, min_y, max_x + 1, max_y + 1))

        if boxes:
            # Sort into rows then left-to-right
            avg_h = sum(b[3] - b[1] for b in boxes) / len(boxes)
            boxes.sort(key=lambda b: (int(b[1] // max(8.0, avg_h * 0.6)), b[0]))
            return [rgba.crop(b) for b in boxes]

    # Uniform grid slice
    rows = max(1, rows)
    cols = max(1, cols)
    cell_w = max(1, w // cols)
    cell_h = max(1, h // rows)
    slices: List[Image.Image] = []
    for r in range(rows):
        for c in range(cols):
            box = (c * cell_w, r * cell_h, min(w, (c + 1) * cell_w), min(h, (r + 1) * cell_h))
            crop = rgba.crop(box)
            if crop.getbbox() is not None:
                slices.append(crop)
    return slices if slices else [rgba]


# =============================================================================
# High-Level End-to-End Image Import Pipeline
# =============================================================================

def import_image_to_frames(
    image_bytes_or_b64: bytes | str,
    platform: str = "c64",
    mode: str = "multicolor",
    target_w: int = 24,
    target_h: int = 21,
    bg_tolerance: float = 38.0,
    alpha_cutoff: int = 128,
    defade_strength: float = 0.65,
    sample_mode: str = "dominant",
    preserve_aspect: bool = True,
    auto_crop: bool = True,
    sheet_rows: int = 1,
    sheet_cols: int = 1,
    auto_detect_islands: bool = False,
    locked_slots: Optional[List[Optional[int]]] = None,
) -> List[MultiPlatformSpriteFrame]:
    """
    Full pipeline: decode image -> strip background & AI edge halos -> slice sprite sheet ->
    smart downsample -> CIELAB hardware palette quantize into `MultiPlatformSpriteFrame` list.
    """
    if isinstance(image_bytes_or_b64, str):
        b64_str = image_bytes_or_b64
        if "," in b64_str:
            b64_str = b64_str.split(",", 1)[1]
        raw_bytes = base64.b64decode(b64_str)
    else:
        raw_bytes = image_bytes_or_b64

    img = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")

    # Clean background before slicing so island detection works on solid-background sprite sheets
    cleaned_full = detect_and_strip_background(
        img,
        bg_tolerance=bg_tolerance,
        alpha_cutoff=alpha_cutoff,
        defade_strength=defade_strength,
        auto_crop=(auto_crop and sheet_rows == 1 and sheet_cols == 1 and not auto_detect_islands),
    )

    slices = slice_sprite_sheet(
        cleaned_full,
        rows=sheet_rows,
        cols=sheet_cols,
        auto_detect_islands=auto_detect_islands,
    )

    step_x = 2 if (
        (platform == "c64" and mode == "multicolor")
        or (platform == "bbc_micro" and mode == "mode2")
    ) else 1

    frames: List[MultiPlatformSpriteFrame] = []
    shared_slots: Optional[List[Optional[int]]] = locked_slots

    for idx, sl in enumerate(slices):
        if auto_crop:
            bbox = sl.getbbox()
            if bbox:
                sl = sl.crop(bbox)
        grid_rgb = smart_grid_downsample(
            sl,
            target_w=target_w,
            target_h=target_h,
            step_x=step_x,
            sample_mode=sample_mode,
            preserve_aspect=preserve_aspect,
        )
        frame = quantize_to_platform(
            grid_rgb,
            platform=platform,
            mode=mode,
            locked_slots=shared_slots,
            frame_name=f"frame_{idx}",
        )
        # Lock palette slots from Frame 0 across subsequent frames of the same sheet for consistency
        if idx == 0 and shared_slots is None and platform in ("c64", "bbc_micro"):
            shared_slots = [int(c) for c in frame.color_slots]
        frames.append(frame)

    return frames

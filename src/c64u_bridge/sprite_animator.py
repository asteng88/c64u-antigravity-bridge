"""
Smooth Sprite Animation Generator:
1. Deterministic Pixel-Art Keyframe Tweening (Scanline Span + Centroid Correspondence Morphing)
2. Single-Sprite Procedural Motion Cycle Presets:
   - `walk_cycle`: Split-body stride with leg swing, foot lift, and torso bob
   - `hover_bob`: Vertical hover oscillation + thruster/rotor/highlight slot phase cycling
   - `rotate_bank`: Clean pixel-art banking tilt / directional rotation
   - `pulse_breathe`: Breathing chest/silhouette expansion + energy pulse
   - `explode_dissolve`: Radial velocity scatter + heat-palette progression
3. AI-Powered Frame Synthesis (via Gemini API when `GEMINI_API_KEY` is configured,
   automatically piped through De-Fading + CIELAB Hardware Palette Quantization).
"""

from __future__ import annotations

import io
import math
import os
import urllib.error
import urllib.request
import json
from typing import Any, Dict, List, Optional, Tuple

from .sprite import MultiPlatformSpriteFrame
from .sprite_import import import_image_to_frames


# =============================================================================
# Helper: Bounding Box & Pixel Point Correspondence
# =============================================================================

def _get_bbox(frame: MultiPlatformSpriteFrame) -> Tuple[int, int, int, int]:
    """Return (min_x, min_y, max_x, max_y) of non-zero pixels, or center box if empty."""
    min_x, min_y = frame.width, frame.height
    max_x, max_y = -1, -1
    for y in range(frame.height):
        for x in range(frame.width):
            if frame.grid[y][x] > 0:
                min_x = min(min_x, x)
                max_x = max(max_x, x)
                min_y = min(min_y, y)
                max_y = max(max_y, y)
    if max_x < min_x:
        return (0, 0, frame.width - 1, frame.height - 1)
    return (min_x, min_y, max_x, max_y)


def _extract_spans_by_row(
    frame: MultiPlatformSpriteFrame,
) -> Dict[int, List[Tuple[int, int, int]]]:
    """Extract contiguous horizontal spans `(x_start, x_end, color_val)` per row."""
    spans_by_row: Dict[int, List[Tuple[int, int, int]]] = {}
    for y in range(frame.height):
        row = frame.grid[y]
        spans: List[Tuple[int, int, int]] = []
        x = 0
        while x < frame.width:
            v = row[x]
            if v == 0:
                x += 1
                continue
            x0 = x
            while x < frame.width and row[x] == v:
                x += 1
            spans.append((x0, x - 1, v))
        if spans:
            spans_by_row[y] = spans
    return spans_by_row


# =============================================================================
# 1. Keyframe In-Betweening (Pixel-Pure Morphing Tween)
# =============================================================================

def tween_keyframes(
    frame_a: MultiPlatformSpriteFrame,
    frame_b: MultiPlatformSpriteFrame,
    num_inbetweens: int = 2,
) -> List[MultiPlatformSpriteFrame]:
    """
    Generate `num_inbetweens` smooth intermediate frames between `frame_a` and `frame_b`.
    Uses a hybrid of:
    - Per-color sorted pixel-cloud optimal transport (preserves pixel counts & color identity)
    - Scanline span interpolation (prevents Swiss-cheese gaps inside solid regions)
    Strictly respects hardware `step_x` (2 for C64 Multicolor / BBC Mode 2, 1 otherwise).
    """
    num_inbetweens = max(1, min(16, int(num_inbetweens)))
    w, h = frame_a.width, frame_a.height
    step_x = frame_a.step_x

    # Collect logical pixel coordinates (lx, y) grouped by color slot value
    def collect_by_color(f: MultiPlatformSpriteFrame) -> Dict[int, List[Tuple[int, int]]]:
        by_col: Dict[int, List[Tuple[int, int]]] = {}
        for y in range(h):
            for x in range(0, w, step_x):
                v = f.get_pixel(x, y)
                if v > 0:
                    by_col.setdefault(v, []).append((x // step_x, y))
        return by_col

    col_a = collect_by_color(frame_a)
    col_b = collect_by_color(frame_b)
    all_colors = sorted(set(col_a.keys()) | set(col_b.keys()))

    # Also collect all opaque points regardless of color as fallback when a color only exists in one frame
    all_pts_a = [(x // step_x, y, frame_a.get_pixel(x, y)) for y in range(h) for x in range(0, w, step_x) if frame_a.get_pixel(x, y) > 0]
    all_pts_b = [(x // step_x, y, frame_b.get_pixel(x, y)) for y in range(h) for x in range(0, w, step_x) if frame_b.get_pixel(x, y) > 0]

    inbetweens: List[MultiPlatformSpriteFrame] = []

    for i in range(1, num_inbetweens + 1):
        t = float(i) / float(num_inbetweens + 1)
        out = frame_a.clone(new_name=f"{frame_a.name}_tween_{i}")
        out.grid = [[0 for _ in range(w)] for _ in range(h)]

        # 1. Scanline span interpolation for solid silhouette continuity
        bbox_a = _get_bbox(frame_a)
        bbox_b = _get_bbox(frame_b)
        min_ya, max_ya = bbox_a[1], bbox_a[3]
        min_yb, max_yb = bbox_b[1], bbox_b[3]
        ha = max(1, max_ya - min_ya + 1)
        hb = max(1, max_yb - min_yb + 1)

        min_yt = int(round((1.0 - t) * min_ya + t * min_yb))
        max_yt = int(round((1.0 - t) * max_ya + t * max_yb))
        ht = max(1, max_yt - min_yt + 1)

        for yt in range(max(0, min_yt), min(h, max_yt + 1)):
            rel_y = (yt - min_yt) / float(max(1, ht - 1)) if ht > 1 else 0.0
            ya = min(h - 1, max(0, int(round(min_ya + rel_y * (ha - 1)))))
            yb = min(h - 1, max(0, int(round(min_yb + rel_y * (hb - 1)))))

            row_a = [frame_a.get_pixel(x, ya) for x in range(0, w, step_x)]
            row_b = [frame_b.get_pixel(x, yb) for x in range(0, w, step_x)]
            nz_a = [idx for idx, v in enumerate(row_a) if v > 0]
            nz_b = [idx for idx, v in enumerate(row_b) if v > 0]

            if nz_a and nz_b:
                left_t = int(round((1.0 - t) * nz_a[0] + t * nz_b[0]))
                right_t = int(round((1.0 - t) * nz_a[-1] + t * nz_b[-1]))
                span_t = max(1, right_t - left_t + 1)
                span_a = max(1, nz_a[-1] - nz_a[0] + 1)
                span_b = max(1, nz_b[-1] - nz_b[0] + 1)
                for k in range(span_t):
                    lx = left_t + k
                    if 0 <= lx < (w // step_x):
                        u = k / float(max(1, span_t - 1)) if span_t > 1 else 0.0
                        lxa = min(len(row_a) - 1, max(0, int(round(nz_a[0] + u * (span_a - 1)))))
                        lxb = min(len(row_b) - 1, max(0, int(round(nz_b[0] + u * (span_b - 1)))))
                        va = row_a[lxa]
                        vb = row_b[lxb]
                        if va > 0 and vb > 0:
                            val = va if t < 0.5 else vb
                            out.set_pixel(lx * step_x, yt, val)

        # 2. Per-color point-cloud correspondence to preserve detailed features (eyes, weapons, rotors)
        for col_val in all_colors:
            pts_a = col_a.get(col_val, [])
            pts_b = col_b.get(col_val, [])
            if not pts_a and not pts_b:
                continue
            if not pts_a:
                pts_a = [(px, py) for px, py, _ in all_pts_a] if all_pts_a else pts_b
            if not pts_b:
                pts_b = [(px, py) for px, py, _ in all_pts_b] if all_pts_b else pts_a

            # Sort both clouds spatially (by y then x) and match quantiles
            pts_a_sorted = sorted(pts_a, key=lambda p: (p[1], p[0]))
            pts_b_sorted = sorted(pts_b, key=lambda p: (p[1], p[0]))
            target_count = int(round((1.0 - t) * len(pts_a_sorted) + t * len(pts_b_sorted)))
            if target_count <= 0:
                continue

            for k in range(target_count):
                u = (k + 0.5) / float(target_count)
                ia = min(len(pts_a_sorted) - 1, int(u * len(pts_a_sorted)))
                ib = min(len(pts_b_sorted) - 1, int(u * len(pts_b_sorted)))
                xa, ya = pts_a_sorted[ia]
                xb, yb = pts_b_sorted[ib]
                xt = int(round((1.0 - t) * xa + t * xb))
                yt = int(round((1.0 - t) * ya + t * yb))
                if 0 <= xt * step_x < w and 0 <= yt < h:
                    out.set_pixel(xt * step_x, yt, col_val)

        inbetweens.append(out)

    return inbetweens


# =============================================================================
# 2. Single-Sprite Procedural Motion Cycle Generators
# =============================================================================

def generate_motion_cycle(
    base_frame: MultiPlatformSpriteFrame,
    preset: str = "walk_cycle",
    num_frames: int = 4,
    intensity: float = 1.0,
) -> List[MultiPlatformSpriteFrame]:
    """
    Generate a complete smooth multi-frame animation sequence from a single static sprite frame.
    Supported presets:
    - `walk_cycle`: Character/mech walk stride with upper-body bob and alternating lower-limb swing
    - `hover_bob`: Vehicle/spaceship/character hover bob + rotor/thruster color phase animation
    - `rotate_bank`: Banking left/right roll or 8-way directional rotation
    - `pulse_breathe`: Idle breathing silhouette expansion/contraction + highlight cycling
    - `explode_dissolve`: Multi-frame radial shatter/explosion sequence
    """
    num_frames = max(2, min(16, int(num_frames)))
    preset = preset.lower().strip()

    if preset == "walk_cycle":
        return _gen_walk_cycle(base_frame, num_frames, intensity)
    if preset == "hover_bob":
        return _gen_hover_bob(base_frame, num_frames, intensity)
    if preset == "rotate_bank":
        return _gen_rotate_bank(base_frame, num_frames, intensity)
    if preset == "pulse_breathe":
        return _gen_pulse_breathe(base_frame, num_frames, intensity)
    if preset == "explode_dissolve":
        return _gen_explode_dissolve(base_frame, num_frames, intensity)
    return _gen_hover_bob(base_frame, num_frames, intensity)


def _gen_walk_cycle(
    base: MultiPlatformSpriteFrame,
    num_frames: int,
    intensity: float,
) -> List[MultiPlatformSpriteFrame]:
    w, h = base.width, base.height
    step_x = base.step_x
    min_x, min_y, max_x, max_y = _get_bbox(base)
    body_h = max(1, max_y - min_y + 1)
    hip_y = min_y + int(body_h * 0.60)
    mid_x = (min_x + max_x) // 2

    frames: List[MultiPlatformSpriteFrame] = []
    for f_idx in range(num_frames):
        phase = (2.0 * math.pi * f_idx) / float(num_frames)
        sin_p = math.sin(phase)
        cos_p = math.cos(phase)

        frame = base.clone(new_name=f"{base.name}_walk_{f_idx}")
        frame.grid = [[0 for _ in range(w)] for _ in range(h)]

        # Upper body bobs down at peak stride (2 cycles per full walk loop)
        torso_dy = -1 if abs(sin_p) > 0.65 and min_y > 0 else 0
        arm_dx = int(round(sin_p * intensity)) * step_x

        for y in range(h):
            for x in range(0, w, step_x):
                v = base.get_pixel(x, y)
                if v <= 0:
                    continue
                if y < hip_y:
                    # Upper torso & head
                    is_arm_band = (min_y + int(body_h * 0.28)) <= y < hip_y and abs(x - mid_x) > (max_x - min_x) * 0.25
                    nx = x + (arm_dx if (is_arm_band and x < mid_x) else (-arm_dx if is_arm_band else 0))
                    ny = y + torso_dy
                else:
                    # Lower legs / treads: left and right sides swing in opposite phase
                    leg_rel = (y - hip_y + 1) / float(max(1, max_y - hip_y + 1))
                    is_left_leg = x < mid_x
                    leg_phase = sin_p if is_left_leg else -sin_p
                    leg_lift = -1 if (cos_p > 0.45 if is_left_leg else -cos_p > 0.45) else 0
                    dx_units = int(round(leg_phase * leg_rel * 1.4 * intensity))
                    nx = x + dx_units * step_x
                    ny = y + leg_lift

                if 0 <= nx < w and 0 <= ny < h:
                    frame.set_pixel(nx, ny, v)
        frames.append(frame)
    return frames


def _gen_hover_bob(
    base: MultiPlatformSpriteFrame,
    num_frames: int,
    intensity: float,
) -> List[MultiPlatformSpriteFrame]:
    w, h = base.width, base.height
    step_x = base.step_x
    min_x, min_y, max_x, max_y = _get_bbox(base)
    frames: List[MultiPlatformSpriteFrame] = []

    for f_idx in range(num_frames):
        phase = (2.0 * math.pi * f_idx) / float(num_frames)
        dy = int(round(math.sin(phase) * max(1.0, intensity)))
        # Clamp dy so sprite doesn't clip off top/bottom if avoidable
        if min_y + dy < 0:
            dy = -min_y
        elif max_y + dy >= h:
            dy = (h - 1) - max_y

        frame = base.clone(new_name=f"{base.name}_hover_{f_idx}")
        frame.grid = [[0 for _ in range(w)] for _ in range(h)]

        for y in range(h):
            for x in range(0, w, step_x):
                v = base.get_pixel(x, y)
                if v <= 0:
                    continue
                ny = y + dy
                # Subtle rotor/thruster/tread shimmer on top/bottom rows or secondary color slots
                nv = v
                if base.mode in ("multicolor", "overlay", "mode1", "mode2") and v in (1, 3):
                    if ((x // step_x) + y + f_idx) % 3 == 0 and (y <= min_y + 2 or y >= max_y - 2):
                        nv = 3 if v == 1 else 1
                if 0 <= ny < h:
                    frame.set_pixel(x, ny, nv)
        frames.append(frame)
    return frames


def _gen_rotate_bank(
    base: MultiPlatformSpriteFrame,
    num_frames: int,
    intensity: float,
) -> List[MultiPlatformSpriteFrame]:
    """
    Generate smooth banking/rolling or rotational frames around the sprite's centroid
    using area-preserving double-shear transformation so pixels never develop holes.
    """
    w, h = base.width, base.height
    step_x = base.step_x
    min_x, min_y, max_x, max_y = _get_bbox(base)
    cx = ((min_x + max_x) / 2.0) / step_x
    cy = (min_y + max_y) / 2.0
    lw = w // step_x

    frames: List[MultiPlatformSpriteFrame] = []
    max_angle = min(0.75, 0.45 * intensity)  # ~25-40 deg banking roll wave

    for f_idx in range(num_frames):
        phase = (2.0 * math.pi * f_idx) / float(num_frames)
        angle = math.sin(phase) * max_angle
        scale_x = max(0.60, math.cos(angle * 1.25))
        shear_y = math.sin(angle) * 0.65

        frame = base.clone(new_name=f"{base.name}_bank_{f_idx}")
        frame.grid = [[0 for _ in range(w)] for _ in range(h)]

        # Inverse-map each target logical pixel (tx, ty) to source (sx, sy) for hole-free rendering
        for ty in range(h):
            for tx in range(lw):
                dx = (tx - cx) / scale_x
                dy = (ty - cy) - dx * shear_y
                sx = int(round(cx + dx))
                sy = int(round(cy + dy))
                if 0 <= sx < lw and 0 <= sy < h:
                    v = base.get_pixel(sx * step_x, sy)
                    if v > 0:
                        frame.set_pixel(tx * step_x, ty, v)
        frames.append(frame)
    return frames


def _gen_pulse_breathe(
    base: MultiPlatformSpriteFrame,
    num_frames: int,
    intensity: float,
) -> List[MultiPlatformSpriteFrame]:
    w, h = base.width, base.height
    step_x = base.step_x
    lw = w // step_x
    min_x, min_y, max_x, max_y = _get_bbox(base)
    cx = ((min_x + max_x) / 2.0) / step_x
    cy = (min_y + max_y) / 2.0

    frames: List[MultiPlatformSpriteFrame] = []
    for f_idx in range(num_frames):
        phase = (2.0 * math.pi * f_idx) / float(num_frames)
        swell = 1.0 + 0.28 * math.sin(phase) * intensity

        frame = base.clone(new_name=f"{base.name}_pulse_{f_idx}")
        frame.grid = [[0 for _ in range(w)] for _ in range(h)]

        for ty in range(h):
            for tx in range(lw):
                sx = int(round(cx + (tx - cx) / swell))
                sy = int(round(cy + (ty - cy) / (1.0 + (swell - 1.0) * 0.6)))
                if 0 <= sx < lw and 0 <= sy < h:
                    v = base.get_pixel(sx * step_x, sy)
                    if v > 0:
                        frame.set_pixel(tx * step_x, ty, v)
        frames.append(frame)
    return frames


def _gen_explode_dissolve(
    base: MultiPlatformSpriteFrame,
    num_frames: int,
    intensity: float,
) -> List[MultiPlatformSpriteFrame]:
    w, h = base.width, base.height
    step_x = base.step_x
    lw = w // step_x
    min_x, min_y, max_x, max_y = _get_bbox(base)
    cx = ((min_x + max_x) / 2.0) / step_x
    cy = (min_y + max_y) / 2.0

    frames: List[MultiPlatformSpriteFrame] = []
    for f_idx in range(num_frames):
        t = float(f_idx) / float(max(1, num_frames - 1))
        frame = base.clone(new_name=f"{base.name}_explode_{f_idx}")
        frame.grid = [[0 for _ in range(w)] for _ in range(h)]

        if f_idx == 0:
            frame.grid = [list(r) for r in base.grid]
            frames.append(frame)
            continue

        for sy in range(h):
            for sx in range(lw):
                v = base.get_pixel(sx * step_x, sy)
                if v <= 0:
                    continue
                # Deterministic pseudo-random velocity & survival per pixel
                h_seed = ((sx * 73856093) ^ (sy * 19349663) ^ (f_idx * 83492791)) & 0xFFFF
                rnd = h_seed / 65535.0
                if rnd < t * 0.68:
                    continue  # Dissolved particle

                vx = (sx - cx) * (1.0 + t * 1.8 * intensity) + ((h_seed & 3) - 1.5) * t * 1.5
                vy = (sy - cy) * (1.0 + t * 1.8 * intensity) + (((h_seed >> 2) & 3) - 1.0) * t * 1.5
                tx = int(round(cx + vx))
                ty = int(round(cy + vy))
                if 0 <= tx < lw and 0 <= ty < h:
                    # Cycle color slots toward fire/sparks on later frames if multiple slots exist
                    nv = v
                    if base.mode in ("multicolor", "overlay", "mode1", "mode2") and t > 0.45:
                        nv = 1 if (tx + ty + f_idx) % 2 == 0 else 3
                    frame.set_pixel(tx * step_x, ty, nv)
        frames.append(frame)
    return frames


# =============================================================================
# 3. AI-Prompted Animation Frame Synthesis (Gemini API + Auto-Quantization)
# =============================================================================

def generate_ai_animation_frames(
    base_frame: MultiPlatformSpriteFrame,
    prompt: str,
    num_frames: int = 4,
) -> Tuple[List[MultiPlatformSpriteFrame], str]:
    """
    Generate `num_frames` animation frames for `base_frame` guided by `prompt`.
    - If `GEMINI_API_KEY` is configured in the environment or `.env`, calls the Gemini multimodal image
      generation endpoint using the current sprite as reference and automatically runs the output strip
      through `import_image_to_frames` (De-Fade + CIELAB Hardware Constraint Solver) locked to `base_frame.color_slots`.
    - If `GEMINI_API_KEY` is not available or the API call fails, intelligently selects the closest
      procedural motion generator based on the prompt keywords and returns the generated frames with a status note.
    """
    from .env import load_env
    from .sprite import SpriteAnimationProject

    load_env()
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

    if api_key:
        try:
            proj = SpriteAnimationProject(
                platform=base_frame.platform,
                mode=base_frame.mode,
                width=base_frame.width,
                height=base_frame.height,
                frames=[base_frame],
            )
            ref_img = proj.render_frame_pil(0, scale=8, transparent_bg=False)
            buf = io.BytesIO()
            ref_img.save(buf, format="PNG")
            ref_b64 = io.BytesIO(buf.getvalue())
            import base64
            b64_str = base64.b64encode(ref_b64.getvalue()).decode("ascii")

            sys_prompt = (
                f"Generate a horizontal pixel-art sprite sheet with exactly {num_frames} equally spaced frames "
                f"side-by-side on a solid black (#000000) background, continuing this retro {base_frame.platform.upper()} "
                f"sprite ({base_frame.width}x{base_frame.height} resolution) to animate: {prompt}. "
                f"Use crisp hard pixel edges with zero anti-aliasing, zero gradients, and the exact same flat palette."
            )

            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp-image-generation:generateContent?key={api_key}"
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": sys_prompt},
                            {"inlineData": {"mimeType": "image/png", "data": b64_str}},
                        ]
                    }
                ],
                "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))

            for cand in resp_data.get("candidates", []):
                for part in cand.get("content", {}).get("parts", []):
                    inline = part.get("inlineData")
                    if inline and inline.get("data"):
                        frames = import_image_to_frames(
                            inline["data"],
                            platform=base_frame.platform,
                            mode=base_frame.mode,
                            target_w=base_frame.width,
                            target_h=base_frame.height,
                            sheet_rows=1,
                            sheet_cols=num_frames,
                            locked_slots=[int(c) for c in base_frame.color_slots],
                        )
                        if frames:
                            return frames, f"Generated {len(frames)} frames via Gemini AI + CIELAB Hardware Quantizer"
        except Exception as exc:
            fallback_note = f"Gemini image endpoint unavailable ({exc}); used procedural pixel-art motion engine."
        else:
            fallback_note = "Gemini response contained no image; used procedural pixel-art motion engine."
    else:
        fallback_note = "No GEMINI_API_KEY configured; used procedural pixel-art motion engine."

    # Map prompt keywords to best procedural generator
    p_low = prompt.lower()
    if any(k in p_low for k in ("explode", "destroy", "shatter", "die", "death", "hit", "damage", "dissolve")):
        preset = "explode_dissolve"
    elif any(k in p_low for k in ("bank", "turn", "rotate", "spin", "roll", "tilt", "fly")):
        preset = "rotate_bank"
    elif any(k in p_low for k in ("breathe", "pulse", "idle", "grow", "charge", "attack")):
        preset = "pulse_breathe"
    elif any(k in p_low for k in ("hover", "float", "bob", "rotor", "chopper", "ship")):
        preset = "hover_bob"
    else:
        preset = "walk_cycle"

    frames = generate_motion_cycle(base_frame, preset=preset, num_frames=num_frames, intensity=1.0)
    return frames, f"{fallback_note} (Preset: {preset})"

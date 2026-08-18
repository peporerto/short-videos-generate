"""
tools/image_container.py
------------------------
Renders a source image into a fixed-size rounded-rectangle container using
"cover" crop mode (fill + crop overflow). Never upscales, never fits/stretches.

Guardrail rules (both abort with a clear error):
  1. Source image is smaller than the target container at the container's
     aspect ratio → abort (upscale forbidden).
  2. The crop needed to reach the container aspect ratio would remove more
     than `crop_threshold_pct` % of the source image area → abort.
"""

from __future__ import annotations
import math
from pathlib import Path
from PIL import Image, ImageDraw


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def place_image_in_container(
    src_path: str,
    container_width: int,
    container_height: int,
    corner_radius: int = 12,
    crop_threshold_pct: float = 35.0,
    bg_color: tuple[int, int, int] = (255, 255, 255),
) -> Image.Image:
    """
    Load *src_path*, validate guardrails, and return a PIL image that is
    exactly (container_width × container_height) with rounded corners.

    Parameters
    ----------
    src_path : str
        Path to the source image file.
    container_width, container_height : int
        Target container dimensions in pixels.
    corner_radius : int
        Rounded-corner radius in pixels.
    crop_threshold_pct : float
        Maximum fraction of source area that may be cropped away (0–100).
    bg_color : tuple
        Background fill colour (used behind the rounded mask).

    Returns
    -------
    PIL.Image  (RGBA, container_width × container_height)

    Raises
    ------
    ValueError
        If any guardrail is violated; message includes filename, actual dims,
        minimum required dims, and (when relevant) the crop % that would have
        been needed.
    """
    src_path = str(src_path)
    filename = Path(src_path).name

    img = Image.open(src_path).convert("RGBA")
    src_w, src_h = img.size

    cw, ch = container_width, container_height
    c_ratio = cw / ch          # container aspect ratio
    s_ratio = src_w / src_h    # source aspect ratio

    # ── Which dimension drives the cover scale? ───────────────────────────────
    if s_ratio >= c_ratio:
        # Width is the constraining axis → scale by height
        scale = ch / src_h
        scaled_w = src_w * scale
        scaled_h = float(ch)
        cropped_px_w = scaled_w - cw  # horizontal overflow to crop
        cropped_px_h = 0.0
    else:
        # Height is the constraining axis → scale by width
        scale = cw / src_w
        scaled_w = float(cw)
        scaled_h = src_h * scale
        cropped_px_w = 0.0
        cropped_px_h = scaled_h - ch  # vertical overflow to crop

    # ── Guardrail 1: no upscaling ─────────────────────────────────────────────
    if scale > 1.0:
        min_w = math.ceil(src_w / scale)   # minimum needed to avoid upscale
        min_h = math.ceil(src_h / scale)
        # Actually the minimum src size: we need scale ≤ 1, meaning
        # if height-driven: src_h >= ch  →  min src_h = ch; min src_w ≥ cw
        # if width-driven:  src_w >= cw  →  min src_w = cw; min src_h ≥ ch
        if s_ratio >= c_ratio:
            min_src_w = math.ceil(cw * src_w / src_h)
            min_src_h = ch
        else:
            min_src_w = cw
            min_src_h = math.ceil(ch * src_h / src_w)
        raise ValueError(
            f"[image_container] '{filename}' is too small to fill the container "
            f"without upscaling.\n"
            f"  Actual size      : {src_w}×{src_h} px\n"
            f"  Minimum required : {min_src_w}×{min_src_h} px\n"
            f"  Container size   : {cw}×{ch} px\n"
            f"  Scale needed     : {scale:.3f}× (must be ≤1.0)"
        )

    # ── Guardrail 2: crop threshold ───────────────────────────────────────────
    src_area = src_w * src_h
    # Area that will actually be kept after scaling + cropping
    kept_area = cw * ch / (scale * scale)  # in source-pixel units
    crop_pct = (1.0 - kept_area / src_area) * 100.0

    if crop_pct > crop_threshold_pct:
        raise ValueError(
            f"[image_container] '{filename}' requires too much cropping to fit "
            f"the container.\n"
            f"  Actual size        : {src_w}×{src_h} px\n"
            f"  Container size     : {cw}×{ch} px\n"
            f"  Crop needed        : {crop_pct:.1f}% of image area\n"
            f"  Allowed threshold  : {crop_threshold_pct:.1f}%\n"
            f"  Tip: supply an image whose aspect ratio is closer to "
            f"{cw}:{ch} ({c_ratio:.2f})"
        )

    # ── Cover-crop render ─────────────────────────────────────────────────────
    new_w = round(src_w * scale)
    new_h = round(src_h * scale)
    resized = img.resize((new_w, new_h), Image.LANCZOS)

    # Centre-crop to container
    left = (new_w - cw) // 2
    top = (new_h - ch) // 2
    cropped = resized.crop((left, top, left + cw, top + ch))

    # ── Rounded-corner mask ───────────────────────────────────────────────────
    mask = Image.new("L", (cw, ch), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), (cw - 1, ch - 1)], radius=corner_radius, fill=255)

    # Compose over bg
    result = Image.new("RGBA", (cw, ch), (*bg_color, 255))
    result.paste(cropped, (0, 0), mask)

    return result

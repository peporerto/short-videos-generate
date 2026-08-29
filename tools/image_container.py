"""
tools/image_container.py
------------------------
Renders a source image into a fixed-size rounded-rectangle container using
"contain" mode: the image is scaled (down or up) to fit entirely inside the
container, preserving its aspect ratio, then centered. Any leftover space is
filled with `bg_color` (letterbox / pillarbox), so the image is NEVER cropped
and NEVER distorted/stretched.

This replaces the old "cover + crop" behaviour, which required the source
aspect ratio to be close to the container's or it would abort. "contain"
mode works with ANY source size or aspect ratio, always.
"""

from __future__ import annotations
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
    bg_color: tuple[int, int, int] = (255, 255, 255),
    allow_upscale: bool = True,
    max_upscale: float = 3.0,
) -> Image.Image:
    """
    Load *src_path* and return a PIL image that is exactly
    (container_width × container_height) with rounded corners, containing
    the full source image scaled to fit (never cropped).

    Parameters
    ----------
    src_path : str
        Path to the source image file.
    container_width, container_height : int
        Target container dimensions in pixels.
    corner_radius : int
        Rounded-corner radius in pixels.
    bg_color : tuple
        Background/letterbox fill colour (RGB).
    allow_upscale : bool
        If True, small images are scaled UP to fit the container as fully
        as possible (up to `max_upscale`x their original size). If False,
        small images are kept at their native size and simply centered,
        leaving more background visible around them.
    max_upscale : float
        Safety cap on how much a small image can be enlarged, to avoid
        visibly blurry results from stretching a tiny source too far.
        Only applies when allow_upscale=True.

    Returns
    -------
    PIL.Image  (RGBA, container_width × container_height)
    """
    src_path = str(src_path)
    img = Image.open(src_path).convert("RGBA")
    src_w, src_h = img.size

    cw, ch = container_width, container_height

    # Scale so the image fits entirely inside the container (contain mode).
    scale = min(cw / src_w, ch / src_h)

    if not allow_upscale:
        scale = min(scale, 1.0)
    else:
        scale = min(scale, max_upscale)

    new_w = max(1, round(src_w * scale))
    new_h = max(1, round(src_h * scale))
    resized = img.resize((new_w, new_h), Image.LANCZOS)

    # Centre the resized image on a full-container canvas.
    offset = ((cw - new_w) // 2, (ch - new_h) // 2)
    canvas = Image.new("RGBA", (cw, ch), (*bg_color, 255))
    canvas.paste(resized, offset, resized)

    # Rounded-corner mask applied to the whole container.
    mask = Image.new("L", (cw, ch), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), (cw - 1, ch - 1)], radius=corner_radius, fill=255)

    result = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    result.paste(canvas, (0, 0), mask)

    return result
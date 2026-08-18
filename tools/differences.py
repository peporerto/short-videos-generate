"""
tools/differences.py
--------------------
Renders the "differences" short-form video niche.

For each diff block in the script:
  Beat 1 -- Hook     : images A+B blur-in, presenter poses (left then right), hook caption
  Beat 2 -- Question : no images, confused pose, question caption
  Beat 3 -- Def 1    : image A only (centred), professor pose, definition A caption
  Beat 4 -- Def 2    : images A+B, professor pose, definition B caption

Multiple diffs are chained back-to-back into a single raw video.
The output file replaces raw_concat.mp4 so generate_short.py's step 7 can
mix in audio + music unchanged.

Bug fixes applied:
  1. Animated GIF background   -- all frames loaded, global_frame_idx cycles them.
  2. Left/right presenter       -- switches exactly when image B starts entering.
  3. Alpha-fade image entry     -- images invisible until their entrance begins.
  4. TTS-driven beat durations  -- real speech lengths, now per manually-authored line.
  5. Worm size / centering      -- scaled to 42 % canvas height, centred dynamically.
  6. Cross-platform fonts       -- repo-local font, no Windows-only paths.
  7. Pose debug logging         -- _stamp_worm() logs pose + resolved path + load status
                                    on every call, so a misconfigured config.yaml shows
                                    up immediately in the console instead of silently
                                    rendering the wrong (or no) pose.
  8. Auto-fit caption font      -- font size per beat is chosen so captions can never
                                    grow tall enough to overlap the worm.
  9. SCRIPT FORMAT CHANGE (this round) -- caption chunking is no longer automatic
     sentence-detection (that approach kept breaking on real scripts -- dashes,
     hyphenated words, and edge-tts's own tokenization never lined up reliably
     with a regex-based sentence splitter). Each of the 4 fields (hook, question,
     definition_a, definition_b) is now an explicit LIST of physical lines from
     script.txt, under its own `hook:` / `question:` / `definition_a:` /
     `definition_b:` marker. Each line is synthesized as its own independent
     TTS call, so it gets its own word timings with zero risk of bleeding into
     a neighboring line. On screen, exactly one line is visible at a time, in
     the order written, and it disappears the instant its own audio ends --
     right before the next line's first word appears. The number of caption
     chunks in the video is exactly the number of lines you wrote, no more,
     no less, and no auto-splitting logic sits in between to get it wrong.
"""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import edge_tts
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageSequence

from tools.image_container import place_image_in_container
from tools.tts import concat_audio_segments, get_segment_duration


# ── Type aliases ──────────────────────────────────────────────────────────────

# (word, start_sec, duration_sec) -- start_sec/duration_sec are relative to
# the start of THIS line's own audio clip, never to the whole beat/diff.
WordTiming = tuple[str, float, float]


@dataclass
class CaptionLine:
    """One physical line from script.txt, with its own independent TTS timing."""
    text: str
    timings: list[WordTiming]
    duration: float


# ── Data classes ──────────────────────────────────────────────────────────────

_FIELDS = ("hook", "question", "definition_a", "definition_b")


@dataclass
class DiffBlock:
    index: int                # 1-based
    hook: list[str]
    question: list[str]
    definition_a: list[str]
    definition_b: list[str]


# ── Script parser ─────────────────────────────────────────────────────────────

_DIFF_RE = re.compile(r"^diff(\d+)\s*:\s*$", re.IGNORECASE)
_FIELD_RE = re.compile(r"^(hook|question|definition_a|definition_b)\s*:\s*$", re.IGNORECASE)


def parse_differences_script(script_path: str) -> list[DiffBlock]:
    """
    Parse input/differences/script.txt.

    Format (new -- explicit sub-markers, each field can span as many
    physical lines as you want; each line becomes its own caption chunk):

        diff1:
        hook:
        This is Rainbow Six Siege.
        This is Call of Duty.
        question:
        What's the difference?
        definition_a:
        Rainbow Six Siege is slow,
        tactical, and unforgiving
        one life per round, destructible walls,
        and every match built around outsmarting the enemy,
        not outgunning them.
        definition_b:
        Call of Duty is fast and relentless
        respawns, run-and-gun action,
        and gunplay built for instant,
        nonstop firefights. So
        are you team Rainbow Six, or team Call of Duty?
        diff2:
        ...

    Lines starting with '#' and blank lines are ignored. Every diff needs
    all 4 sub-markers, each with at least one line under it.
    """
    path = Path(script_path)
    if not path.exists():
        raise FileNotFoundError(f"Differences script not found: {script_path}")

    blocks: list[DiffBlock] = []
    current_idx: Optional[int] = None
    current_field: Optional[str] = None
    current_data: dict[str, list[str]] = {}

    def _flush_diff(idx: int, data: dict[str, list[str]]) -> None:
        missing = [f for f in _FIELDS if not data.get(f)]
        if missing:
            raise ValueError(
                f"diff{idx} is missing required section(s): {', '.join(missing)}. "
                f"Every diff needs a hook:, question:, definition_a: and "
                f"definition_b: marker, each followed by at least one line of text."
            )
        blocks.append(
            DiffBlock(
                index=idx,
                hook=data["hook"],
                question=data["question"],
                definition_a=data["definition_a"],
                definition_b=data["definition_b"],
            )
        )

    with open(path, encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.rstrip("\n").strip()
            if not line or line.startswith("#"):
                continue

            m_diff = _DIFF_RE.match(line)
            if m_diff:
                if current_idx is not None:
                    _flush_diff(current_idx, current_data)
                current_idx = int(m_diff.group(1))
                current_data = {f: [] for f in _FIELDS}
                current_field = None
                continue

            m_field = _FIELD_RE.match(line)
            if m_field:
                current_field = m_field.group(1).lower()
                continue

            if current_idx is None:
                continue  # stray line before the first diffN: -- ignore
            if current_field is None:
                raise ValueError(
                    f"diff{current_idx}: found text before any hook:/question:/"
                    f"definition_a:/definition_b: marker -- line was: {line!r}"
                )
            current_data[current_field].append(line)

    if current_idx is not None:
        _flush_diff(current_idx, current_data)

    if not blocks:
        raise ValueError(f"No diff blocks found in {script_path}")

    return sorted(blocks, key=lambda b: b.index)


# ── TTS with per-word timings ──────────────────────────────────────────────────

async def _synthesize_with_word_timings(
    text: str,
    output_path: str,
    voice: str,
    rate: str = "+5%",
) -> list[WordTiming]:
    """
    Stream edge_tts to capture both audio bytes AND WordBoundary events.
    Returns list of (word, start_sec, duration_sec) -- in order of speech,
    relative to the start of THIS clip.

    Does NOT call anything from tools/tts.py so that file is never touched.
    """
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    timings: list[WordTiming] = []
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "wb") as fh:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                fh.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 1e7        # 100-ns units -> seconds
                dur = chunk["duration"] / 1e7
                timings.append((chunk["text"], start, dur))
    return timings


def _duration_from_timings(timings: list[WordTiming], trailing: float = 0.15) -> float:
    """Derive total clip duration from the last word's end time + trailing buffer."""
    if not timings:
        return 0.0
    _, start, dur = timings[-1]
    return start + dur + trailing


def _fabricate_line_timing(text: str, sec_per_word: float = 0.35) -> tuple[list[WordTiming], float]:
    """
    Fallback used only when real TTS/WordBoundary capture fails for a line
    (network hiccup, etc). Produces evenly-spaced fake timings so the line
    still renders as a caption -- just without true voice sync for that
    one line specifically; every other line is unaffected.
    """
    words = text.split()
    timings = [(w, i * sec_per_word, sec_per_word) for i, w in enumerate(words)]
    duration = max(0.5, len(words) * sec_per_word + 0.15)
    return timings, duration


# ── Low-level canvas helpers ──────────────────────────────────────────────────

def _load_font(font_path: str, size: int) -> ImageFont.FreeTypeFont:
    """Bug 6: try the repo-local path first; fall back to PIL default with a loud WARNING."""
    try:
        return ImageFont.truetype(font_path, size)
    except OSError:
        print(
            f"  [differences] WARNING: font not found at '{font_path}'. "
            "Falling back to PIL default bitmap font -- caption quality will "
            "be degraded. Add a real .ttf under assets/fonts/ to fix this."
        )
        return ImageFont.load_default()


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Word-wrap *text* to fit within *max_width* pixels."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        bbox = font.getbbox(candidate)
        if bbox[2] - bbox[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _fit_caption(
    texts: list[str],
    font_path: str,
    base_size: int,
    max_width: int,
    max_height: int,
    min_size: int = 20,
    step: int = 2,
) -> ImageFont.FreeTypeFont:
    """
    Bug 8: auto-fit a caption's font size so it never grows tall enough to
    overlap the worm below it. Fits against each of *texts* (here: the
    beat's own literal lines, shown one at a time) so a beat with several
    short lines can use a bigger, more legible size than sizing for one
    giant combined string would allow.
    """
    size = base_size
    while size > min_size:
        font = _load_font(font_path, size)
        line_height = font.getbbox("Ag")[3] + 6
        fits = True
        for text in texts:
            if not text:
                continue
            wrapped = _wrap_text(text, font, max_width)
            if len(wrapped) * line_height > max_height:
                fits = False
                break
        if fits:
            return font
        size -= step
    return _load_font(font_path, min_size)


def _apply_blur_in(img: Image.Image, progress: float) -> Image.Image:
    """Bug 3: progress 0.0 = fully transparent + blurry; 1.0 = sharp + opaque."""
    if progress <= 0.0:
        return Image.new("RGBA", img.size, (0, 0, 0, 0))

    radius = 12.0 * (1.0 - progress) ** 2
    result = img.convert("RGBA")
    if radius >= 0.3:
        result = result.filter(ImageFilter.GaussianBlur(radius=radius))

    if progress < 1.0:
        r, g, b, a = result.split()
        a = a.point(lambda px: int(px * progress))
        result = Image.merge("RGBA", (r, g, b, a))

    return result


def _paste_with_alpha(canvas: Image.Image, overlay: Image.Image, x: int, y: int) -> None:
    """Paste an RGBA overlay onto an RGB/RGBA canvas at (x, y)."""
    if overlay.mode != "RGBA":
        overlay = overlay.convert("RGBA")
    canvas.paste(overlay, (x, y), overlay)


def _cumulative_offsets(lines: list[CaptionLine]) -> list[float]:
    """Start time (relative to the beat) of each line, assuming lines play back-to-back."""
    offsets: list[float] = []
    running = 0.0
    for line in lines:
        offsets.append(running)
        running += line.duration
    return offsets


def _draw_caption_lines(
    draw: ImageDraw.ImageDraw,
    font: ImageFont.FreeTypeFont,
    canvas_width: int,
    caption_y: int,
    max_width: int,
    color: tuple[int, int, int],
    current_time: float,
    lines: list[CaptionLine],
    offsets: list[float],
) -> None:
    """
    Manual-line caption renderer. Exactly one line is ever visible: the one
    whose offset window contains current_time. Words within it reveal one
    by one using that line's OWN WordBoundary timings (each line was
    synthesized independently, so there's no possibility of another line's
    words leaking in). The line disappears the instant its own audio ends
    -- before the next line's first word ever appears -- so consecutive
    lines never visually pile up on top of each other.
    """
    if not lines:
        return

    idx = 0
    for i, off in enumerate(offsets):
        if current_time >= off:
            idx = i
        else:
            break

    line = lines[idx]
    local_t = current_time - offsets[idx]
    if local_t >= line.duration:
        return  # this line's audio already finished -- nothing to show

    if line.timings:
        visible_words = [w for w, s, _ in line.timings if s <= local_t]
        if not visible_words:
            return  # first WordBoundary hasn't fired yet
        partial = " ".join(visible_words)
    else:
        partial = line.text

    wrapped = _wrap_text(partial, font, max_width)
    line_height = font.getbbox("Ag")[3] + 6
    y = caption_y
    for wline in wrapped:
        bbox = font.getbbox(wline)
        w = bbox[2] - bbox[0]
        x = (canvas_width - w) // 2
        draw.text((x + 2, y + 2), wline, font=font, fill=(200, 200, 200))
        draw.text((x, y), wline, font=font, fill=color)
        y += line_height


# ── Frame-level compositor ────────────────────────────────────────────────────

class DifferencesCompositor:
    """Builds individual frames for a single diff cycle."""

    def __init__(
        self,
        cfg: dict,
        diff: DiffBlock,
        beat_frame_counts: dict[str, int],
        caption_lines: dict[str, list[CaptionLine]],
    ) -> None:
        self.cfg = cfg
        self.diff = diff
        self._fps = int(cfg["fps"])

        cw = cfg["canvas_width"]
        ch = cfg["canvas_height"]

        self.hook_frames = beat_frame_counts["hook"]
        self.question_frames = beat_frame_counts["question"]
        self.def1_frames = beat_frame_counts["definition_a"]
        self.def2_frames = beat_frame_counts["definition_b"]
        self.total_frames = (
            self.hook_frames + self.question_frames + self.def1_frames + self.def2_frames
        )

        # ── Bug 1: load ALL GIF frames ────────────────────────────────────────
        bg_path = cfg["background"]
        if os.path.exists(bg_path):
            raw_bg = Image.open(bg_path)
            self._bg_frames: list[Image.Image] = [
                frame.convert("RGB").resize((cw, ch), Image.LANCZOS)
                for frame in ImageSequence.Iterator(raw_bg)
            ]
            if not self._bg_frames:
                self._bg_frames = [Image.new("RGB", (cw, ch), (248, 245, 238))]
        else:
            self._bg_frames = [Image.new("RGB", (cw, ch), (248, 245, 238))]

        # ── Scale worm by target HEIGHT (default 52 % of canvas) ──────────────
        worm_h_pct = float(cfg.get("worm_height_pct", 0.52))
        target_worm_h = round(worm_h_pct * ch)

        # ── Bug 2: load presenter_left and presenter_right separately ─────────
        self._worm: dict[str, Optional[Image.Image]] = {
            "presenter_left": self._load_worm(cfg["worm_presenter_left"], target_worm_h),
            "presenter_right": self._load_worm(cfg["worm_presenter_right"], target_worm_h),
            "confused": self._load_worm(cfg["worm_confused"], target_worm_h),
            "professor": self._load_worm(cfg["worm_professor"], target_worm_h),
        }
        self._worm_paths: dict[str, str] = {
            "presenter_left": cfg["worm_presenter_left"],
            "presenter_right": cfg["worm_presenter_right"],
            "confused": cfg["worm_confused"],
            "professor": cfg["worm_professor"],
        }

        # ── Container images ──────────────────────────────────────────────────
        cont_w = cfg["container_width"]
        cont_h = cfg["container_height"]
        radius = cfg["container_radius"]
        threshold = cfg["crop_threshold_pct"]
        images_dir = cfg["images_dir"]

        def _find_image(subfolder: str, name: str) -> str:
            base = Path(images_dir) / subfolder
            for ext in (".png", ".jpg", ".jpeg", ".webp"):
                candidate = base / (name + ext)
                if candidate.exists():
                    return str(candidate)
            raise FileNotFoundError(
                f"No image found for '{name}' in {base} "
                f"(looked for .png/.jpg/.jpeg/.webp)"
            )

        diff_folder = f"diff{diff.index}"
        img_a_path = _find_image(diff_folder, "imageA")
        img_b_path = _find_image(diff_folder, "imageB")
        print(f"    [diff{diff.index}] imageA -> {img_a_path}")
        print(f"    [diff{diff.index}] imageB -> {img_b_path}")

        self._img_a = place_image_in_container(img_a_path, cont_w, cont_h, radius, threshold)
        self._img_b = place_image_in_container(img_b_path, cont_w, cont_h, radius, threshold)

        total_pair_w = cont_w * 2 + cfg["container_margin"]
        pair_left = (cw - total_pair_w) // 2
        self._xa = pair_left
        self._xb = pair_left + cont_w + cfg["container_margin"]
        self._cy = cfg["container_y"]

        self._worm_cx = cw // 2
        self._worm_y = int(cfg.get("worm_y", 680))

        # ── Caption geometry / colors (shared across beats) ──────────────────
        self._caption_color = _hex_to_rgb(cfg["caption_color"])
        self._caption_y = cfg["caption_y"]
        self._caption_max_w = cfg["caption_max_width"]
        self._wm_font = _load_font(cfg["caption_font"], cfg["watermark_font_size"])
        self._wm_color = _hex_to_rgb(cfg["watermark_color"])

        font_path = cfg["caption_font"]
        base_size = cfg["caption_font_size"]
        caption_worm_margin = int(cfg.get("caption_worm_margin", 24))
        caption_max_h = max(80, self._worm_y - self._caption_y - caption_worm_margin)

        # ── Literal per-line caption chunks ────────────────
        self._hook_lines = caption_lines["hook"]
        self._question_lines = caption_lines["question"]
        self._def1_lines = caption_lines["definition_a"]
        self._def2_lines = caption_lines["definition_b"]

        self._hook_offsets = _cumulative_offsets(self._hook_lines)
        self._question_offsets = _cumulative_offsets(self._question_lines)
        self._def1_offsets = _cumulative_offsets(self._def1_lines)
        self._def2_offsets = _cumulative_offsets(self._def2_lines)

        self._hook_font = _fit_caption(
            [l.text for l in self._hook_lines], font_path, base_size, self._caption_max_w, caption_max_h,
        )
        self._question_font = _fit_caption(
            [l.text for l in self._question_lines], font_path, base_size, self._caption_max_w, caption_max_h,
        )
        self._def1_font = _fit_caption(
            [l.text for l in self._def1_lines], font_path, base_size, self._caption_max_w, caption_max_h,
        )
        self._def2_font = _fit_caption(
            [l.text for l in self._def2_lines], font_path, base_size, self._caption_max_w, caption_max_h,
        )

        for label, lines in (
            ("hook", self._hook_lines),
            ("question", self._question_lines),
            ("definition_a", self._def1_lines),
            ("definition_b", self._def2_lines),
        ):
            print(f"    [caption-lines] {label}: {len(lines)} line(s)")
            for i, l in enumerate(lines):
                print(f"        [{i}] ({l.duration:.2f}s) {l.text!r}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _load_worm(self, path: str, target_h: int) -> Optional[Image.Image]:
        """Bug 5: scale by target HEIGHT so all poses fill the configured canvas fraction."""
        if not os.path.exists(path):
            print(f"  [differences] WARNING: worm pose not found: {path}")
            return None
        img = Image.open(path).convert("RGBA")
        ratio = img.width / img.height
        w = round(target_h * ratio)
        return img.resize((w, target_h), Image.LANCZOS)

    def _base_frame(self, global_frame_idx: int) -> Image.Image:
        """Select the correct GIF frame with slowdown and pause at the end of loop."""
        num_frames = len(self._bg_frames)
        if num_frames <= 1:
            bg = self._bg_frames[0]
            return bg.copy().convert("RGBA")

        slow_factor = 3  # Hold each GIF frame for 3 video frames to slow it down
        pause_frames = 30  # Pause for 30 video frames (1.0s at 30fps) at the loop boundary

        active_period = num_frames * slow_factor
        total_period = active_period + pause_frames

        local_step = global_frame_idx % total_period
        if local_step < active_period:
            gif_idx = local_step // slow_factor
        else:
            gif_idx = num_frames - 1  # Hold the last frame during the pause

        bg = self._bg_frames[gif_idx]
        return bg.copy().convert("RGBA")

    def _stamp_watermark(self, frame: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        """Render watermark rotated 90° on the left edge, bottom-to-top."""
        text = self.cfg["watermark_text"]
        font = self._wm_font
        bbox = font.getbbox(text)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        # Padding + offsetting the draw position by -bbox[0]/-bbox[1] is what
        # actually fixes the clipping: getbbox()'s box does not start at
        # (0, 0), so drawing at a fixed (2, 2) like before let part of the
        # glyphs land outside the small canvas -- invisible after rotation,
        # which looked like the watermark running off the frame.
        pad = 8
        txt_img = Image.new("RGBA", (text_w + pad * 2, text_h + pad * 2), (0, 0, 0, 0))
        txt_draw = ImageDraw.Draw(txt_img)
        txt_draw.text((pad - bbox[0], pad - bbox[1]), text, font=font, fill=self._wm_color)
        # Rotate 90° counter-clockwise so text reads bottom-to-top
        rotated = txt_img.rotate(90, expand=True)
        margin = 12
        x = frame.width - rotated.width - margin
        y = frame.height - rotated.height - margin
        _paste_with_alpha(frame, rotated, x, y)

    def _stamp_worm(self, frame: Image.Image, pose: str) -> None:
        """
        Bug 5: centre worm on canvas_width // 2, not a config magic number.
        Bug 7 (real fix): logs pose + resolved path + load status on every
        call, so a misconfigured config.yaml shows up immediately.
        """
        worm = self._worm.get(pose)
        path = self._worm_paths.get(pose, "<unknown>")
        if worm is None:
            print(f"    [worm-debug] pose='{pose}' path='{path}' -> FAILED TO LOAD")
            return
        print(f"    [worm-debug] pose='{pose}' path='{path}' -> {worm.width}x{worm.height}")
        x = self._worm_cx - worm.width // 2
        _paste_with_alpha(frame, worm, x, self._worm_y)

    # ── Frame generators ──────────────────────────────────────────────────────
    # Pose-per-beat is UNCHANGED from before: presenter during the hook
    # (left -> right exactly when image B starts entering), confused during
    # the question, professor during both definition beats. Only the
    # caption rendering changed this round.

    def frame_hook(self, frame_idx: int, global_frame_idx: int) -> Image.Image:
        f = self._base_frame(global_frame_idx)
        draw = ImageDraw.Draw(f)
        total = self.hook_frames

        # Transition duration in frames based on transition_sec
        trans_sec = float(self.cfg.get("transition_sec", 0.4))
        trans_frames = round(trans_sec * self._fps)

        progress_a = min(1.0, frame_idx / max(1, trans_frames))
        b_start_frame = total * 0.3
        progress_b = min(1.0, max(0.0, (frame_idx - b_start_frame) / max(1, trans_frames)))

        img_a = _apply_blur_in(self._img_a, progress_a)
        img_b = _apply_blur_in(self._img_b, progress_b)

        _paste_with_alpha(f, img_a, self._xa, self._cy)
        _paste_with_alpha(f, img_b, self._xb, self._cy)

        pose = "presenter_right" if frame_idx >= b_start_frame else "presenter_left"
        self._stamp_worm(f, pose)

        current_time = frame_idx / self._fps
        _draw_caption_lines(
            draw, self._hook_font, self.cfg["canvas_width"], self._caption_y,
            self._caption_max_w, self._caption_color, current_time,
            self._hook_lines, self._hook_offsets,
        )
        self._stamp_watermark(f, draw)
        return f.convert("RGB")

    def frame_question(self, frame_idx: int, global_frame_idx: int) -> Image.Image:
        f = self._base_frame(global_frame_idx)
        draw = ImageDraw.Draw(f)
        self._stamp_worm(f, "confused")

        current_time = frame_idx / self._fps
        _draw_caption_lines(
            draw, self._question_font, self.cfg["canvas_width"], self._caption_y,
            self._caption_max_w, self._caption_color, current_time,
            self._question_lines, self._question_offsets,
        )
        self._stamp_watermark(f, draw)
        return f.convert("RGB")

    def frame_def1(self, frame_idx: int, global_frame_idx: int) -> Image.Image:
        f = self._base_frame(global_frame_idx)
        draw = ImageDraw.Draw(f)

        # Same blur-in transition as hook (visual only, no audio)
        trans_sec = float(self.cfg.get("transition_sec", 0.4))
        trans_frames = round(trans_sec * self._fps)
        progress = min(1.0, frame_idx / max(1, trans_frames))
        img_a = _apply_blur_in(self._img_a, progress)

        cx = (self.cfg["canvas_width"] - self.cfg["container_width"]) // 2
        _paste_with_alpha(f, img_a, cx, self._cy)

        self._stamp_worm(f, "professor")

        current_time = frame_idx / self._fps
        _draw_caption_lines(
            draw, self._def1_font, self.cfg["canvas_width"], self._caption_y,
            self._caption_max_w, self._caption_color, current_time,
            self._def1_lines, self._def1_offsets,
        )
        self._stamp_watermark(f, draw)
        return f.convert("RGB")

    def frame_def2(self, frame_idx: int, global_frame_idx: int) -> Image.Image:
        f = self._base_frame(global_frame_idx)
        draw = ImageDraw.Draw(f)

        # Same blur-in transition as hook (visual only, no audio)
        trans_sec = float(self.cfg.get("transition_sec", 0.4))
        trans_frames = round(trans_sec * self._fps)
        progress_a = min(1.0, frame_idx / max(1, trans_frames))
        b_start_frame = trans_frames * 0.3
        progress_b = min(1.0, max(0.0, (frame_idx - b_start_frame) / max(1, trans_frames)))
        img_a = _apply_blur_in(self._img_a, progress_a)
        img_b = _apply_blur_in(self._img_b, progress_b)

        _paste_with_alpha(f, img_a, self._xa, self._cy)
        _paste_with_alpha(f, img_b, self._xb, self._cy)

        self._stamp_worm(f, "professor")

        current_time = frame_idx / self._fps
        _draw_caption_lines(
            draw, self._def2_font, self.cfg["canvas_width"], self._caption_y,
            self._caption_max_w, self._caption_color, current_time,
            self._def2_lines, self._def2_offsets,
        )
        self._stamp_watermark(f, draw)
        return f.convert("RGB")

    def all_frames(self, global_start: int = 0) -> list[Image.Image]:
        frames: list[Image.Image] = []
        g = global_start
        for i in range(self.hook_frames):
            frames.append(self.frame_hook(i, g)); g += 1
        for i in range(self.question_frames):
            frames.append(self.frame_question(i, g)); g += 1
        for i in range(self.def1_frames):
            frames.append(self.frame_def1(i, g)); g += 1
        for i in range(self.def2_frames):
            frames.append(self.frame_def2(i, g)); g += 1
        return frames


# ── FFmpeg render ─────────────────────────────────────────────────────────────

def _render_frames_to_video(
    frames: list[Image.Image],
    output_path: str,
    fps: int,
    width: int,
    height: int,
) -> None:
    """Pipe raw RGB frames into FFmpeg to produce a silent H.264 MP4."""
    cmd = [
        "ffmpeg", "-y",
        "-loglevel", "error",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{width}x{height}",
        "-pix_fmt", "rgb24",
        "-r", str(fps),
        "-i", "pipe:0",
        "-vcodec", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "fast",
        output_path,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    for frame in frames:
        proc.stdin.write(frame.tobytes())  # type: ignore[union-attr]
    proc.stdin.close()  # type: ignore[union-attr]
    proc.wait()
    if proc.returncode != 0:
        err = proc.stderr.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"FFmpeg frame-pipe failed:\n{err}")


# ── Public entry point ────────────────────────────────────────────────────────

async def render_differences(niche_config: dict, output_path: str) -> None:
    """
    Full pipeline:
      1. Parse script -> list[DiffBlock] (each field is now a list of lines)
      2. For each diff: synthesize EVERY line independently (own audio, own
         word timings), grouped back by field
      3. Build frames with DifferencesCompositor
      4. Pipe all frames to FFmpeg -> output_path (raw_concat.mp4)
      5. Concatenate every line's audio file, in order -> output/audio.mp3
      6. Overlay pop SFX at the entrance of each image during the hook beats.
    """
    cfg = niche_config
    script_path = cfg.get("script_path", "input/differences/script.txt")
    fps = int(cfg.get("fps", 30))
    canvas_w = int(cfg.get("canvas_width", 720))
    canvas_h = int(cfg.get("canvas_height", 1280))
    voice = cfg.get("voice", "en-US-GuyNeural")

    diffs = parse_differences_script(script_path)
    print(f"  [differences] Found {len(diffs)} diff block(s) in script.")

    all_frames: list[Image.Image] = []
    all_audio_paths: list[str] = []
    global_frame_count = 0
    diff_durations = {}  # Store durations for pop overlay alignment

    for diff in diffs:
        print(f"  [differences] Processing diff{diff.index}")
        seg_dir = os.path.join("output", "differences", f"diff{diff.index}")
        os.makedirs(seg_dir, exist_ok=True)

        field_lines = {
            "hook": diff.hook,
            "question": diff.question,
            "definition_a": diff.definition_a,
            "definition_b": diff.definition_b,
        }

        # Flatten every physical line across all 4 fields into one parallel
        # TTS batch -- each line gets its OWN independent synthesis call.
        flat: list[tuple[str, str]] = []
        for field in _FIELDS:
            for text in field_lines[field]:
                flat.append((field, text))

        async def _synth(i: int, field: str, text: str):
            path = os.path.join(seg_dir, f"seg_{i:03d}.mp3")
            rate = cfg.get("voice_rate", "+50%")
            try:
                timings = await _synthesize_with_word_timings(text, path, voice, rate=rate)
                dur = _duration_from_timings(timings)
                if dur <= 0:
                    dur = get_segment_duration(path)
                return field, CaptionLine(text=text, timings=timings, duration=dur), path
            except Exception as exc:
                print(
                    f"  [differences] WARNING: TTS failed for {field} line "
                    f"{text!r} ({exc}); fabricating timing for this line only."
                )
                timings, dur = _fabricate_line_timing(text)
                return field, CaptionLine(text=text, timings=timings, duration=dur), None

        results = await asyncio.gather(
            *[_synth(i, field, text) for i, (field, text) in enumerate(flat)]
        )

        by_field: dict[str, list[CaptionLine]] = {f: [] for f in _FIELDS}
        seg_paths: list[str] = []
        for field, cap_line, path in results:
            by_field[field].append(cap_line)
            if path is not None:
                seg_paths.append(path)

        beat_durations = {f: sum(cl.duration for cl in by_field[f]) for f in _FIELDS}
        beat_frame_counts = {f: max(1, round(beat_durations[f] * fps)) for f in _FIELDS}
        diff_durations[diff.index] = beat_durations

        print(
            f"    beat durations (s): hook={beat_durations['hook']:.2f}  "
            f"q={beat_durations['question']:.2f}  "
            f"def1={beat_durations['definition_a']:.2f}  "
            f"def2={beat_durations['definition_b']:.2f}"
        )

        compositor = DifferencesCompositor(cfg, diff, beat_frame_counts, by_field)
        frames = compositor.all_frames(global_start=global_frame_count)
        all_frames.extend(frames)
        global_frame_count += len(frames)
        all_audio_paths.extend(seg_paths)

        print(
            f"    -> {len(frames)} frames ({len(frames)/fps:.1f}s) | "
            f"audio segs: {len(seg_paths)}"
        )

    total_sec = len(all_frames) / fps
    print(f"  [differences] Total: {len(all_frames)} frames ({total_sec:.1f}s). Encoding...")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    _render_frames_to_video(all_frames, output_path, fps, canvas_w, canvas_h)
    print(f"  [differences] Saved raw video -> {output_path}")

    if all_audio_paths:
        final_audio = "output/audio.mp3"
        os.makedirs("output", exist_ok=True)
        concat_audio_segments(all_audio_paths, final_audio)
        print(f"  [differences] Line-aligned audio -> {final_audio}")

        # ── Overlay pop SFX at image entry frames in the hook beat ──
        pop_audio = cfg.get("pop_audio", "input/audio/dragon-studio-clean-minimal-pop-467466.mp3")
        if os.path.exists(pop_audio):
            pop_timestamps = []
            current_time = 0.0
            for diff in diffs:
                durs = diff_durations.get(diff.index, {f: 0.0 for f in _FIELDS})
                dur_hook = durs["hook"]

                # 1. imageA starts entering at the beginning of the hook (current_time)
                pop_timestamps.append(current_time)

                # 2. imageB starts entering at current_time + (hook_frames * 0.3) / fps
                hook_frames = round(dur_hook * fps)
                b_start_sec = (hook_frames * 0.3) / fps
                pop_timestamps.append(current_time + b_start_sec)

                # Advance current_time by the duration of the entire diff cycle
                current_time += dur_hook + durs["question"] + durs["definition_a"] + durs["definition_b"]

            print(f"  [differences] Overlaying pop SFX at: {[round(t, 2) for t in pop_timestamps]}s")
            temp_audio = final_audio + ".temp.mp3"
            try:
                filter_parts = []
                n = len(pop_timestamps)
                # Split pop_audio (input 1) into n streams
                filter_parts.append(f"[1]asplit={n}" + "".join(f"[p{i}]" for i in range(n)))

                # Format voice track (input 0) to stereo 44.1kHz
                filter_parts.append(f"[0]aformat=sample_rates=44100:channel_layouts=stereo[a0]")

                for i, ts in enumerate(pop_timestamps):
                    ms = int(ts * 1000)
                    filter_parts.append(
                        f"[p{i}]adelay={ms}:all=1,"
                        f"aformat=sample_rates=44100:channel_layouts=stereo"
                        f"[ap{i}]"
                    )
                # Mix voice track (a0) with all delayed pop tracks (ap{i})
                mix_inputs = "[a0]" + "".join(f"[ap{i}]" for i in range(n))
                filter_parts.append(f"{mix_inputs}amix=inputs={n+1}:normalize=0[aout]")
                filter_complex = ";".join(filter_parts)

                cmd = [
                    "ffmpeg", "-y", "-loglevel", "error",
                    "-i", final_audio,
                    "-i", pop_audio,
                    "-filter_complex", filter_complex,
                    "-map", "[aout]",
                    temp_audio
                ]
                r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                if r.returncode == 0:
                    os.replace(temp_audio, final_audio)
                    print("  [differences] Pop SFX overlaid successfully.")
                else:
                    err = r.stderr.decode("utf-8", errors="replace")
                    print(f"  [differences] WARNING: Failed to overlay pop SFX: {err}")
                    if os.path.exists(temp_audio):
                        os.remove(temp_audio)
            except Exception as e:
                print(f"  [differences] WARNING: Error overlaying pop SFX: {e}")
    else:
        print("  [differences] No TTS audio; existing output/audio.mp3 will be used.")
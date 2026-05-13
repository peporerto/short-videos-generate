import os
import ffmpeg
from typing import List, Optional

EFFECT_SEQUENCE = [
    "zoom_in",
    "pan_left",
    "zoom_out",
    "pan_right",
    "zoom_in_out",
    "pan_up",
    "zoom_in",
    "pan_left",
]

# ── Resoluciones por formato ──────────────────────────────────────────────────
FORMAT_CONFIG = {
    "short": {"width": 1080, "height": 1920},  # Vertical 9:16
    "long":  {"width": 1920, "height": 1080},  # Horizontal 16:9
}


def _pick_effect(index: int, override: str = None) -> str:
    if override and override != "zoom_in":
        if index % 4 == 0:
            return EFFECT_SEQUENCE[index % len(EFFECT_SEQUENCE)]
        return override
    return EFFECT_SEQUENCE[index % len(EFFECT_SEQUENCE)]


def _get_clip_duration(index: int, base_duration: float) -> float:
    if index % 5 == 0:
        return base_duration * 1.35
    elif index % 3 == 0:
        return base_duration * 0.80
    return base_duration


def _apply_camera_effect(
    stream,
    effect_name: str,
    duration: float,
    width: int,
    height: int,
    fps: int,
    intensity: float = 1.0
):
    total_frames = max(int(duration * fps), 1)
    speed = 0.0008 * intensity

    if effect_name == "zoom_in":
        z = f"min(zoom+{speed:.4f},1.08)"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"

    elif effect_name == "zoom_out":
        z = f"if(eq(on,1),1.08,max(zoom-{speed:.4f},1.0))"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"

    elif effect_name == "zoom_in_out":
        half = total_frames // 2
        z = f"if(lte(on,{half}),min(zoom+{speed:.4f},1.08),max(zoom-{speed:.4f},1.0))"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"

    elif effect_name == "pan_right":
        step = max(int(width * 0.08 / total_frames), 1)
        z = "1.08"
        x = f"if(eq(on,1),0,x+{step})"
        y = "ih/2-(ih/zoom/2)"

    elif effect_name == "pan_left":
        step = max(int(width * 0.08 / total_frames), 1)
        z = "1.08"
        x = f"if(eq(on,1),iw*0.08,x-{step})"
        y = "ih/2-(ih/zoom/2)"

    elif effect_name == "pan_up":
        step = max(int(height * 0.08 / total_frames), 1)
        z = "1.08"
        x = "iw/2-(iw/zoom/2)"
        y = f"if(eq(on,1),ih*0.08,y-{step})"

    elif effect_name == "pan_down":
        step = max(int(height * 0.08 / total_frames), 1)
        z = "1.08"
        x = "iw/2-(iw/zoom/2)"
        y = f"if(eq(on,1),0,y+{step})"

    else:
        z = f"min(zoom+{speed:.4f},1.08)"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"

    stream = ffmpeg.filter(
        stream, 'zoompan',
        z=z, x=x, y=y,
        d=total_frames,
        s=f'{width}x{height}',
        fps=fps
    )
    return stream


def _get_subtitle_style(video_format: str) -> str:
    if video_format == "long":
        return (
            "FontName=Arial,"
            "FontSize=22,"
            "PrimaryColour=&HFFFFFF,"
            "OutlineColour=&H000000,"
            "Outline=2,"
            "Alignment=2,"
            "MarginV=60"
        )
    return (
        "FontName=Arial,"
        "FontSize=14,"
        "PrimaryColour=&HFFFFFF,"
        "OutlineColour=&H000000,"
        "Outline=2,"
        "Alignment=2,"
        "MarginV=40"
    )


def assemble_video(
    image_paths: List[str],
    audio_path: str,
    subtitle_path: Optional[str],
    output_path: str,
    duration_sec: float,
    music_path: str = None,
    camera_effect: str = "zoom_in",
    effect_list: Optional[List[str]] = None,
    video_format: str = "short"
) -> None:
    """
    Ensambla imágenes con efectos Ken Burns, crossfade y color grading.

    Args:
        image_paths:   Lista de rutas de imágenes
        audio_path:    Ruta del audio principal
        subtitle_path: Ruta del SRT o None para omitir subtítulos
        output_path:   Ruta del video final
        duration_sec:  Duración total en segundos
        music_path:    Música de fondo (opcional)
        camera_effect: Efecto de cámara por defecto
        effect_list:   Efectos individuales por imagen (opcional)
        video_format:  'short' vertical 9:16 o 'long' horizontal 16:9
    """
    try:
        num_images = len(image_paths)
        if num_images == 0:
            raise ValueError("No hay imágenes para ensamblar.")

        fmt    = FORMAT_CONFIG.get(video_format, FORMAT_CONFIG["short"])
        width  = fmt["width"]
        height = fmt["height"]

        crossfade_duration = 0.5
        base_duration = (duration_sec + crossfade_duration * (num_images - 1)) / num_images
        fps = 30

        audio = ffmpeg.input(audio_path)

        # ── Construir clips ───────────────────────────────────────────────────
        inputs = []
        for i, img in enumerate(image_paths):
            clip_duration = _get_clip_duration(i, base_duration)

            if effect_list and i < len(effect_list):
                effect = effect_list[i]
            else:
                effect = _pick_effect(i, camera_effect)

            intensity = 1.5 if i % 5 == 0 else 1.0

            v = ffmpeg.input(img, loop=1, t=clip_duration).video
            v = ffmpeg.filter(v, 'scale', width * 2, height * 2,
                              force_original_aspect_ratio='increase')
            v = ffmpeg.filter(v, 'crop', width * 2, height * 2)
            v = ffmpeg.filter(v, 'setsar', 1)
            v = ffmpeg.filter(v, 'eq',
                              contrast=1.05,
                              brightness=-0.02,
                              saturation=0.85)
            v = _apply_camera_effect(v, effect, clip_duration, width, height, fps, intensity)
            inputs.append((v, clip_duration))

        # ── Ensamblar con xfade ───────────────────────────────────────────────
        if len(inputs) == 1:
            video = inputs[0][0]
        else:
            video = inputs[0][0]
            accumulated = inputs[0][1]
            for i in range(1, len(inputs)):
                offset = accumulated - crossfade_duration
                if offset < 0:
                    offset = 0.05
                transition = 'fadeblack' if i % 6 == 0 else 'fade'
                video = ffmpeg.filter(
                    [video, inputs[i][0]], 'xfade',
                    transition=transition,
                    duration=crossfade_duration,
                    offset=offset
                )
                accumulated += inputs[i][1] - crossfade_duration

        # ── Subtítulos (opcional) ─────────────────────────────────────────────
        if subtitle_path and os.path.exists(subtitle_path):
            abs_subtitle_path = os.path.abspath(subtitle_path).replace("\\", "/")
            subtitle_style = _get_subtitle_style(video_format)
            video = video.filter(
                'subtitles',
                abs_subtitle_path,
                force_style=subtitle_style
            )

        # ── Audio y output ────────────────────────────────────────────────────
        if music_path and os.path.exists(music_path):
            music = ffmpeg.input(music_path).audio.filter('volume', 0.15)
            mixed_audio = ffmpeg.filter([audio, music], 'amix', inputs=2, duration='first')
            out = ffmpeg.output(video, mixed_audio, output_path,
                                vcodec='libx264', acodec='aac',
                                pix_fmt='yuv420p', t=duration_sec)
        else:
            out = ffmpeg.output(video, audio, output_path,
                                vcodec='libx264', acodec='aac',
                                pix_fmt='yuv420p', t=duration_sec)

        out.run(overwrite_output=True, capture_stdout=True, capture_stderr=True)

    except ffmpeg.Error as e:
        stderr_output = e.stderr.decode('utf-8') if e.stderr else str(e)
        raise RuntimeError(f"Error ensamblando video con FFmpeg: {stderr_output}")
    except Exception as e:
        raise RuntimeError(f"Error construyendo el video: {e}")
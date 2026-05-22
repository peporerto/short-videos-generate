import os
<<<<<<< HEAD
import subprocess
from typing import List, Optional

FORMAT_CONFIG = {
    "short": {"width": 1080, "height": 1920},
    "long":  {"width": 1920, "height": 1080},
}

EFFECT_SEQUENCE = [
    "zoom_in", "pan_left", "zoom_out", "pan_right",
    "zoom_in_out", "pan_up", "zoom_in", "pan_left",
]

FPS = 30
=======
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
>>>>>>> ca52ab4e061fdd2c4390c50a8e8a2e85a3993e58


def _pick_effect(index: int, override: str = None) -> str:
    if override and override != "zoom_in":
        if index % 4 == 0:
            return EFFECT_SEQUENCE[index % len(EFFECT_SEQUENCE)]
        return override
    return EFFECT_SEQUENCE[index % len(EFFECT_SEQUENCE)]


<<<<<<< HEAD
def _frames_from_durations(
    durations_sec: List[float],
    total_frames: int,
    fps: int,
) -> List[int]:
    """
    Convierte duraciones reales (float) a frames enteros cuya suma
    sea exactamente total_frames, distribuyendo el residuo al mayor decimal.
    """
    raw = [d * fps for d in durations_sec]
    frames = [int(f) for f in raw]
    remainder = total_frames - sum(frames)
    order = sorted(range(len(frames)), key=lambda i: raw[i] - frames[i], reverse=True)
    for j in range(remainder):
        frames[order[j]] += 1
    assert sum(frames) == total_frames, f"Frame mismatch: {sum(frames)} != {total_frames}"
    return frames
=======
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
>>>>>>> ca52ab4e061fdd2c4390c50a8e8a2e85a3993e58


def _get_subtitle_style(video_format: str) -> str:
    if video_format == "long":
<<<<<<< HEAD
        return "FontName=Arial,FontSize=22,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2,Alignment=2,MarginV=60"
    return "FontName=Arial,FontSize=14,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2,Alignment=2,MarginV=40"
=======
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
>>>>>>> ca52ab4e061fdd2c4390c50a8e8a2e85a3993e58


def assemble_video(
    image_paths: List[str],
    audio_path: str,
    subtitle_path: Optional[str],
    output_path: str,
    duration_sec: float,
    music_path: str = None,
    camera_effect: str = "zoom_in",
    effect_list: Optional[List[str]] = None,
<<<<<<< HEAD
    video_format: str = "short",
    segment_audio_paths: Optional[List[str]] = None,
) -> None:
    """
    Ensambla imágenes + audio en un video final.

    Si se provee `segment_audio_paths` (un MP3 por imagen), la duración de
    cada clip se mide directamente del audio real → sincronización perfecta.
    En caso contrario, distribuye el tiempo de forma igual entre los clips.
    """
    from tools.camera import apply_camera_effect
    from tools.tts import get_segment_duration

    num_images = len(image_paths)
    if num_images == 0:
        raise ValueError("No hay imagenes.")

    fmt    = FORMAT_CONFIG.get(video_format, FORMAT_CONFIG["short"])
    width  = fmt["width"]
    height = fmt["height"]
    fps    = FPS

    total_frames = round(duration_sec * fps)

    # ── Calcular frames por clip ──────────────────────────────────
    if segment_audio_paths and len(segment_audio_paths) == num_images:
        print(f"  Midiendo duraciones reales de {num_images} segmentos de audio...")
        seg_durations = []
        for i, seg_path in enumerate(segment_audio_paths):
            d = get_segment_duration(seg_path)
            seg_durations.append(d)
            print(f"    [{i:02d}] {os.path.basename(seg_path)}: {d:.3f}s")
        clip_frames = _frames_from_durations(seg_durations, total_frames, fps)
        print(f"  Suma duraciones segmentos: {sum(seg_durations):.3f}s | Audio total: {duration_sec:.3f}s")
    else:
        if segment_audio_paths:
            print(f"  ADVERTENCIA: segment_audio_paths ({len(segment_audio_paths)}) != imagenes ({num_images}). Distribucion igual.")
        else:
            print("  Sin segmentos de audio — distribucion igual.")
        dur_each = duration_sec / num_images
        clip_frames = _frames_from_durations([dur_each] * num_images, total_frames, fps)

    # ── 1. Pre-render clips ───────────────────────────────────────
    os.makedirs("output/clips", exist_ok=True)
    clip_paths = []
    print(f"\n  Renderizando {num_images} clips...")

    for i, img_path in enumerate(image_paths):
        effect = (
            effect_list[i]
            if (effect_list and i < len(effect_list))
            else _pick_effect(i, camera_effect)
        )
        nf = clip_frames[i]
        print(f"    [{i+1:02d}/{num_images}] {effect} {nf}f ({nf/fps:.3f}s)")

        clip_path = apply_camera_effect(
            image_path=img_path,
            effect=effect,
            num_frames=nf,
            width=width,
            height=height,
            fps=fps,
            output_dir="output/clips",
            clip_index=i,
        )
        clip_paths.append(clip_path)

    # ── 2. Concat demuxer ─────────────────────────────────────────
    concat_list = os.path.abspath("output/clips/concat_list.txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        for cp in clip_paths:
            safe_path = os.path.abspath(cp).replace("\\", "/")
            f.write(f"file '{safe_path}'\n")

    raw_video = os.path.abspath("output/clips/raw_concat.mp4")
    concat_list_safe = concat_list.replace("\\", "/")

    r = subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_list_safe,
        "-c", "copy",
        raw_video.replace("\\", "/"),
    ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    if r.returncode != 0:
        raise RuntimeError(f"Error concat:\n{r.stderr.decode('utf-8', errors='replace')}")

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", raw_video],
        capture_output=True, text=True,
    )
    print(f"\n  Concat: {float(probe.stdout.strip()):.3f}s (esperado {duration_sec:.3f}s)")

    # ── 3. Video + audio final ────────────────────────────────────
    sub_filter = ""
    if subtitle_path and os.path.exists(subtitle_path):
        abs_sub = os.path.abspath(subtitle_path).replace("\\", "/")
        style   = _get_subtitle_style(video_format)
        sub_filter = f",subtitles='{abs_sub}':force_style='{style}'"

    vf = f"eq=contrast=1.05:brightness=-0.02:saturation=0.90{sub_filter}"
    output_abs = os.path.abspath(output_path).replace("\\", "/")

    if music_path and os.path.exists(music_path):
        final_cmd = [
            "ffmpeg", "-y",
            "-i", raw_video,
            "-i", os.path.abspath(audio_path),
            "-i", os.path.abspath(music_path),
            "-filter_complex",
            "[2:a]volume=0.15[m];[1:a][m]amix=inputs=2:duration=first[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-vf", vf,
            "-vcodec", "libx264", "-acodec", "aac",
            "-pix_fmt", "yuv420p", "-r", str(fps),
            "-preset", "medium", "-movflags", "+faststart",
            "-shortest",
            output_abs,
        ]
    else:
        final_cmd = [
            "ffmpeg", "-y",
            "-i", raw_video,
            "-i", os.path.abspath(audio_path),
            "-map", "0:v", "-map", "1:a",
            "-vf", vf,
            "-vcodec", "libx264", "-acodec", "aac",
            "-pix_fmt", "yuv420p", "-r", str(fps),
            "-preset", "medium", "-movflags", "+faststart",
            "-shortest",
            output_abs,
        ]

    r = subprocess.run(final_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if r.returncode != 0:
        raise RuntimeError(f"Error final:\n{r.stderr.decode('utf-8', errors='replace')}")

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", output_abs],
        capture_output=True, text=True,
    )
    print(f"  Video final: {float(probe.stdout.strip()):.3f}s | Audio: {duration_sec:.3f}s")
    print(f"\n  Exportado: {output_path}")
=======
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
>>>>>>> ca52ab4e061fdd2c4390c50a8e8a2e85a3993e58

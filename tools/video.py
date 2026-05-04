import os
import ffmpeg
from typing import List

CAMERA_EFFECTS = {
    "zoom_in":     {"start_scale": 1.0,  "end_scale": 1.08, "x_start": 0.5,  "y_start": 0.5,  "x_end": 0.5,  "y_end": 0.5},
    "zoom_out":    {"start_scale": 1.08, "end_scale": 1.0,  "x_start": 0.5,  "y_start": 0.5,  "x_end": 0.5,  "y_end": 0.5},
    "zoom_in_out": {"start_scale": 1.0,  "end_scale": 1.08, "x_start": 0.5,  "y_start": 0.5,  "x_end": 0.5,  "y_end": 0.5},
    "pan_right":   {"start_scale": 1.08, "end_scale": 1.08, "x_start": 0.46, "y_start": 0.5,  "x_end": 0.54, "y_end": 0.5},
    "pan_left":    {"start_scale": 1.08, "end_scale": 1.08, "x_start": 0.54, "y_start": 0.5,  "x_end": 0.46, "y_end": 0.5},
    "pan_up":      {"start_scale": 1.08, "end_scale": 1.08, "x_start": 0.5,  "y_start": 0.54, "x_end": 0.5,  "y_end": 0.46},
    "pan_down":    {"start_scale": 1.08, "end_scale": 1.08, "x_start": 0.5,  "y_start": 0.46, "x_end": 0.5,  "y_end": 0.54},
}

def _apply_camera_effect(stream, effect_name: str, duration: float, width: int, height: int, fps: int):
    """Aplica efecto de cámara Ken Burns a un stream de video."""
    total_frames = int(duration * fps)

    # Expresiones zoompan usan 'on' para el frame actual (no 'n')
    if effect_name == "zoom_in":
        z = f"min(zoom+0.0008,1.08)"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"

    elif effect_name == "zoom_out":
        z = f"if(eq(on,1),1.08,max(zoom-0.0008,1.0))"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"

    elif effect_name == "zoom_in_out":
        half = total_frames // 2
        z = f"if(lte(on,{half}),min(zoom+0.0008,1.08),max(zoom-0.0008,1.0))"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"

    elif effect_name == "pan_right":
        z = "1.08"
        x = f"if(eq(on,1),0,x+{int(width * 0.08 / total_frames)})"
        y = "ih/2-(ih/zoom/2)"

    elif effect_name == "pan_left":
        z = "1.08"
        x = f"if(eq(on,1),iw*0.08,x-{int(width * 0.08 / total_frames)})"
        y = "ih/2-(ih/zoom/2)"

    elif effect_name == "pan_up":
        z = "1.08"
        x = "iw/2-(iw/zoom/2)"
        y = f"if(eq(on,1),ih*0.08,y-{int(height * 0.08 / total_frames)})"

    elif effect_name == "pan_down":
        z = "1.08"
        x = "iw/2-(iw/zoom/2)"
        y = f"if(eq(on,1),0,y+{int(height * 0.08 / total_frames)})"

    else:
        z = "min(zoom+0.0008,1.08)"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"

    stream = ffmpeg.filter(
        stream, 'zoompan',
        z=z,
        x=x,
        y=y,
        d=total_frames,
        s=f'{width}x{height}',
        fps=fps
    )
    return stream


def assemble_video(
    image_paths: List[str],
    audio_path: str,
    subtitle_path: str,
    output_path: str,
    duration_sec: float,
    music_path: str = None,
    camera_effect: str = "zoom_in"
) -> None:
    """Ensambla imágenes estáticas y audio con efectos de cámara y crossfade usando ffmpeg."""
    try:
        num_images = len(image_paths)
        if num_images == 0:
            raise ValueError("No hay imágenes para ensamblar.")

        crossfade_duration = 0.5
        img_duration = (duration_sec + crossfade_duration * (num_images - 1)) / num_images
        width, height = 1080, 1920
        fps = 30

        abs_subtitle_path = os.path.abspath(subtitle_path).replace("\\", "/")
        audio = ffmpeg.input(audio_path)

        inputs = []
        for img in image_paths:
            v = ffmpeg.input(img, loop=1, t=img_duration).video
            v = ffmpeg.filter(v, 'scale', width * 2, height * 2, force_original_aspect_ratio='increase')
            v = ffmpeg.filter(v, 'crop', width * 2, height * 2)
            v = ffmpeg.filter(v, 'setsar', 1)
            v = _apply_camera_effect(v, camera_effect, img_duration, width, height, fps)
            inputs.append(v)

        if len(inputs) == 1:
            video = inputs[0]
        else:
            video = inputs[0]
            for i in range(1, len(inputs)):
                offset = i * img_duration - i * crossfade_duration
                video = ffmpeg.filter(
                    [video, inputs[i]], 'xfade',
                    transition='fade',
                    duration=crossfade_duration,
                    offset=offset
                )

        video = video.filter(
            'subtitles',
            abs_subtitle_path,
            force_style='FontName=Arial,FontSize=18,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2,Alignment=2'
        )

        if music_path and os.path.exists(music_path):
            music = ffmpeg.input(music_path).audio.filter('volume', 0.15)
            mixed_audio = ffmpeg.filter([audio, music], 'amix', inputs=2, duration='first')
            out = ffmpeg.output(video, mixed_audio, output_path, vcodec='libx264', acodec='aac', pix_fmt='yuv420p', t=duration_sec)
        else:
            out = ffmpeg.output(video, audio, output_path, vcodec='libx264', acodec='aac', pix_fmt='yuv420p', t=duration_sec)

        out.run(overwrite_output=True, capture_stdout=True, capture_stderr=True)

    except ffmpeg.Error as e:
        stderr_output = e.stderr.decode('utf-8') if e.stderr else str(e)
        raise RuntimeError(f"Error ensamblando video con FFmpeg: {stderr_output}")
    except Exception as e:
        raise RuntimeError(f"Error construyendo el video: {e}")
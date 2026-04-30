import os
import ffmpeg
from typing import List

def assemble_video(image_paths: List[str], audio_path: str, subtitle_path: str, output_path: str, duration_sec: float) -> None:
    """Ensambla imágenes estáticas y audio con crossfade usando ffmpeg."""
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
            v = ffmpeg.filter(v, 'scale', width, height, force_original_aspect_ratio='increase')
            v = ffmpeg.filter(v, 'crop', width, height)
            v = ffmpeg.filter(v, 'setsar', 1)
            v = ffmpeg.filter(v, 'fps', fps=fps)
            inputs.append(v)

        if len(inputs) == 1:
            video = inputs[0]
        else:
            video = inputs[0]
            for i in range(1, len(inputs)):
                offset = i * img_duration - i * crossfade_duration
                video = ffmpeg.filter([video, inputs[i]], 'xfade', transition='fade', duration=crossfade_duration, offset=offset)

        video = video.filter(
            'subtitles',
            abs_subtitle_path,
            force_style='FontName=Arial,FontSize=18,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2,Alignment=2'
        )

        out = ffmpeg.output(
            video, audio, output_path,
            vcodec='libx264',
            acodec='aac',
            pix_fmt='yuv420p',
            t=duration_sec
        )
        out.run(overwrite_output=True, capture_stdout=True, capture_stderr=True)

    except ffmpeg.Error as e:
        stderr_output = e.stderr.decode('utf-8') if e.stderr else str(e)
        raise RuntimeError(f"Error ensamblando video con FFmpeg: {stderr_output}")
    except Exception as e:
        raise RuntimeError(f"Error construyendo el video: {e}")
import os
import subprocess

EFFECT_PARAMS = {
    "zoom_in":     ("min(zoom+0.0006,1.06)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
    "zoom_out":    ("if(eq(on,1),1.06,max(zoom-0.0006,1.0))", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
    "zoom_in_out": ("min(zoom+0.0006,1.06)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
    "pan_right":   ("1.06", "min(iw*0.06,x+2)", "ih/2-(ih/zoom/2)"),
    "pan_left":    ("1.06", "max(0,x-2)",        "ih/2-(ih/zoom/2)"),
    "pan_up":      ("1.06", "iw/2-(iw/zoom/2)",  "max(0,y-2)"),
    "pan_down":    ("1.06", "iw/2-(iw/zoom/2)",  "min(ih*0.06,y+2)"),
}


def apply_camera_effect(
    image_path: str,
    effect: str,
    num_frames: int,          # <-- frames exactos, no segundos
    width: int,
    height: int,
    fps: int = 30,
    output_dir: str = "output/clips",
    clip_index: int = 0       # <-- índice para evitar colisiones de nombre
) -> str:
    os.makedirs(output_dir, exist_ok=True)

    z, x, y = EFFECT_PARAMS.get(effect, EFFECT_PARAMS["zoom_in"])

    # nombre único por índice, no por nombre de archivo
    output_path = os.path.join(output_dir, f"clip_{clip_index:04d}_{effect}.mp4")

    vf = (
        f"scale={width*2}:{height*2}:force_original_aspect_ratio=increase,"
        f"crop={width*2}:{height*2},"
        f"setsar=1,"
        f"zoompan=z='{z}':x='{x}':y='{y}':d={num_frames}:s={width}x{height}:fps={fps},"
        f"setpts=PTS-STARTPTS"
    )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
        "-vf", vf,
        "-vcodec", "libx264",
        "-pix_fmt", "yuv420p",
        "-r", str(fps),
        "-frames:v", str(num_frames),   # frames exactos, no -t
        "-preset", "fast",
        "-tune", "stillimage",
        output_path
    ]

    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg error clip {clip_index}:\n"
            f"{result.stderr.decode('utf-8', errors='replace')}"
        )

    return output_path
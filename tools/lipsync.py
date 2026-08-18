import os
import subprocess
import json
from PIL import Image
from typing import Dict


def convert_mp3_to_wav(mp3_path: str, wav_path: str) -> None:
    """Convierte un MP3 a WAV PCM de 16 bits y 44.1kHz mono para Rhubarb."""
    cmd = [
        "ffmpeg", "-y",
        "-i", mp3_path,
        "-ar", "44100",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        wav_path
    ]
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if r.returncode != 0:
        raise RuntimeError(f"Error convirtiendo MP3 a WAV:\n{r.stderr.decode('utf-8')}")


def run_rhubarb(wav_path: str, rhubarb_bin: str) -> dict:
    """Corre Rhubarb en español y retorna el JSON parseado."""
    actual_bin = rhubarb_bin
    
    # Agregar extensión .exe en Windows si no está presente
    if os.name == 'nt' and not actual_bin.lower().endswith('.exe'):
        if os.path.exists(actual_bin + '.exe'):
            actual_bin += '.exe'

    if not os.path.exists(actual_bin):
        from shutil import which
        basename = os.path.basename(rhubarb_bin)
        system_bin = which(basename) or which(basename + ".exe")
        if system_bin:
            actual_bin = system_bin
        else:
            raise RuntimeError(
                f"Rhubarb no encontrado en '{rhubarb_bin}' ni en el PATH del sistema. "
                "Descárgalo de https://github.com/DanielSWolf/rhubarb-lip-sync/releases"
            )

    output_json_path = wav_path + ".timing.json"
    cmd = [
        actual_bin,
        "-f", "json",
        "-o", output_json_path,
        "--recognizer", "phonetic",
        wav_path
    ]
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if r.returncode != 0:
        raise RuntimeError(f"Error ejecutando Rhubarb:\n{r.stderr.decode('utf-8')}")

    with open(output_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if os.path.exists(output_json_path):
        os.remove(output_json_path)

    return data


def normalize_mouth_images(
    mascota_dir: str,
    mouth_map: Dict[str, str],
    target_size: tuple,
    output_dir: str
) -> Dict[str, str]:
    """
    Asegura que cada una de las imágenes de la boca esté normalizada (redimensionada y centrada)
    al tamaño del video de salida (1080x1920 o 1920x1080) para que FFmpeg concat no falle.
    """
    os.makedirs(output_dir, exist_ok=True)
    normalized_paths = {}

    for cue, filename in mouth_map.items():
        src_path = os.path.join(mascota_dir, filename)
        if not os.path.exists(src_path):
            raise FileNotFoundError(f"Imagen de boca para cue '{cue}' no encontrada en '{src_path}'")

        out_path = os.path.join(output_dir, f"norm_mouth_{cue}.png")
        
        img = Image.open(src_path).convert("RGBA")
        tw, th = target_size
        iw, ih = img.size
        
        scale = min(tw / iw, th / ih)
        new_w, new_h = int(iw * scale), int(ih * scale)
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        
        bg = Image.new("RGBA", target_size, (0, 0, 0, 0))
        bg.paste(resized, ((tw - new_w) // 2, (th - new_h) // 2))
        bg.save(out_path)
        
        normalized_paths[cue] = out_path

    return normalized_paths


def generate_lipsync_video(
    audio_path: str,
    output_path: str,
    mascota_dir: str,
    rhubarb_bin: str,
    mouth_map: Dict[str, str],
    video_format: str = "short",
    fps: int = 30
) -> None:
    """Flujo completo para crear el video de la mascota sincronizada."""
    format_sizes = {"short": (1080, 1920), "long": (1920, 1080)}
    target_size = format_sizes.get(video_format, (1080, 1920))

    wav_path = audio_path + ".wav"
    convert_mp3_to_wav(audio_path, wav_path)

    try:
        timing_data = run_rhubarb(wav_path, rhubarb_bin)
        cues = timing_data.get("mouthCues", [])
        
        norm_dir = os.path.join(os.path.dirname(output_path), "normalized_mascota")
        mouth_paths = normalize_mouth_images(mascota_dir, mouth_map, target_size, norm_dir)

        concat_file = output_path + ".concat_list.txt"
        with open(concat_file, "w", encoding="utf-8") as f:
            for cue in cues:
                duration = cue["end"] - cue["start"]
                if duration <= 0:
                    continue
                img_path = mouth_paths.get(cue["value"], mouth_paths.get("X"))
                if not img_path:
                    img_path = list(mouth_paths.values())[0]
                
                safe_path = os.path.abspath(img_path).replace("\\", "/")
                f.write(f"file '{safe_path}'\n")
                f.write(f"duration {duration:.3f}\n")
            
            if cues:
                last_cue = cues[-1]
                img_path = mouth_paths.get(last_cue["value"], mouth_paths.get("X")) or list(mouth_paths.values())[0]
                safe_path = os.path.abspath(img_path).replace("\\", "/")
                f.write(f"file '{safe_path}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-r", str(fps),
            output_path
        ]
        r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        
        if os.path.exists(concat_file):
            os.remove(concat_file)
            
        if r.returncode != 0:
            raise RuntimeError(f"Error generando video lip-sync con FFmpeg:\n{r.stderr.decode('utf-8')}")

    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)

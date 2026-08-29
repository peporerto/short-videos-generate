import asyncio
import edge_tts
import subprocess
import os
from typing import List, Union


def _normalize_rate(rate: Union[str, int, float]) -> str:
    """Asegura que el rate esté en el formato esperado por edge-tts (ej. '+10%' o '-10%')."""
    if rate is None:
        return "-10%"
    
    if isinstance(rate, (int, float)):
        if rate >= 0:
            return f"+{int(rate)}%"
        else:
            return f"{int(rate)}%"
            
    rate_str = str(rate).strip()
    if not rate_str.endswith("%"):
        rate_str += "%"
    if not rate_str.startswith("+") and not rate_str.startswith("-"):
        rate_str = "+" + rate_str
    return rate_str


async def generate_audio(text: str, output_path: str, voice: str = "es-CO-GonzaloNeural", rate: Union[str, int, float] = "-10%") -> None:
    """Genera audio a partir de texto usando edge-tts en español."""
    try:
        norm_rate = _normalize_rate(rate)
        communicate = edge_tts.Communicate(text, voice, rate=norm_rate)
        await communicate.save(output_path)
    except Exception as e:
        raise RuntimeError(f"Error generando audio con edge-tts: {e}")


async def _generate_one(text: str, path: str, voice: str, rate: Union[str, int, float] = "-10%") -> str:
    norm_rate = _normalize_rate(rate)
    communicate = edge_tts.Communicate(text, voice, rate=norm_rate)
    await communicate.save(path)
    return path


async def generate_audio_segments(
    segments: List[str],
    output_dir: str,
    voice: str = "es-CO-GonzaloNeural",
    rate: Union[str, int, float] = "-10%",
) -> List[str]:
    """
    Genera un MP3 por cada segmento en paralelo (asyncio.gather).
    Retorna la lista de rutas en el mismo orden que `segments`.
    Los archivos se regeneran siempre para evitar datos obsoletos.
    """
    os.makedirs(output_dir, exist_ok=True)
    paths = [os.path.join(output_dir, f"seg_{i:03d}.mp3") for i in range(len(segments))]
    tasks = [_generate_one(text, path, voice, rate=rate) for text, path in zip(segments, paths)]
    await asyncio.gather(*tasks)
    return paths


def get_segment_duration(audio_path: str) -> float:
    """Devuelve la duración en segundos de un archivo de audio usando ffprobe."""
    r = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path,
        ],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe error en {audio_path}: {r.stderr.strip()}")
    return float(r.stdout.strip())


def concat_audio_segments(segment_paths: List[str], output_path: str) -> str:
    """
    Concatena mini-MP3 en un solo archivo usando ffmpeg concat demuxer.
    Retorna la ruta del archivo final.
    """
    list_file = output_path + ".concat_list.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for p in segment_paths:
            safe = os.path.abspath(p).replace("\\", "/")
            f.write(f"file '{safe}'\n")

    r = subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", list_file,
            "-c", "copy",
            output_path,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    os.remove(list_file)
    if r.returncode != 0:
        raise RuntimeError(
            f"Error concatenando audios:\n{r.stderr.decode('utf-8', errors='replace')}"
        )
    return output_path

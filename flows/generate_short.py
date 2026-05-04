import os
import sys
import asyncio
import yaml
import ffmpeg
import argparse
import time
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tools.script import generate_script
from tools.tts import generate_audio
from tools.srt import generate_srt
from tools.images import generate_image
from tools.video import assemble_video

def log(msg: str, start: float = None) -> float:
    """Imprime un mensaje con tiempo transcurrido opcional."""
    elapsed = f" ({time.time() - start:.1f}s)" if start else ""
    print(f"[{time.strftime('%H:%M:%S')}] {msg}{elapsed}")
    return time.time()

def get_audio_duration(audio_path: str) -> float:
    """Obtiene la duración del archivo de audio usando ffprobe."""
    try:
        probe = ffmpeg.probe(audio_path)
        return float(probe['format']['duration'])
    except Exception as e:
        raise RuntimeError(f"Error obteniendo duración del audio: {e}")

async def main() -> None:
    """Flujo principal para orquestar la generación de videos cortos."""
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--niche", type=str, default=None)
    parser.add_argument("--prompt", type=str, default=None)
    args = parser.parse_args()

    config_path = "config.yaml"
    if not os.path.exists(config_path):
        raise RuntimeError(f"Falta el archivo de configuración: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    # Resolver nicho
    niche = args.niche or "ai_tech"
    niche_config = config.get("nichos", {}).get(niche)
    if not niche_config:
        raise RuntimeError(f"Nicho '{niche}' no encontrado en config.yaml. Nichos disponibles: {list(config.get('nichos', {}).keys())}")

    image_style = niche_config.get("image_style", "cinematic photorealistic, 4k")
    music_path = niche_config.get("music")
    voice = niche_config.get("voice", "es-CO-GonzaloNeural")

    # Resolver prompt/topic
    if args.prompt and args.prompt.strip():
        topic = args.prompt.strip()
    elif os.path.exists("input/prompt.txt"):
        with open("input/prompt.txt", "r", encoding="utf-8") as f:
            topic = f.read().strip()
    else:
        topic = config.get("default_topic", "Inteligencia artificial")

    total_start = time.time()
    log(f"Nicho: {niche} | Tema: {topic}")

    t = log("Generando guion...")
    script_data = generate_script(topic, image_style)
    full_text = " ".join([
        script_data.get(key, {}).get("text", "")
        for key in ["hook", "context", "value", "outro"]
    ])
    log("Guion generado", t)

    t = log("Generando audio TTS...")
    audio_path = "output/audio.mp3"
    await generate_audio(full_text, audio_path, voice=voice)
    duration = get_audio_duration(audio_path)
    log(f"Audio generado — {duration:.1f}s", t)

    t = log("Generando subtítulos...")
    srt_path = "output/subtitles.srt"
    generate_srt(audio_path, srt_path)
    log("Subtítulos generados", t)

    log("Verificando imágenes...")
    image_paths = sorted([
        f"input/{f}" for f in os.listdir("input")
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ])

    if image_paths:
        log(f"Modo A: usando {len(image_paths)} imágenes de input/")
    else:
        log("Modo B: generando imágenes con IA...")
        keys = ["hook", "context", "value", "outro"]
        for i, key in enumerate(keys):
            img_prompt = script_data.get(key, {}).get(
                "image_prompt",
                f"A visual representation of {topic}, {image_style}"
            )
            img_path = f"output/image_{i}.png"
            t = log(f"  Imagen {i+1}/4...")
            generate_image(img_prompt, img_path)
            log(f"  Imagen {i+1}/4 lista", t)
            image_paths.append(img_path)

    t = log("Ensamblando video...")
    output_video = "output/final_short.mp4"
    camera_effect = niche_config.get("camera_effect", "zoom_in")
    assemble_video(image_paths, audio_path, srt_path, output_video, duration, music_path=music_path, camera_effect=camera_effect)
    log("Video ensamblado", t)

    log(f"¡Video generado en output/final_short.mp4! — Total", total_start)

if __name__ == "__main__":
    os.makedirs("input", exist_ok=True)
    os.makedirs("output", exist_ok=True)
    asyncio.run(main())
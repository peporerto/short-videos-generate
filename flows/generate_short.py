import os
import sys
import asyncio
import yaml
import ffmpeg
import argparse
import time
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tools.script import generate_script, get_script_sections, get_all_image_prompts
from tools.tts import generate_audio, generate_audio_segments, concat_audio_segments
from tools.images import generate_image
from tools.video import assemble_video
from tools.normalizer import normalize_images


def log(msg: str, start: float = None) -> float:
    elapsed = f" ({time.time() - start:.1f}s)" if start else ""
    print(f"[{time.strftime('%H:%M:%S')}] {msg}{elapsed}")
    return time.time()


def get_audio_duration(audio_path: str) -> float:
    try:
        probe = ffmpeg.probe(audio_path)
        return float(probe['format']['duration'])
    except Exception as e:
        raise RuntimeError(f"Error obteniendo duración del audio: {e}")


def _load_segments_file(path: str):
    """Lee input/segments.txt, ignora comentarios y líneas vacías."""
    if not os.path.exists(path):
        return []
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                out.append(line)
    return out


def read_prompts_file(filepath: str, default_effect: str = "zoom_in"):
    prompt_list = []
    effect_list = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "|" in line:
                parts = line.split("|", 1)
                prompt_list.append(parts[0].strip())
                effect_list.append(parts[1].strip())
            else:
                prompt_list.append(line)
                effect_list.append(default_effect)
    return prompt_list, effect_list


def collect_numbered_files(folder: str, extensions: tuple) -> list:
    if not os.path.exists(folder):
        return []
    files = []
    for f in os.listdir(folder):
        if f.lower().endswith(extensions):
            files.append(os.path.join(folder, f))
    return sorted(files)


async def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--niche",    type=str, default=None)
    parser.add_argument("--prompt",   type=str, default=None)
    parser.add_argument("--duration", type=str, default=None,
                        choices=["short", "medium"])
    parser.add_argument("--mode",     type=str, default=None,
                        choices=["informative", "second_person"])
    parser.add_argument("--format",   type=str, default=None,
                        choices=["short", "long"])
    args = parser.parse_args()

    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    niche = args.niche or "ai_tech"
    niche_config = config.get("nichos", {}).get(niche)
    if not niche_config:
        raise RuntimeError(
            f"Nicho '{niche}' no encontrado. "
            f"Disponibles: {list(config.get('nichos', {}).keys())}"
        )

    image_style    = niche_config.get("image_style", "cinematic 2D illustration")
    music_path     = niche_config.get("music")
    voice          = niche_config.get("voice", "es-CO-GonzaloNeural")
    camera_effect  = niche_config.get("camera_effect", "zoom_in")
    duration       = args.duration or niche_config.get("duration", "short")
    narrative_mode = args.mode     or niche_config.get("narrative_mode", "informative")
    video_format   = args.format or niche_config.get("format", "short")

    # Resolución según formato
    format_sizes = {"short": (1080, 1920), "long": (1920, 1080)}
    target_size  = format_sizes.get(video_format, (1920, 1080))

    total_start = time.time()
    log(f"Nicho: {niche} | Duración: {duration} | Formato: {video_format} | Resolución: {target_size[0]}x{target_size[1]}")

    # ── Resolver guión ────────────────────────────────────────────────────────
    script_from_file = False
    full_text = None
    script_data = None

    if os.path.exists("input/script.txt"):
        with open("input/script.txt", "r", encoding="utf-8") as f:
            full_text = f.read().strip()
        topic = full_text[:80].replace("\n", " ")
        script_from_file = True
        log(f"Script manual cargado ({len(full_text.split())} palabras)")

    elif args.prompt and args.prompt.strip():
        topic = args.prompt.strip()

    elif os.path.exists("input/prompt.txt"):
        with open("input/prompt.txt", "r", encoding="utf-8") as f:
            topic = f.read().strip()

    else:
        topic = config.get("default_topic", "Inteligencia artificial")

    log(f"Tema: {topic[:80]}")

    if not script_from_file:
        t = log("Generando guión con Gemini...")
        script_data = generate_script(topic, image_style, duration, narrative_mode)
        sections = get_script_sections(duration)
        full_text = " ".join([
            script_data.get(key, {}).get("text", "")
            for key in sections
        ])
        log("Guión generado", t)

    # ── Audio ─────────────────────────────────────────────────────────────────
    audio_path = "output/audio.mp3"
    srt_path = None
    segment_audio_paths = None

    segments_file = _load_segments_file("input/segments.txt")

    # Calcular cuántas imágenes habrá (para validar contra segments.txt)
    # En este punto aún no tenemos image_paths, pero podemos anticipar:
    # si hay segments.txt lo usaremos después de tener image_paths.
    # Por ahora generamos siempre el audio completo.
    t = log("Generando audio TTS...")
    await generate_audio(full_text, audio_path, voice=voice)
    duration_sec = get_audio_duration(audio_path)
    log(f"Audio generado — {duration_sec:.1f}s", t)

    # ── Imágenes ──────────────────────────────────────────────────────────────
    log("Verificando assets de imágenes...")
    effect_list = None
    image_paths = []

    manual_images = collect_numbered_files(
        "input/images", (".jpg", ".jpeg", ".png")
    )

    if not manual_images:
        manual_images = collect_numbered_files(
            "input", (".jpg", ".jpeg", ".png")
        )

    if manual_images:
        log(f"Modo A — imágenes manuales: {len(manual_images)}")
        image_paths = manual_images

    elif os.path.exists("input/prompts.txt"):
        prompt_list, effect_list = read_prompts_file("input/prompts.txt", camera_effect)
        log(f"Modo B — prompts.txt: {len(prompt_list)} imágenes...")
        image_paths = []
        for i, img_prompt in enumerate(prompt_list):
            img_path = f"output/image_{i:02d}.png"
            t = log(f"  Imagen {i+1}/{len(prompt_list)} [{effect_list[i]}]...")
            generate_image(img_prompt, img_path)
            log(f"  Imagen {i+1}/{len(prompt_list)} lista", t)
            image_paths.append(img_path)

    else:
        if script_data is None:
            raise RuntimeError(
                "No hay imágenes en input/, input/prompts.txt ni script_data. "
                "Agrega imágenes o usa --prompt."
            )
        all_prompts = get_all_image_prompts(script_data, duration)
        log(f"Modo B automático — {len(all_prompts)} imágenes...")
        image_paths = []
        for i, img_prompt in enumerate(all_prompts):
            img_path = f"output/image_{i:02d}.png"
            t = log(f"  Imagen {i+1}/{len(all_prompts)}...")
            generate_image(img_prompt, img_path)
            log(f"  Imagen {i+1}/{len(all_prompts)} lista", t)
            image_paths.append(img_path)

    # ── Normalizar imágenes ───────────────────────────────────────────────────
    t = log(f"Normalizando {len(image_paths)} imágenes a {target_size[0]}x{target_size[1]}...")
    image_paths = normalize_images(image_paths, target_size=target_size)
    log("Imágenes normalizadas", t)

    # ── Audio por segmento (sincronización perfecta) ───────────────────────────
    if segments_file and len(segments_file) == len(image_paths):
        t = log(f"Generando {len(segments_file)} audios por segmento (paralelo)...")
        seg_dir = "output/segments"
        segment_audio_paths = await generate_audio_segments(
            segments_file, seg_dir, voice=voice
        )
        # Reemplazar el audio.mp3 con la concatenación exacta de los segmentos
        concat_audio_segments(segment_audio_paths, audio_path)
        duration_sec = get_audio_duration(audio_path)
        log(f"Audios por segmento listos — total {duration_sec:.1f}s", t)
    elif segments_file:
        log(
            f"ADVERTENCIA: segments.txt tiene {len(segments_file)} líneas "
            f"pero hay {len(image_paths)} imágenes. Se usará distribución igual."
        )

    # ── Ensamblar ─────────────────────────────────────────────────────────────
    t = log("Ensamblando video...")
    output_video = "output/final_video.mp4"
    assemble_video(
        image_paths, audio_path, srt_path,
        output_video, duration_sec,
        music_path=music_path,
        camera_effect=camera_effect,
        effect_list=effect_list,
        video_format=video_format,
        segment_audio_paths=segment_audio_paths,
    )
    log(f"Video generado en output/final_video.mp4 — Total", total_start)


if __name__ == "__main__":
    os.makedirs("input", exist_ok=True)
    os.makedirs("input/images", exist_ok=True)
    os.makedirs("input/audio", exist_ok=True)
    os.makedirs("output", exist_ok=True)
    asyncio.run(main())
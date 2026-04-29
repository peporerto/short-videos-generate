import os
import sys
import asyncio
import yaml
import ffmpeg
from dotenv import load_dotenv
 
# Garantiza que la raíz del proyecto esté en el path independientemente
# de desde dónde se ejecute el script
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
 
from tools.script import generate_script
from tools.tts import generate_audio
from tools.srt import generate_srt
from tools.images import generate_image
from tools.video import assemble_video
 
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
    
    config_path = "config.yaml"
    if not os.path.exists(config_path):
        raise RuntimeError(f"Falta el archivo de configuración: {config_path}")
        
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
        
    topic = "Inteligencia artificial"
    if os.path.exists("input/prompt.txt"):
        with open("input/prompt.txt", "r", encoding="utf-8") as f:
            topic = f.read().strip()
    else:
        topic = config.get("default_topic", topic)
    
    print(f"Generando guion para: {topic}")
    script_data = generate_script(topic)
    full_text = f"{script_data.get('hook', '')} {script_data.get('context', '')} {script_data.get('value', '')} {script_data.get('outro', '')}"
    
    print("Generando audio TTS...")
    audio_path = "output/audio.mp3"
    await generate_audio(full_text, audio_path)
    
    duration = get_audio_duration(audio_path)
    print(f"Duración del audio: {duration:.2f}s")
    
    print("Generando SRT...")
    srt_path = "output/subtitles.srt"
    generate_srt(full_text, duration, srt_path)
    
    print("Generando imágenes...")
    image_paths = []
    keys = ["hook", "context", "value", "outro"]
    for i, key in enumerate(keys):
        img_prompt = config.get("image_prompts", {}).get(key, f"A visual representation of {topic}, cinematic 4k")
        img_path = f"output/image_{i}.png"
        generate_image(img_prompt, img_path)
        image_paths.append(img_path)
        
    print("Ensamblando video...")
    output_video = "output/final_short.mp4"
    assemble_video(image_paths, audio_path, srt_path, output_video, duration)
    print("¡Video generado con éxito en output/final_short.mp4!")
 
if __name__ == "__main__":
    os.makedirs("input", exist_ok=True)
    os.makedirs("output", exist_ok=True)
    asyncio.run(main())
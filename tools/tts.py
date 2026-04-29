import edge_tts
import aiofiles

async def generate_audio(text: str, output_path: str) -> None:
    """Genera audio a partir de texto usando edge-tts en español."""
    try:
        communicate = edge_tts.Communicate(text, "es-CO-GonzaloNeural", rate="-10%")
        await communicate.save(output_path)
    except Exception as e:
        raise RuntimeError(f"Error generando audio con edge-tts: {e}")

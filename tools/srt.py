import whisper

def generate_srt(audio_path: str, output_path: str) -> None:
    """Genera un archivo SRT con timestamps reales usando Whisper."""
    try:
        model = whisper.load_model("small")
        result = model.transcribe(audio_path, language="es", word_timestamps=True)

        with open(output_path, "w", encoding="utf-8") as f:
            index = 1
            for segment in result["segments"]:
                words = segment.get("words", [])
                chunk = []
                chunk_start = None

                for word in words:
                    if chunk_start is None:
                        chunk_start = word["start"]
                    chunk.append(word["word"].strip())

                    if len(chunk) >= 4:
                        start_str = _format_time(chunk_start)
                        end_str = _format_time(word["end"])
                        f.write(f"{index}\n{start_str} --> {end_str}\n{' '.join(chunk)}\n\n")
                        index += 1
                        chunk = []
                        chunk_start = None

                if chunk:
                    end_time = words[-1]["end"] if words else segment["end"]
                    start_str = _format_time(chunk_start)
                    end_str = _format_time(end_time)
                    f.write(f"{index}\n{start_str} --> {end_str}\n{' '.join(chunk)}\n\n")
                    index += 1

    except Exception as e:
        raise RuntimeError(f"Error generando SRT con Whisper: {e}")

def _format_time(seconds: float) -> str:
    """Formatea segundos a formato de tiempo SRT."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
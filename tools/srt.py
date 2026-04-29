import math

def generate_srt(text: str, audio_duration_seconds: float, output_path: str) -> None:
    """Genera un archivo SRT calculando tiempos desde el texto y la duración total."""
    try:
        words = text.split()
        if not words:
            raise ValueError("El texto está vacío.")
        
        words_per_second = len(words) / audio_duration_seconds
        
        with open(output_path, "w", encoding="utf-8") as f:
            chunk_size = 4  # palabras por subtítulo
            for i in range(0, len(words), chunk_size):
                chunk = words[i:i + chunk_size]
                start_time_sec = i / words_per_second
                end_time_sec = (i + len(chunk)) / words_per_second
                
                # Formato SRT: HH:MM:SS,mmm
                start_str = _format_time(start_time_sec)
                end_str = _format_time(end_time_sec)
                
                index = (i // chunk_size) + 1
                f.write(f"{index}\n")
                f.write(f"{start_str} --> {end_str}\n")
                f.write(f"{' '.join(chunk)}\n\n")
    except Exception as e:
        raise RuntimeError(f"Error generando archivo SRT: {e}")

def _format_time(seconds: float) -> str:
    """Formatea segundos a formato de tiempo SRT."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

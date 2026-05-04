import os
import time
import requests
from urllib.parse import quote

def generate_image(prompt: str, output_path: str) -> None:
    """Genera una imagen usando Pollinations.ai (gratuito, sin autenticación)."""
    encoded_prompt = quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&nologo=true"

    max_retries = 3
    base_delay = 3.0

    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=90)
            response.raise_for_status()

            with open(output_path, "wb") as f:
                f.write(response.content)
            time.sleep(2)
            return

        except Exception as e:
            if attempt == max_retries - 1:
                raise RuntimeError(f"Error generando imagen tras {max_retries} intentos: {e}")
            print(f"Intento {attempt + 1} fallido, reintentando...")
            time.sleep(base_delay ** attempt)
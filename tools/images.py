import os
import time
import requests

def generate_image(prompt: str, output_path: str) -> None:
    """Genera una imagen usando HuggingFace Inference API con reintentos y delay."""
    api_key = os.getenv("HUGGINGFACE_API_KEY")
    if not api_key:
        raise ValueError("HUGGINGFACE_API_KEY no configurada.")
        
    url = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {"inputs": prompt}
    
    max_retries = 3
    base_delay = 2.0
    
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=45)
            response.raise_for_status()
            
            with open(output_path, "wb") as f:
                f.write(response.content)
            return  # Éxito
            
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise RuntimeError(f"Error generando imagen tras {max_retries} intentos: {e}")
            time.sleep(base_delay ** attempt)

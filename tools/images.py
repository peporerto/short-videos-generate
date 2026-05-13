import os
import time
import math
import requests
from urllib.parse import quote
from PIL import Image
import cv2
import numpy as np


# ── Configuración ─────────────────────────────────────────────────────────────
PANEL_WIDTH  = 1080
PANEL_HEIGHT = 1920
MAX_PANELS_PER_MURAL = 9  # máximo de paneles por lote


# ── Generación de imagen en Pollinations ──────────────────────────────────────

def _fetch_image(url: str, output_path: str, max_retries: int = 3) -> None:
    """Descarga una imagen desde una URL y la guarda en output_path."""
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
            print(f"  Intento {attempt + 1} fallido, reintentando en {base_delay ** attempt:.0f}s...")
            time.sleep(base_delay ** attempt)


def generate_image(prompt: str, output_path: str) -> None:
    """
    Genera una imagen individual usando Pollinations.ai.
    Resolución: 1080x1920 (vertical short).
    """
    encoded_prompt = quote(prompt)
    url = (
        f"https://image.pollinations.ai/prompt/{encoded_prompt}"
        f"?width={PANEL_WIDTH}&height={PANEL_HEIGHT}&nologo=true"
    )
    _fetch_image(url, output_path)


# ── Mural — generación, corte y upscale ──────────────────────────────────────

def _build_mural_prompt(panel_prompts: list, start_index: int = 0) -> str:
    """
    Convierte una lista de prompts de paneles en un único prompt maestro
    que describe una cuadrícula de paneles estilo cómic.

    Args:
        panel_prompts: Lista de prompts individuales por panel
        start_index:   Índice global del primer panel (para numeración correcta en lotes)
    """
    n = len(panel_prompts)
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)

    panel_descriptions = []
    for i, prompt in enumerate(panel_prompts):
        row = i // cols + 1
        col = i % cols + 1
        global_index = start_index + i + 1
        panel_descriptions.append(
            f"Panel {global_index} (row {row}, column {col}): {prompt}"
        )

    panels_text = ". ".join(panel_descriptions)

    return (
        f"Comic book style image grid with {rows} rows and {cols} columns, "
        f"{n} panels total, thick black borders separating each panel, "
        f"each panel is a separate scene, consistent character design across all panels, "
        f"high quality 2D animation, flat vibrant colors, thick black outlines, "
        f"Family Guy GTA animated style, theater director wide shot in each panel. "
        f"{panels_text}. "
        f"No text, no watermarks, no speech bubbles, clean grid layout."
    )


def _generate_mural(prompt: str, output_path: str, n_panels: int) -> None:
    """
    Genera una imagen de mural con múltiples paneles en Pollinations.
    La resolución se escala según el número de paneles.
    """
    cols = math.ceil(math.sqrt(n_panels))
    rows = math.ceil(n_panels / cols)

    mural_width  = PANEL_WIDTH  * cols
    mural_height = PANEL_HEIGHT * rows

    # Limitar resolución máxima para que Pollinations no falle
    max_dim = 4096
    scale = min(max_dim / mural_width, max_dim / mural_height, 1.0)
    req_width  = int(mural_width  * scale)
    req_height = int(mural_height * scale)

    encoded_prompt = quote(prompt)
    url = (
        f"https://image.pollinations.ai/prompt/{encoded_prompt}"
        f"?width={req_width}&height={req_height}&nologo=true"
    )
    _fetch_image(url, output_path)


def _cut_mural(mural_path: str, n_panels: int, output_dir: str, start_index: int = 0) -> list:
    """
    Corta el mural en paneles individuales.

    Args:
        mural_path:  Ruta de la imagen del mural
        n_panels:    Número de paneles esperados
        output_dir:  Carpeta donde guardar los paneles
        start_index: Índice global del primer panel (para lotes)

    Returns:
        Lista de rutas de los paneles cortados
    """
    img = Image.open(mural_path)
    mural_w, mural_h = img.size

    cols = math.ceil(math.sqrt(n_panels))
    rows = math.ceil(n_panels / cols)

    panel_w = mural_w // cols
    panel_h = mural_h // rows

    paths = []
    for i in range(n_panels):
        row = i // cols
        col = i % cols

        left   = col * panel_w
        top    = row * panel_h
        right  = left + panel_w
        bottom = top  + panel_h

        panel = img.crop((left, top, right, bottom))
        global_index = start_index + i
        panel_path = os.path.join(output_dir, f"image_{global_index:02d}.png")
        panel.save(panel_path)
        paths.append(panel_path)

    return paths


def _upscale_panel(image_path: str, target_width: int = 1080, target_height: int = 1920) -> None:
    """
    Sube la calidad del panel usando OpenCV:
    - Redimensiona a resolución objetivo con interpolación Lanczos
    - Aplica leve sharpening para compensar pérdida de detalle del corte
    """
    img = cv2.imread(image_path)
    if img is None:
        raise RuntimeError(f"No se pudo leer la imagen: {image_path}")

    # Redimensionar a resolución objetivo
    resized = cv2.resize(img, (target_width, target_height), interpolation=cv2.INTER_LANCZOS4)

    # Sharpening leve
    kernel = np.array([
        [ 0, -0.5,  0],
        [-0.5,  3, -0.5],
        [ 0, -0.5,  0]
    ])
    sharpened = cv2.filter2D(resized, -1, kernel)

    cv2.imwrite(image_path, sharpened)


# ── API pública ───────────────────────────────────────────────────────────────

def generate_images_from_prompts(
    prompt_list: list,
    output_dir: str,
    start_index: int = 0
) -> list:
    """
    Genera imágenes a partir de una lista de prompts usando el método de mural.
    Procesa en lotes de MAX_PANELS_PER_MURAL si hay más de ese número.

    Args:
        prompt_list: Lista de prompts individuales por escena
        output_dir:  Carpeta donde guardar los paneles finales
        start_index: Índice global inicial (útil para lotes consecutivos)

    Returns:
        Lista ordenada de rutas de imágenes finales
    """
    os.makedirs(output_dir, exist_ok=True)
    all_paths = []
    total = len(prompt_list)
    batch_size = MAX_PANELS_PER_MURAL

    for batch_start in range(0, total, batch_size):
        batch = prompt_list[batch_start:batch_start + batch_size]
        n = len(batch)
        global_start = start_index + batch_start
        batch_num = batch_start // batch_size + 1
        total_batches = math.ceil(total / batch_size)

        print(f"  Lote {batch_num}/{total_batches} — {n} paneles...")

        # 1. Construir prompt maestro
        mural_prompt = _build_mural_prompt(batch, start_index=global_start)

        # 2. Generar mural
        mural_path = os.path.join(output_dir, f"mural_{batch_num:02d}.png")
        _generate_mural(mural_prompt, mural_path, n)
        print(f"  Mural {batch_num} generado")

        # 3. Cortar paneles
        panel_paths = _cut_mural(mural_path, n, output_dir, start_index=global_start)
        print(f"  {n} paneles cortados")

        # 4. Upscale cada panel
        for path in panel_paths:
            _upscale_panel(path)
        print(f"  Upscale aplicado a {n} paneles")

        # 5. Eliminar mural temporal
        os.remove(mural_path)

        all_paths.extend(panel_paths)

    return all_paths 
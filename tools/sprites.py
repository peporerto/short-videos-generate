import os
import yaml
from PIL import Image


def _parse_grid(grid_str: str):
    """Parsea '2x2' -> (2, 2)"""
    parts = grid_str.lower().split("x")
    return int(parts[0]), int(parts[1])


def _parse_cell(cell_str: str):
    """Parsea '0,1' -> (0, 1)"""
    parts = cell_str.split(",")
    return int(parts[0]), int(parts[1])


def _crop_cell(img: Image.Image, rows: int, cols: int, row: int, col: int) -> Image.Image:
    """Recorta una celda de la cuadrícula."""
    w, h = img.size
    cell_w = w // cols
    cell_h = h // rows
    left = col * cell_w
    top = row * cell_h
    right = left + cell_w
    bottom = top + cell_h
    return img.crop((left, top, right, bottom))


def _remove_white_background(img: Image.Image, threshold: int = 240) -> Image.Image:
    """Elimina fondo blanco convirtiendo píxeles claros en transparentes."""
    img = img.convert("RGBA")
    data = img.getdata()
    new_data = []
    for r, g, b, a in data:
        if r > threshold and g > threshold and b > threshold:
            new_data.append((255, 255, 255, 0))
        else:
            new_data.append((r, g, b, a))
    img.putdata(new_data)
    return img


def process_sprites(config_path: str = "assets/avatares/config.yaml") -> None:
    """Lee config.yaml y genera todos los PNGs de avatares y escenarios."""
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    os.makedirs("assets/avatares", exist_ok=True)
    os.makedirs("assets/escenarios", exist_ok=True)

    # ── Avatares ──────────────────────────────────────────────────────────────
    avatares = config.get("avatares", {})
    total = len(avatares)
    print(f"\nProcesando {total} avatares...")

    for i, (nombre, cfg) in enumerate(avatares.items()):
        output_path = f"assets/avatares/{nombre}.png"

        if os.path.exists(output_path):
            print(f"  [{i+1}/{total}] {nombre} — ya existe, saltando")
            continue

        print(f"  [{i+1}/{total}] {nombre}...")

        img = Image.open(cfg["source"]).convert("RGBA")
        rows, cols = _parse_grid(cfg["grid"])
        row, col = _parse_cell(cfg["cell"])
        celda = _crop_cell(img, rows, cols, row, col)

        celda_sin_fondo = _remove_white_background(celda)

        if cfg.get("flip", False):
            celda_sin_fondo = celda_sin_fondo.transpose(Image.FLIP_LEFT_RIGHT)

        rotate = cfg.get("rotate", 0)
        if rotate != 0:
            celda_sin_fondo = celda_sin_fondo.rotate(rotate, expand=True)

        celda_sin_fondo.save(output_path)
        print(f"  [{i+1}/{total}] {nombre} — OK")

    # ── Escenarios ────────────────────────────────────────────────────────────
    escenarios = config.get("escenarios", {})
    total = len(escenarios)
    print(f"\nProcesando {total} escenarios...")

    for i, (nombre, cfg) in enumerate(escenarios.items()):
        output_path = f"assets/escenarios/{nombre}.png"

        if os.path.exists(output_path):
            print(f"  [{i+1}/{total}] {nombre} — ya existe, saltando")
            continue

        print(f"  [{i+1}/{total}] {nombre}...")

        img = Image.open(cfg["source"]).convert("RGBA")
        rows, cols = _parse_grid(cfg["grid"])
        row, col = _parse_cell(cfg["cell"])
        celda = _crop_cell(img, rows, cols, row, col)

        celda.save(output_path)
        print(f"  [{i+1}/{total}] {nombre} — OK")

    print("\n¡Sprites procesados! Revisa assets/avatares/ y assets/escenarios/")


if __name__ == "__main__":
    process_sprites()
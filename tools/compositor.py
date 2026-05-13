import os
from PIL import Image
from typing import Tuple, Optional


def composite_scene(
    background_path: str,
    avatar_path: Optional[str],
    output_path: str,
    target_size: Tuple[int, int] = (1080, 1920),
    avatar_position: str = "center",
    avatar_scale: float = 0.35
) -> None:
    """
    Combina un fondo de escenario con un avatar PNG transparente.

    Args:
        background_path: ruta al fondo (assets/escenarios/)
        avatar_path: ruta al avatar PNG transparente (assets/avatares/) o None
        output_path: donde guardar la imagen final
        target_size: resolución final (1080x1920 para shorts, 1920x1080 para largo)
        avatar_position: 'center', 'left', 'right', 'bottom_left', 'bottom_right'
        avatar_scale: tamaño del avatar relativo al ancho de la imagen (0.35 = 35%)
    """
    width, height = target_size

    # Cargar y redimensionar fondo
    bg = Image.open(background_path).convert("RGBA")
    bg = bg.resize(target_size, Image.LANCZOS)

    if avatar_path and os.path.exists(avatar_path):
        avatar = Image.open(avatar_path).convert("RGBA")

        # Escalar avatar proporcional al ancho
        avatar_w = int(width * avatar_scale)
        avatar_ratio = avatar.height / avatar.width
        avatar_h = int(avatar_w * avatar_ratio)
        avatar = avatar.resize((avatar_w, avatar_h), Image.LANCZOS)

        # Calcular posición
        x, y = _get_position(avatar_position, width, height, avatar_w, avatar_h)

        # Pegar avatar sobre fondo usando canal alpha
        bg.paste(avatar, (x, y), avatar)

    bg.save(output_path)


def _get_position(
    position: str,
    bg_w: int, bg_h: int,
    av_w: int, av_h: int
) -> Tuple[int, int]:
    """Calcula coordenadas x,y del avatar según posición."""
    margin = 40

    positions = {
        "center":       ((bg_w - av_w) // 2,        bg_h - av_h - margin),
        "left":         (margin,                      bg_h - av_h - margin),
        "right":        (bg_w - av_w - margin,        bg_h - av_h - margin),
        "bottom_left":  (margin,                      bg_h - av_h - margin),
        "bottom_right": (bg_w - av_w - margin,        bg_h - av_h - margin),
        "top_center":   ((bg_w - av_w) // 2,          margin),
        "top_left":     (margin,                       margin),
        "top_right":    (bg_w - av_w - margin,         margin),
    }

    return positions.get(position, positions["center"])


if __name__ == "__main__":
    # Test rápido
    composite_scene(
        background_path="assets/escenarios/barrio_noche.png",
        avatar_path="assets/avatares/brayan_idle.png",
        output_path="output/test_composite.png",
        avatar_position="center"
    )
    print("Test guardado en output/test_composite.png")
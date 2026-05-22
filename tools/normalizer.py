from PIL import Image, ImageFilter
import os

def normalize_images(image_paths: list, target_size: tuple = (1920, 1080), output_dir: str = "output/normalized") -> list:
    """
    Normaliza todas las imágenes a 1920x1080.
    Imágenes verticales: fondo blur + imagen centrada encima.
    Imágenes horizontales: crop centrado.
    """
    os.makedirs(output_dir, exist_ok=True)
    normalized = []

    for i, path in enumerate(image_paths):
        out_path = os.path.join(output_dir, f"norm_{i:02d}.jpg")
        img = Image.open(path).convert("RGB")
        iw, ih = img.size
        tw, th = target_size
        img_ratio = iw / ih
        target_ratio = tw / th

        if img_ratio < target_ratio:
            # Imagen vertical — blur background + overlay centrado
            bg = img.resize(target_size, Image.LANCZOS)
            bg = bg.filter(ImageFilter.GaussianBlur(radius=20))
            scale = th / ih
            new_w = int(iw * scale)
            new_h = th
            fg = img.resize((new_w, new_h), Image.LANCZOS)
            x = (tw - new_w) // 2
            bg.paste(fg, (x, 0))
            bg.save(out_path, quality=95)
        else:
            # Imagen horizontal — crop centrado
            scale = max(tw / iw, th / ih)
            new_w = int(iw * scale)
            new_h = int(ih * scale)
            resized = img.resize((new_w, new_h), Image.LANCZOS)
            x = (new_w - tw) // 2
            y = (new_h - th) // 2
            cropped = resized.crop((x, y, x + tw, y + th))
            cropped.save(out_path, quality=95)

        normalized.append(out_path)
        print(f"  Normalizada {i+1}/{len(image_paths)}: {os.path.basename(path)}")

    return normalized
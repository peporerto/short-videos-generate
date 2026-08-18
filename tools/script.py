import json
import os
import re
import google.generativeai as genai
from typing import Dict, List
from dotenv import load_dotenv

load_dotenv()


# Configuración de duración — incluye cantidad de imágenes proporcional
DURATION_CONFIG = {
    "short": {
        "label": "60 segundos",
        "words": 130,
        "num_images": 8,
        "sections": ["hook", "context", "value", "outro"],
        "section_guidance": {
            "hook":    "0-3s: pregunta o afirmacion de impacto inmediato, brutal y sin filtro",
            "context": "3-10s: por que importa, datos crudos y especificos",
            "value":   "10-45s: contenido principal, detalles sensoriales exactos, sin piedad",
            "outro":   "45-60s: cierre que deja al espectador sin palabras"
        }
    },
    "medium": {
        "label": "5 minutos",
        "words": 750,
        "num_images": 35,
        "sections": ["hook", "descent", "truth", "outro"],
        "section_guidance": {
            "hook":    "0-30s: empieza en el momento mas brutal, sin introduccion, en medio de la accion",
            "descent": "30s-3min: el conflicto escalando sin piedad, detalles sensoriales exactos en cada parrafo: temperatura, olor, peso, dolor fisico",
            "truth":   "3min-4min30s: la verdad desalmada que nadie dice, sin moralizar, solo hechos que duelen",
            "outro":   "4min30s-5min: cierre que hace que el espectador sienta lastima sin que nadie se la pida"
        }
    }
}

# Cantidad de imágenes por sección proporcional
def _images_per_section(duration: str) -> Dict[str, int]:
    """Distribuye las imágenes entre secciones proporcionalmente."""
    cfg = DURATION_CONFIG[duration]
    sections = cfg["sections"]
    total = cfg["num_images"]

    # Distribución: hook 15%, descent/value 60%, truth/context 15%, outro 10%
    if duration == "medium":
        return {
            "hook":    max(1, int(total * 0.15)),
            "descent": max(1, int(total * 0.60)),
            "truth":   max(1, int(total * 0.15)),
            "outro":   max(1, int(total * 0.10)),
        }
    else:
        return {
            "hook":    2,
            "context": 2,
            "value":   3,
            "outro":   1,
        }


def _build_prompt(topic: str, image_style: str, duration: str, narrative_mode: str) -> str:
    """Construye el prompt según duración y modo narrativo."""
    cfg = DURATION_CONFIG[duration]
    sections = cfg["sections"]
    guidance = cfg["section_guidance"]
    img_per_section = _images_per_section(duration)

    if narrative_mode == "second_person":
        narrative_instruction = (
            "Escribe en SEGUNDA PERSONA (tu). El espectador ES el protagonista. "
            "Sin filtro moral. Sin compasion. Solo hechos descritos con precision quirurgica. "
            "Detalles sensoriales en cada parrafo: temperatura exacta, olores especificos, "
            "peso del equipo, textura del suelo, sonidos que no se olvidan. "
            "La crueldad no se nombra. Se describe. "
            "El espectador debe sentir lastima sin que nadie se la pida. "
            "Nada generico. Sin moralizar. Los hechos hablan solos."
        )
    else:
        narrative_instruction = (
            "Escribe en tercera persona con tono informativo y directo. "
            "Datos concretos, ejemplos especificos, sin relleno. "
            "Cada afirmacion debe tener un detalle que la haga irrefutable."
        )

    # Schema con múltiples image_prompts por sección
    schema_parts = []
    for section in sections:
        n = img_per_section.get(section, 1)
        img_prompts = ", ".join([
            f'"image_prompt_{i+1}": "cinematic 2D illustration, editorial style, atmospheric, muted colors, soft shadows, {image_style}, clear subject, defined background, no photorealistic, no photography, no text, no watermark"'
            for i in range(n)
        ])
        schema_parts.append(
            f'"{section}": {{\n'
            f'    "text": "{guidance[section]}",\n'
            f'    {img_prompts}\n'
            f'}}'
        )
    schema = "{\n" + ",\n".join(schema_parts) + "\n}"

    return f"""
Eres un escritor de narrativa inmersiva para YouTube en español.

Escribe un guion de {cfg["label"]} sobre: {topic}

OBJETIVO:
- Crear una historia fuerte, humana y triste
- Mantener el interés con ritmo, tensión y detalles concretos
- Incluir algunos datos reales en medio del relato si son seguros
- No sonar genérico, dramático ni exagerado

ESTILO NARRATIVO:
{narrative_instruction}

REGLAS DEL RELATO:
- Prioriza emoción, contexto y consecuencia
- Usa detalles sensoriales específicos, pero sin recargar cada frase
- No repitas ideas
- No hagas el texto más cruel por ser cruel
- La dureza debe venir de los hechos y de la situación
- Si un dato no es seguro, escribe [VERIFY]
- Mantén un tono serio, sobrio y humano

IMÁGENES:
- Las image_prompts deben ser atmosféricas, no literales
- No describas la acción exacta del texto
- Evoca ambiente, tensión y emoción
- Estilo visual: {image_style}
- Siempre en inglés
- Cada prompt debe ser corto, limpio y usable para IA de imagen

SALIDA:
Devuelve estrictamente este JSON, sin texto adicional:
{schema}
"""


def generate_script(
    topic: str,
    image_style: str = "cinematic photorealistic, 4k",
    duration: str = "short",
    narrative_mode: str = "informative"
) -> Dict:
    """
    Genera un guion con prompts de imagen usando Gemini API.

    Args:
        topic: Tema del video
        image_style: Estilo visual para las imágenes
        duration: 'short' (60s) o 'medium' (5min)
        narrative_mode: 'second_person' (brutal inmersivo) o 'informative' (datos)
    """
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY no configurada.")

        genai.configure(api_key=api_key)
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        model = genai.GenerativeModel(model_name)


        if duration not in DURATION_CONFIG:
            raise ValueError(f"Duracion '{duration}' no valida. Usa 'short' o 'medium'.")

        prompt = _build_prompt(topic, image_style, duration, narrative_mode)

        response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:-3].strip()
        elif text.startswith("```"):
            text = text[3:-3].strip()

        text = text.replace("\\'", "'").replace("\u2019", "")

        try:
            script_data = json.loads(text)
        except json.JSONDecodeError:
            text = re.sub(
                r'(?<=[^\\])"([^"]*?)\'([^"]*?)"',
                lambda m: '"' + m.group(1) + m.group(2) + '"',
                text
            )
            script_data = json.loads(text)

        # Limpiar etiquetas de tiempo
        for key in script_data:
            if isinstance(script_data[key], dict):
                if "text" in script_data[key]:
                    script_data[key]["text"] = re.sub(
                        r'^\d+-\d+s:\s*', '',
                        str(script_data[key]["text"])
                    ).strip()

        return script_data

    except Exception as e:
        raise RuntimeError(f"Error generando guion con Gemini: {e}")


def get_script_sections(duration: str) -> List[str]:
    """Retorna las secciones del guion según la duración."""
    return DURATION_CONFIG.get(duration, DURATION_CONFIG["short"])["sections"]


def get_all_image_prompts(script_data: Dict, duration: str) -> List[str]:
    """
    Extrae todos los image_prompts del script en orden.
    Retorna una lista plana de todos los prompts de imagen.
    """
    sections = get_script_sections(duration)
    prompts = []
    for section in sections:
        section_data = script_data.get(section, {})
        i = 1
        while f"image_prompt_{i}" in section_data:
            prompts.append(section_data[f"image_prompt_{i}"])
            i += 1
        # Fallback si no hay image_prompts numerados
        if i == 1 and "image_prompt" in section_data:
            prompts.append(section_data["image_prompt"])
    return prompts
import json
import os
import re
import google.generativeai as genai
from typing import Dict

def generate_script(topic: str, image_style: str = "cinematic photorealistic, 4k") -> Dict[str, str]:
    """Genera un guion con prompts de imagen usando Gemini API."""
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY no configurada.")

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-3-flash-preview")

        prompt = f"""
        Genera un guion de 60 segundos y descripciones de imágenes para un video sobre: {topic}.
        
        IMPORTANTE: No uses apostrofes ni comillas simples en ningun valor.
        Escribe palabras completas sin contracciones ni caracteres especiales.
        
        Para cada image_prompt aplica obligatoriamente este estilo visual: {image_style}
        Las image_prompt deben ser en inglés, cinematográficas y directamente relacionadas con el tema.
        
        Responde estrictamente con este JSON sin texto adicional:
        {{
            "hook": {{
                "text": "pregunta o afirmación de impacto",
                "image_prompt": "descripción visual detallada en inglés con el estilo indicado"
            }},
            "context": {{
                "text": "por qué importa",
                "image_prompt": "descripción visual detallada en inglés con el estilo indicado"
            }},
            "value": {{
                "text": "contenido principal",
                "image_prompt": "descripción visual detallada en inglés con el estilo indicado"
            }},
            "outro": {{
                "text": "cierre o llamada a acción",
                "image_prompt": "descripción visual detallada en inglés con el estilo indicado"
            }}
        }}
        """
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

        for key in script_data:
            if isinstance(script_data[key], dict):
                script_data[key]["text"] = re.sub(
                    r'^\d+-\d+s:\s*', '', str(script_data[key].get("text", ""))
                ).strip()

        return script_data

    except Exception as e:
        raise RuntimeError(f"Error generando guion con Gemini: {e}")
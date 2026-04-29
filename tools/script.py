import json
import os
import google.generativeai as genai
from typing import Dict

def generate_script(topic: str) -> Dict[str, str]:
    """Genera un guion usando Gemini API con una estructura JSON fija."""
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY no configurada.")
            
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        prompt = f"""
        Genera un guion para un video corto de 60 segundos sobre: {topic}.
        Debes responder estrictamente con un JSON válido con estas claves exactas y sin texto adicional:
        {{
            "hook": "0-3s: pregunta o afirmación que genera tensión",
            "context": "3-10s: por qué importa",
            "value": "10-45s: la respuesta o el contenido real",
            "outro": "45-60s: cierre o llamada a acción"
        }}
        """
        response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:-3].strip()
        elif text.startswith("```"):
            text = text[3:-3].strip()
        
        script_data = json.loads(text)
        return script_data
    except Exception as e:
        raise RuntimeError(f"Error generando guion con Gemini: {e}")

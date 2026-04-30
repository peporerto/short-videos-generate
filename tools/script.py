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
        
        # Configuramos el modelo para que ESCUPA JSON puro
        model = genai.GenerativeModel(
            model_name="gemini-3-flash-preview",
            generation_config={"response_mime_type": "application/json"}
        )
        
        prompt = f"""
        Genera un guion para un video corto de 60 segundos sobre: {topic}.
        Responde estrictamente con este esquema JSON:
        {{
            "hook": "0-3s: frase de impacto",
            "context": "3-10s: contexto",
            "value": "10-45s: contenido",
            "outro": "45-60s: cierre"
        }}
        """
        
        # Una sola llamada es suficiente
        response = model.generate_content(prompt)
        
        # Como usamos response_mime_type, response.text ya es un JSON válido
        return json.loads(response.text)

    except Exception as e:
        raise RuntimeError(f"Error generando guion con Gemini: {e}")
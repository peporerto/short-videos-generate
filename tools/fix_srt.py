"""
fix_srt.py
----------
Corrige errores de transcripción en archivos .srt generados por TTS/Whisper.
Uso: python fix_srt.py input.srt output.srt
Si no se pasa output.srt, sobreescribe el input.
"""

import sys
import re

# ---------------------------------------------------------------
# DICCIONARIO DE CORRECCIONES
# Agrega aquí cualquier error nuevo que encuentres en futuros videos
# Formato: "texto_erroneo": "texto_correcto"
# ---------------------------------------------------------------
CORRECTIONS = {
    # Nombres propios
    "Bralla n":         "Brayan",
    "Bralla":           "Brayan",
    "Bralla nació":     "Brayan nació",
    "Bralla no":        "Brayan no",

    # Marcas y lugares
    "van Colombia":     "Bancolombia",
    "BanColombia":      "Bancolombia",
    "banco colombia":   "Bancolombia",

    # Palabras colombianas / latinas mal transcritas
    "Chang Wei Pan":    "Changua y pan",
    "chang wei pan":    "changua y pan",
    "Chang way pan":    "Changua y pan",
    "fletear":          "fletear",       # a veces se escribe "fle tear"
    "fle tear":         "fletear",
    "campaneros":       "campaneros",
    "campa neros":      "campaneros",
    "parche":           "parche",

    # Números y fechas que se cortan mal
    "16\naños":         "16 años",
    "45\ncon 107":      "45 con 107",
}

# ---------------------------------------------------------------


def fix_srt(input_path: str, output_path: str):
    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read()

    total_fixes = 0
    for wrong, correct in CORRECTIONS.items():
        count = len(re.findall(re.escape(wrong), content, flags=re.IGNORECASE))
        if count > 0:
            content = re.sub(re.escape(wrong), correct, content, flags=re.IGNORECASE)
            print(f"  ✅ '{wrong}' → '{correct}' ({count} vez/veces)")
            total_fixes += count

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\n✅ Total correcciones: {total_fixes}")
    print(f"📄 Guardado en: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python fix_srt.py input.srt [output.srt]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) >= 3 else input_file

    print(f"\n🔍 Procesando: {input_file}")
    fix_srt(input_file, output_file)
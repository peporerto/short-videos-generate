import asyncio
import edge_tts
import os

async def test():
    # Asegurarnos de que existe la carpeta output
    os.makedirs('output', exist_ok=True)

    texto = 'Juan Manuel duerme con un peluche de oso bajo el brazo ja ja ja ja '
    # Probamos con una voz estándar y sin parámetros raros
    communicate = edge_tts.Communicate(texto, 'es-ES-AlvaroNeural')
    await communicate.save('output/test_audio.mp3')
    print('[OK] Audio generado OK en output/test_audio.mp3')

if __name__ == "__main__":
    asyncio.run(test())
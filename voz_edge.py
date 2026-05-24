import asyncio
import tempfile
import edge_tts


async def _generar_audio(texto: str, ruta: str):
    communicate = edge_tts.Communicate(
        text=texto,
        voice="es-BO-SofiaNeural"
    )
    await communicate.save(ruta)


def texto_a_voz_edge(texto: str) -> bytes:
    if not texto or not texto.strip():
        return b""

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    ruta = temp.name
    temp.close()

    asyncio.run(_generar_audio(texto, ruta))

    with open(ruta, "rb") as f:
        audio_bytes = f.read()

    return audio_bytes
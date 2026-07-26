"""Synthesize text to speech using Edge-TTS.

Usage:
    uv run python scripts/synthesize.py "Hola, esto es una prueba"
    uv run python scripts/synthesize.py "Bienvenido" --voice es-MX-JorgeNeural --output saludo.mp3
    uv run python scripts/synthesize.py --list-voices
"""

import argparse
import asyncio
import time

from src.app.services.synthesizer import Synthesizer


async def list_voices() -> None:
    import edge_tts

    voices = await edge_tts.list_voices()
    mx_voices = [v for v in voices if "es-MX" in v["ShortName"]]

    print(f"{'Voice':<45} {'Gender':<8}")
    print("-" * 55)
    for v in mx_voices:
        print(f"{v['ShortName']:<45} {v['Gender']:<8}")
    print(f"\n{len(mx_voices)} voces es-MX disponibles")


async def synthesize(text: str, voice: str, output: str) -> None:
    print(f"Voice: {voice}")
    print(f"Text: {text[:80]}{'...' if len(text) > 80 else ''}")

    synthesizer = Synthesizer(voice=voice)

    t0 = time.time()
    audio_bytes = await synthesizer.synthesize(text)
    elapsed = time.time() - t0

    with open(output, "wb") as f:
        f.write(audio_bytes)

    print(f"\nGenerated {len(audio_bytes) / 1024:.1f} KB in {elapsed:.2f}s")
    print(f"Saved to: {output}")
    print(f"\nPlay with: mpv {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Text-to-speech with Edge-TTS")
    parser.add_argument("text", nargs="?", help="Text to synthesize")
    parser.add_argument("--voice", default="es-MX-DaliaNeural", help="Voice ID")
    parser.add_argument("--output", "-o", default="output.mp3", help="Output file path")
    parser.add_argument("--list-voices", action="store_true", help="List available es-MX voices")
    args = parser.parse_args()

    if args.list_voices:
        asyncio.run(list_voices())
        return

    if not args.text:
        parser.error("text is required (or use --list-voices)")

    asyncio.run(synthesize(args.text, args.voice, args.output))


if __name__ == "__main__":
    main()

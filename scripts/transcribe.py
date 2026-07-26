"""Transcribe an audio file using Faster-Whisper.

Usage:
    uv run python scripts/transcribe.py archives/AUDIO.mp3
    uv run python scripts/transcribe.py archivo.ogg --model base --device cpu
"""

import argparse
import time
from pathlib import Path

from src.app.services.transcriber import Transcriber


def main() -> None:
    parser = argparse.ArgumentParser(description="Transcribe audio to text")
    parser.add_argument("audio_file", help="Path to audio file (mp3, ogg, wav)")
    parser.add_argument("--model", default="base", help="Whisper model (tiny/base/small/medium/large-v3)")
    parser.add_argument("--device", default="cpu", help="Device (cpu/cuda)")
    parser.add_argument("--language", default="es", help="Language code")
    args = parser.parse_args()

    audio_path = Path(args.audio_file)
    if not audio_path.exists():
        print(f"Error: {audio_path} not found")
        return

    print(f"Loading model '{args.model}' on {args.device}...")
    t0 = time.time()
    transcriber = Transcriber(model_size=args.model, device=args.device)
    print(f"Model loaded in {time.time() - t0:.1f}s")

    audio_bytes = audio_path.read_bytes()
    print(f"Transcribing {audio_path.name} ({len(audio_bytes) / 1024:.1f} KB)...")

    t0 = time.time()
    text = transcriber.transcribe(audio_bytes, language=args.language)
    elapsed = time.time() - t0

    print(f"\n{'=' * 60}")
    print(f"Result ({elapsed:.2f}s):")
    print(f"{'=' * 60}")
    print(text)
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()

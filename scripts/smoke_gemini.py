"""
One-shot smoke test: upload a webm file to Gemini Files API, call generate_content, print result.

Usage:
    python scripts/smoke_gemini.py [path/to/audio.webm]

If no path is provided, generates a 3-second silent webm via ffmpeg (requires ffmpeg installed).
Reads GEMINI_API_KEY from environment — fails fast with KeyError if absent.
"""
import os
import sys
import time
import subprocess
from pathlib import Path

from google import genai
from google.genai import types


def generate_silent_webm(output_path: Path) -> None:
    """Generate a 3-second silent webm file using ffmpeg."""
    print(f"No audio file provided. Generating silent test webm at {output_path}...")
    result = subprocess.run(
        [
            "ffmpeg",
            "-f", "lavfi",
            "-i", "anullsrc=r=48000:cl=stereo",
            "-t", "3",
            "-c:a", "libopus",
            str(output_path),
            "-y",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ffmpeg error:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    print(f"Generated: {output_path}")


def main() -> None:
    # Fail fast if key is missing
    api_key = os.environ["GEMINI_API_KEY"]

    # Resolve audio file path
    if len(sys.argv) > 1:
        audio_path = Path(sys.argv[1])
        if not audio_path.exists():
            print(f"Error: file not found: {audio_path}", file=sys.stderr)
            sys.exit(1)
    else:
        audio_path = Path("scripts/test_silence.webm")
        if not audio_path.exists():
            generate_silent_webm(audio_path)

    # Build client
    client = genai.Client(api_key=api_key)

    # Upload to Files API
    print(f"Uploading {audio_path}...")
    uploaded_file = client.files.upload(
        file=audio_path,
        config=types.UploadFileConfig(mime_type="audio/webm"),
    )
    print(f"Upload result: uri={uploaded_file.uri}, state={uploaded_file.state}")

    # Brief sleep to allow small files to move past PROCESSING state
    print("Waiting 2 seconds for file processing...")
    time.sleep(2)

    # Call generate_content with retry for transient errors (503, 429)
    print("Calling Gemini (gemini-2.5-pro)...")
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-pro",
                contents=[uploaded_file, "Briefly describe what you hear in this audio."],
            )
            break
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            if status in (503, 429) and attempt < max_retries:
                wait = 5 * attempt
                print(f"Transient error ({status}), retrying in {wait}s... (attempt {attempt}/{max_retries})")
                time.sleep(wait)
            else:
                raise

    # Check finish reason — safety blocks are informational at smoke-test stage
    candidate = response.candidates[0]
    finish_reason = candidate.finish_reason
    if str(finish_reason) not in ("FinishReason.STOP", "STOP", "1"):
        print(f"Warning: finish_reason={finish_reason} (may indicate a safety block or other issue)")

    print(f"Response text: {response.text}")
    print("SMOKE TEST PASSED")


if __name__ == "__main__":
    main()

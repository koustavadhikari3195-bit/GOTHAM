"""
Speech-to-Text using OpenAI Whisper — runs fully locally.
No API calls. No rate limits. No cost. Works offline.
First run downloads the model (~150MB). Subsequent runs use cache.
"""
import os
import tempfile
import logging
import whisper

logger = logging.getLogger("gotham-agent.stt")
_model = None


def _load():
    global _model
    if _model is None:
        logger.info("Loading Whisper base.en model (one-time download ~150MB)...")
        _model = whisper.load_model("base.en")
        logger.info("Whisper ready")
    return _model


def _detect_suffix(audio_bytes: bytes) -> str:
    """Detect audio format from magic bytes and return appropriate suffix."""
    if audio_bytes[:4] == b'RIFF':
        return ".wav"
    if audio_bytes[:4] == b'\x1aE\xdf\xa3':
        return ".webm"
    if audio_bytes[:3] == b'ID3' or audio_bytes[:2] == b'\xff\xfb':
        return ".mp3"
    if audio_bytes[:4] == b'OggS':
        return ".ogg"
    if audio_bytes[:4] == b'fLaC':
        return ".flac"
    # Default to .webm since browsers typically send WebM/Opus
    return ".webm"


def transcribe(audio_bytes: bytes) -> str:
    """
    Transcribe raw audio bytes to text.
    Auto-detects format (WAV, WebM, MP3, etc.) from magic bytes.
    Requires ffmpeg for non-WAV formats.
    """
    if not audio_bytes or len(audio_bytes) < 100:
        return ""

    model = _load()
    suffix = _detect_suffix(audio_bytes)

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name

    try:
        result = model.transcribe(
            tmp_path,
            language="en",
            fp16=False,   # set True if you have a CUDA GPU
        )
        text = result["text"].strip()
        return text
    except Exception as e:
        logger.error(f"STT error: {e}")
        return ""
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

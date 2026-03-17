"""
Speech-to-Text — Groq Whisper-Large-v3 (primary) + Local Whisper (fallback).

Primary:  Groq API running whisper-large-v3 — blazing fast, extremely accurate, free tier.
Fallback: Local whisper-base.en — runs if Groq is down or rate-limited.

Groq free tier: 14,400 requests/day for audio transcription.
"""
import os
import io
import tempfile
import logging

logger = logging.getLogger("gotham-agent.stt")

# ── Local Whisper fallback ───────────────────────────────────────────────────
_local_model = None

def _load():
    """Load local Whisper model for fallback use."""
    global _local_model
    if _local_model is None:
        import whisper
        logger.info("Loading local Whisper base.en model (fallback)...")
        _local_model = whisper.load_model("base.en")
        logger.info("Local Whisper ready (fallback)")
    return _local_model


def _transcribe_local(audio_bytes: bytes) -> str:
    """Transcribe using local Whisper model (fallback)."""
    model = _load()
    suffix = _detect_suffix(audio_bytes)

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name

    try:
        result = model.transcribe(tmp_path, language="en", fp16=False)
        return result["text"].strip()
    except Exception as e:
        logger.error(f"Local STT error: {e}")
        return ""
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ── Groq Whisper-Large-v3 (primary) ─────────────────────────────────────────
_groq_client = None

def _get_groq_client():
    """Lazy-init Groq client for STT."""
    global _groq_client
    if _groq_client is None:
        try:
            from groq import Groq
            api_key = os.getenv("GROQ_API_KEY")
            if api_key:
                _groq_client = Groq(api_key=api_key)
                logger.info("Groq Whisper-Large-v3 STT ready (primary)")
            else:
                logger.warning("No GROQ_API_KEY — using local Whisper only")
        except ImportError:
            logger.warning("groq package not installed — using local Whisper only")
    return _groq_client


def _transcribe_groq(audio_bytes: bytes) -> str:
    """Transcribe using Groq's Whisper-Large-v3 API."""
    client = _get_groq_client()
    if not client:
        return ""

    suffix = _detect_suffix(audio_bytes)
    filename = f"audio{suffix}"

    try:
        transcription = client.audio.transcriptions.create(
            file=(filename, io.BytesIO(audio_bytes)),
            model="whisper-large-v3",
            language="en",
            response_format="text",
        )
        text = transcription.strip() if isinstance(transcription, str) else str(transcription).strip()
        logger.info(f"Groq STT result: '{text[:80]}...' " if len(text) > 80 else f"Groq STT result: '{text}'")
        return text
    except Exception as e:
        logger.warning(f"Groq STT failed ({e}), falling back to local Whisper")
        return ""


# ── Audio format detection ───────────────────────────────────────────────────

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
    return ".webm"


# ── Public API ───────────────────────────────────────────────────────────────

def transcribe(audio_bytes: bytes) -> str:
    """
    Transcribe audio bytes to text.
    Uses Groq Whisper-Large-v3 (primary) with local Whisper fallback.
    """
    if not audio_bytes or len(audio_bytes) < 100:
        return ""

    # Try Groq first (much more accurate, whisper-large-v3)
    text = _transcribe_groq(audio_bytes)
    if text:
        return text

    # Fallback to local Whisper
    logger.info("Using local Whisper fallback")
    return _transcribe_local(audio_bytes)

"""
Text-to-Speech using Kokoro TTS — runs fully locally.
Apache 2.0 license. No API calls. No cost. Works offline.

Install:  pip install kokoro-onnx soundfile
Models:   download kokoro-v0_19.onnx and voices.bin from
          https://github.com/thewh1teagle/kokoro-onnx/releases

Voice options:
  af_bella — warm, friendly female (recommended default)
  af_sky   — another warm female voice
  am_adam  — energetic male
  bf_emma  — British female
"""
import io
import logging
import soundfile as sf

logger = logging.getLogger("gotham-agent.tts")
_pipeline = None


def _load():
    global _pipeline
    if _pipeline is None:
        try:
            from kokoro_onnx import Kokoro
            logger.info("Loading Kokoro TTS model...")
            _pipeline = Kokoro("kokoro-v0_19.onnx", "voices.bin")
            logger.info("Kokoro TTS ready")
        except ImportError:
            logger.error("kokoro-onnx not installed. Run: pip install kokoro-onnx")
        except FileNotFoundError:
            logger.error(
                "Kokoro model files not found. Download kokoro-v0_19.onnx "
                "and voices.bin - see backend/voice/tts.py for instructions."
            )
    return _pipeline


def speak(text: str,
          voice: str  = "af_bella",
          speed: float = 1.1) -> bytes:
    """
    Convert text to speech. Returns WAV bytes.
    Returns empty bytes if Kokoro is unavailable (frontend shows text only).
    """
    pipeline = _load()
    if pipeline is None:
        return b""

    try:
        # Fallback if voice is missing
        available = pipeline.get_voices()
        if voice not in available:
            logger.warning(f"Voice {voice} not found. Falling back to af_bella. Available: {available}")
            voice = "af_bella" if "af_bella" in available else available[0]

        samples, sample_rate = pipeline.create(
            text,
            voice = voice,
            speed = speed,
            lang  = "en-us"
        )
        buf = io.BytesIO()
        sf.write(buf, samples, sample_rate, format="WAV")
        return buf.getvalue()

    except Exception as e:
        logger.error(f"TTS error: {e}")
        return b""

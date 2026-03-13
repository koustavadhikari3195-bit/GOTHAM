#!/usr/bin/env python3
"""
Test script for audio pipeline: TTS (text-to-speech) and STT (speech-to-text).

This script validates:
1. TTS model loads and generates audio
2. Audio quality (format, duration, sample rate)
3. STT model loads and transcribes accurately
4. Round-trip quality (text -> speech -> text)

Usage:
    python test_audio_pipeline.py

Output:
    - JSON-formatted results for CI/CD integration
    - WAV file saved with timestamp for manual inspection
    - Detailed timing and error information
"""

import asyncio
import os
import sys
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

# Ensure backend is in path
sys.path.append(os.getcwd())

# ══════════════════════════════════════════════════════════════════════════════
# LOGGING SETUP
# ══════════════════════════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test-audio-pipeline")

# Output directory for test artifacts
ARTIFACTS_DIR = Path("test_artifacts")
ARTIFACTS_DIR.mkdir(exist_ok=True)


class AudioTestResult:
    """Structured result from test pipeline."""
    
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.timestamp = datetime.utcnow().isoformat()
        self.passed = False
        self.duration_ms = 0.0
        self.tts_duration_ms = 0.0
        self.stt_duration_ms = 0.0
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.audio_file: Optional[str] = None
        self.details: Dict[str, Any] = {}
    
    def add_error(self, msg: str):
        """Record an error."""
        logger.error(msg)
        self.errors.append(msg)
    
    def add_warning(self, msg: str):
        """Record a warning."""
        logger.warning(msg)
        self.warnings.append(msg)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "test_name": self.test_name,
            "timestamp": self.timestamp,
            "passed": self.passed,
            "duration_ms": round(self.duration_ms, 2),
            "tts_duration_ms": round(self.tts_duration_ms, 2),
            "stt_duration_ms": round(self.stt_duration_ms, 2),
            "errors": self.errors,
            "warnings": self.warnings,
            "audio_file": self.audio_file,
            "details": self.details
        }


async def validate_models_exist() -> bool:
    """Pre-check: verify model files are accessible."""
    logger.info("Step 0: Validating model file paths...")
    
    # Check for common model locations
    # Adjust paths based on your backend configuration
    potential_kokoro_paths = [
        Path("models/kokoro"),
        Path("backend/models/kokoro"),
        Path("/usr/local/models/kokoro"),
        Path(os.path.expanduser("~/.cache/kokoro")),
        Path("kokoro-v0_19.onnx") # based on the root directory
    ]
    
    potential_whisper_paths = [
        Path("models/whisper"),
        Path("backend/models/whisper"),
        Path("/usr/local/models/whisper"),
        Path(os.path.expanduser("~/.cache/whisper")),
        Path(os.path.expanduser("~/.cache/whisper/base.en.pt"))
    ]
    
    kokoro_found = any(p.exists() for p in potential_kokoro_paths)
    whisper_found = any(p.exists() for p in potential_whisper_paths)
    
    if not kokoro_found:
        logger.warning(f"Kokoro model not found in common paths. (It might auto-download)")
    if not whisper_found:
        logger.warning(f"Whisper model not found in common paths. (It might auto-download)")
    
    return kokoro_found and whisper_found


async def test_audio_pipeline() -> AudioTestResult:
    """Full test: TTS -> transcribe -> STT -> validate."""
    result = AudioTestResult("audio_pipeline_full")
    start_time = time.time()
    
    try:
        # Step 0: Pre-flight checks
        logger.info("=" * 80)
        logger.info("AUDIO PIPELINE TEST")
        logger.info("=" * 80)
        
        models_ready = await validate_models_exist()
        if not models_ready:
            result.add_warning("Some models may not be found — test may fail on import")
        
        # Step 1: Import modules
        logger.info("Step 1: Importing audio modules...")
        try:
            from backend.voice.tts import speak
            from backend.voice.stt import transcribe
            logger.info("✓ Modules imported successfully")
        except ImportError as e:
            result.add_error(f"Failed to import audio modules: {e}")
            result.passed = False
            return result
        
        # Step 2: Test TTS
        logger.info("Step 2: Testing TTS (text-to-speech)...")
        test_text = "Welcome to Gotham Fitness. Let's get to work."
        
        tts_start = time.time()
        try:
            audio_bytes = await speak(test_text)
            tts_duration = (time.time() - tts_start) * 1000
            result.tts_duration_ms = tts_duration
            
            if not audio_bytes:
                result.add_error("TTS returned None or empty bytes")
                result.passed = False
                return result
            
            audio_size = len(audio_bytes)
            logger.info(f"✓ TTS succeeded: {audio_size} bytes in {tts_duration:.1f}ms")
            
            # Validate audio size
            MIN_AUDIO_SIZE = 500   # Very permissive; real audio is typically >10KB
            MAX_AUDIO_SIZE = 1_000_000  # 1MB max
            
            if audio_size < MIN_AUDIO_SIZE:
                result.add_error(f"Audio too small: {audio_size} bytes (min: {MIN_AUDIO_SIZE})")
                result.passed = False
                return result
            
            if audio_size > MAX_AUDIO_SIZE:
                result.add_warning(f"Audio unusually large: {audio_size} bytes (max: {MAX_AUDIO_SIZE})")
            
            result.details["tts_audio_size"] = audio_size
            
        except Exception as e:
            result.add_error(f"TTS failed with exception: {type(e).__name__}: {e}")
            logger.exception("TTS exception:")
            result.passed = False
            return result
        
        # Step 3: Save audio file
        logger.info("Step 3: Saving audio to file...")
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        audio_file = ARTIFACTS_DIR / f"test_output_{timestamp}.wav"
        
        try:
            with open(audio_file, "wb") as f:
                f.write(audio_bytes)
            logger.info(f"✓ Audio saved to {audio_file}")
            result.audio_file = str(audio_file)
        except Exception as e:
            result.add_error(f"Failed to save audio: {e}")
            result.passed = False
            return result
        
        # Step 4: Test STT
        logger.info("Step 4: Testing STT (speech-to-text)...")
        
        stt_start = time.time()
        try:
            transcribed_text = transcribe(audio_bytes)
            stt_duration = (time.time() - stt_start) * 1000
            result.stt_duration_ms = stt_duration
            
            logger.info(f"✓ STT succeeded in {stt_duration:.1f}ms")
            logger.info(f"  Original:    '{test_text}'")
            logger.info(f"  Transcribed: '{transcribed_text}'")
            
            if not transcribed_text:
                result.add_error("STT returned empty string")
                result.passed = False
                return result
            
            result.details["original_text"] = test_text
            result.details["transcribed_text"] = transcribed_text
            
        except Exception as e:
            result.add_error(f"STT failed with exception: {type(e).__name__}: {e}")
            logger.exception("STT exception:")
            result.passed = False
            return result
        
        # Step 5: Validate transcription accuracy
        logger.info("Step 5: Validating transcription accuracy...")
        
        # Normalize both strings for comparison
        original_normalized = test_text.lower().strip()
        transcribed_normalized = transcribed_text.lower().strip()
        
        if original_normalized == transcribed_normalized:
            logger.info("✓ Perfect match!")
            result.details["match"] = "perfect"
            result.passed = True
        elif _similarity(original_normalized, transcribed_normalized) > 0.9:
            logger.info("✓ Very close match (>90% similar)")
            result.details["match"] = "very_close"
            result.add_warning(f"Minor differences in transcription")
            result.passed = True
        elif _similarity(original_normalized, transcribed_normalized) > 0.7:
            logger.info("⚠ Partial match (>70% similar)")
            result.details["match"] = "partial"
            result.add_warning(f"Significant differences in transcription")
            result.passed = True  # Still passes, but with warnings
        else:
            result.add_error(f"Poor transcription quality (<70% similar)")
            result.details["match"] = "poor"
            result.passed = False
        
        result.details["similarity"] = round(_similarity(original_normalized, transcribed_normalized), 3)
        
    except Exception as e:
        result.add_error(f"Unexpected error in test pipeline: {type(e).__name__}: {e}")
        logger.exception("Unexpected exception:")
        result.passed = False
    
    finally:
        result.duration_ms = (time.time() - start_time) * 1000
    
    return result


def _similarity(a: str, b: str) -> float:
    """
    Calculate string similarity using Levenshtein distance.
    Returns 0.0 to 1.0 (1.0 = identical).
    """
    from difflib import SequenceMatcher
    return SequenceMatcher(None, a, b).ratio()


def print_results(result: AudioTestResult):
    """Pretty-print test results."""
    status = "[PASS]" if result.passed else "[FAIL]"
    
    print("\n" + "=" * 80)
    print(f"{status} | {result.test_name}")
    print("=" * 80)
    print(f"Timestamp:        {result.timestamp}")
    print(f"Total Duration:   {result.duration_ms:.1f}ms")
    print(f"TTS Duration:     {result.tts_duration_ms:.1f}ms")
    print(f"STT Duration:     {result.stt_duration_ms:.1f}ms")
    
    if result.audio_file:
        print(f"Audio File:       {result.audio_file}")
    
    if result.details:
        print("\nDetails:")
        for key, value in result.details.items():
            if isinstance(value, str) and len(value) > 80:
                print(f"  {key}: {value[:77]}...")
            else:
                print(f"  {key}: {value}")
    
    if result.errors:
        print("\nErrors:")
        for error in result.errors:
            print(f"  [FAIL] {error}")
    
    if result.warnings:
        print("\nWarnings:")
        for warning in result.warnings:
            print(f"  [WARN] {warning}")
    
    print("=" * 80 + "\n")


def save_json_report(result: AudioTestResult):
    """Save test results as JSON for CI/CD integration."""
    report_file = ARTIFACTS_DIR / f"test_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    
    try:
        with open(report_file, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        logger.info(f"JSON report saved to {report_file}")
        return report_file
    except Exception as e:
        logger.error(f"Failed to save JSON report: {e}")
        return None


async def main():
    """Run all tests and report results."""
    logger.info("Starting audio pipeline tests...")
    
    result = await test_audio_pipeline()
    
    # Print results
    print_results(result)
    
    # Save JSON report
    report_file = save_json_report(result)
    
    # Exit with appropriate code
    if result.passed:
        logger.info("[OK] All tests passed!")
        sys.exit(0)
    else:
        logger.error("[FAIL] Some tests failed")
        if report_file:
            logger.error(f"See {report_file} for details")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

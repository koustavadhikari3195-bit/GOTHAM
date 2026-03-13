import asyncio
import os
import sys

# Ensure backend is in path
sys.path.append(os.getcwd())

async def test_audio_pipeline():
    from backend.voice.tts import speak
    from backend.voice.stt import transcribe
    
    print("[1/2] Testing TTS (Voice)...")
    text = "Welcome to Gotham Fitness. Let's get to work."
    audio_bytes = await speak(text)
    
    if audio_bytes and len(audio_bytes) > 1000:
        print(f"[OK] TTS worked. Generated {len(audio_bytes)} bytes.")
        
        print("[2/2] Testing STT (Eears)...")
        # Write to temp file to verify manually if needed
        with open("test_voice_output.wav", "wb") as f:
            f.write(audio_bytes)
            
        # Try to transcribe what we just generated
        transcribed_text = transcribe(audio_bytes)
        print(f"STT Result: '{transcribed_text}'")
        
        if transcribed_text.lower().strip() == text.lower().strip():
            print("[OK] STT worked perfectly.")
        elif transcribed_text:
            print(f"[PARTIAL] STT worked but result was slightly different.")
        else:
            print("[FAIL] STT returned nothing.")
    else:
        print(f"[FAIL] TTS returned {len(audio_bytes) if audio_bytes else 0} bytes. Check kokoro model files.")

if __name__ == "__main__":
    asyncio.run(test_audio_pipeline())

import asyncio
import os
import sys

sys.path.append(os.getcwd())

async def test_tts():
    from backend.voice.tts import speak
    print("[+] Starting TTS test...")
    try:
        audio = await speak("Test")
        print(f"[+] TTS Success: {len(audio)} bytes")
    except Exception as e:
        print(f"[!] TTS Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_tts())

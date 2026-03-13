import os
import sys

sys.path.append(os.getcwd())

def test_stt():
    from backend.voice.stt import transcribe
    print("[+] Starting STT test...")
    try:
        # Pass dummy empty bytes to see if it loads model
        text = transcribe(b"")
        print(f"[+] STT finished loading/running.")
    except Exception as e:
        print(f"[!] STT Error: {e}")

if __name__ == "__main__":
    test_stt()

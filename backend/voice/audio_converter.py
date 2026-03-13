"""
Audio format converter for Twilio phone integration.

Twilio sends:  mulaw (G.711), 8000 Hz, mono, base64-encoded
Whisper needs: PCM WAV, 16000 Hz, mono
Kokoro gives:  PCM WAV, variable Hz, mono or stereo
Twilio needs:  mulaw (G.711), 8000 Hz, mono, base64-encoded

NO DEPENDENCIES: This version uses pure Python to ensure compatibility 
with Python 3.13+ where 'audioop' was removed.
"""
import io
import wave
import struct

# Precomputed Mu-Law to Linear lookup table
MU_LAW_TO_LINEAR = []
for i in range(256):
    mu = ~i & 0xFF
    sign = (mu & 0x80)
    exponent = (mu >> 4) & 0x07
    mantissa = mu & 0x0F
    sample = (mantissa << 3) + 132
    sample <<= exponent
    sample -= 132
    MU_LAW_TO_LINEAR.append(-sample if sign else sample)

# Linear to Mu-Law lookup table
LINEAR_TO_MU_LAW = []
for i in range(65536):
    sample = i - 32768
    sign = 0x80 if sample < 0 else 0x00
    if sample < 0: sample = -sample
    sample += 132
    if sample > 32767: sample = 32767
    exponent = 7
    while exponent > 0 and not (sample & (1 << (exponent + 7))):
        exponent -= 1
    mantissa = (sample >> (exponent + 3)) & 0x0F
    mu = sign | (exponent << 4) | mantissa
    LINEAR_TO_MU_LAW.append(~mu & 0xFF)


def mulaw_to_wav(mulaw_bytes: bytes,
                  input_rate: int  = 8000,
                  output_rate: int = 16000) -> bytes:
    """
    Convert Twilio's mulaw audio to WAV PCM (upsampled).
    """
    # 1. Decode mulaw to 16-bit PCM
    pcm_16bit = []
    for b in mulaw_bytes:
        pcm_16bit.append(MU_LAW_TO_LINEAR[b])

    # 2. Simple Resampling (8k -> 16k is just doubling samples)
    if output_rate == input_rate * 2:
        resampled_pcm = []
        for s in pcm_16bit:
            resampled_pcm.extend([s, s])
    else:
        resampled_pcm = pcm_16bit

    # 3. Pack to bytes
    pcm_bytes = struct.pack('<' + 'h' * len(resampled_pcm), *resampled_pcm)

    # 4. Wrap in WAV
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(output_rate)
        wf.writeframes(pcm_bytes)
    
    return buf.getvalue()


def wav_to_mulaw(wav_bytes: bytes,
                  output_rate: int = 8000) -> bytes:
    """
    Convert WAV PCM to mulaw (downsampled and mixed to mono).
    """
    buf = io.BytesIO(wav_bytes)
    with wave.open(buf, 'rb') as wf:
        input_rate = wf.getframerate()
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        n_frames = wf.getnframes()
        raw_frames = wf.readframes(n_frames)

    # Unpack PCM data
    if sampwidth == 2:
        pcm_data = list(struct.unpack('<' + 'h' * (len(raw_frames) // 2), raw_frames))
    else:
        # Fallback for 8-bit or other widths if needed (not expected from Kokoro)
        return b''

    # Mix Stereo to Mono
    if n_channels == 2:
        mono_pcm = []
        for i in range(0, len(pcm_data), 2):
            mono_pcm.append((pcm_data[i] + pcm_data[i+1]) // 2)
        pcm_data = mono_pcm

    # Simple Downsampling (e.g., 24k -> 8k)
    if input_rate > output_rate:
        step = input_rate // output_rate
        pcm_data = pcm_data[::step]

    # Encode to Mu-Law
    mulaw_out = bytearray()
    for s in pcm_data:
        # Clamp and shift for index
        idx = max(0, min(65535, s + 32768))
        mulaw_out.append(LINEAR_TO_MU_LAW[idx])

    return bytes(mulaw_out)

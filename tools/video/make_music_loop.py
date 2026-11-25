"""Loops a short music track with crossfades: python tools/video/make_music_loop.py in.wav out.wav [copies] [fade_s]"""

import sys
import wave

import numpy as np

src, dst = sys.argv[1], sys.argv[2]
copies = int(sys.argv[3]) if len(sys.argv) > 3 else 3
fade = float(sys.argv[4]) if len(sys.argv) > 4 else 3.0

with wave.open(src, "rb") as w:
    ch, sw, sr = w.getnchannels(), w.getsampwidth(), w.getframerate()
    assert sw == 2, "16-bit wav expected"
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).reshape(-1, ch).astype(np.float32)

n = int(fade * sr)
ramp = np.linspace(0, 1, n, dtype=np.float32)[:, None]
out = x
for _ in range(copies - 1):
    mix = out[-n:] * (1 - ramp) + x[:n] * ramp
    out = np.concatenate([out[:-n], mix, x[n:]])

with wave.open(dst, "wb") as w:
    w.setnchannels(ch)
    w.setsampwidth(2)
    w.setframerate(sr)
    w.writeframes(np.clip(out, -32768, 32767).astype(np.int16).tobytes())
print(f"{len(out) / sr:.1f}s -> {dst}")

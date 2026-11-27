"""Adds the looped music under the silent render (fade in and out), and makes the smaller share copy.

    python tools/video/mix_music.py

Uses PyAV: the ffmpeg on this PC's PATH is too old to loop a track.
"""

from fractions import Fraction
from pathlib import Path

import av
import numpy as np

ROOT = Path(__file__).resolve().parents[2] / "video"
TRACK = ROOT / "music" / "track.mp3"
RATE, VOLUME, FADE_IN, FADE_OUT = 48000, 0.7, 2.0, 4.0


def music(seconds: float) -> np.ndarray:
    """Stereo float samples of the track, looped to length, with the fades."""
    resampler = av.AudioResampler(format="fltp", layout="stereo", rate=RATE)
    parts = []
    with av.open(str(TRACK)) as source:
        for frame in source.decode(audio=0):
            parts.extend(f.to_ndarray() for f in resampler.resample(frame))
    one = np.concatenate(parts, axis=1)
    wanted = int(seconds * RATE)
    sound = np.tile(one, (1, wanted // one.shape[1] + 1))[:, :wanted].astype(np.float32)
    t = np.arange(wanted) / RATE
    gain = VOLUME * np.clip(np.minimum(t / FADE_IN, (seconds - t) / FADE_OUT), 0, 1)
    return (sound * gain).astype(np.float32)


def write(silent: Path, out: Path, size: tuple[int, int] | None, crf: int | None, audio_kbps: int) -> None:
    """size and crf None: the video is copied untouched; otherwise it is re-encoded smaller."""
    with av.open(str(silent)) as source, av.open(str(out), "w", options={"movflags": "faststart"}) as target:
        video = source.streams.video[0]
        seconds = float(video.duration * video.time_base)
        if size:
            picture = target.add_stream("libx264", rate=Fraction(video.average_rate))
            picture.width, picture.height = size
            picture.pix_fmt = "yuv420p"
            picture.options = {"crf": str(crf), "preset": "medium"}
        else:
            picture = target.add_stream_from_template(video)
        sound_stream = target.add_stream("aac", rate=RATE)
        sound_stream.layout = "stereo"
        sound_stream.bit_rate = audio_kbps * 1000
        if size:
            for frame in source.decode(video):
                small = frame.reformat(width=size[0], height=size[1], format="yuv420p")
                small.pict_type = av.video.frame.PictureType.NONE
                target.mux(picture.encode(small))
            target.mux(picture.encode())
        else:
            for packet in source.demux(video):
                if packet.dts is not None:
                    packet.stream = picture
                    target.mux(packet)
        samples = music(seconds)
        for start in range(0, samples.shape[1], 1024):
            chunk = np.ascontiguousarray(samples[:, start : start + 1024])
            frame = av.AudioFrame.from_ndarray(chunk, format="fltp", layout="stereo")
            frame.sample_rate, frame.pts, frame.time_base = RATE, start, Fraction(1, RATE)
            target.mux(sound_stream.encode(frame))
        target.mux(sound_stream.encode())
    print(f"{out.name}: {seconds:.1f}s, {out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    silent = ROOT / "farm-demo-ar.silent.mp4"
    write(silent, ROOT / "farm-demo-ar.mp4", None, None, 192)
    write(silent, ROOT / "farm-demo-ar-share.mp4", (1280, 720), 27, 128)

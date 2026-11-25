"""Assembles the demo video from the captures and stills (docs/DEMO_VIDEO_PLAN.md).

    python tools/video/build_video.py [--preview]       # --preview: 640x360 at 10 fps (fast)

Inputs:  video/frames/*  (tools/video/capture.py)   video/assets/raw/still_*.png (tools/video/gen_stills.sh)
Output:  video/farm-demo-ar.mp4  (silent, or with video/music/track.* mixed under it when present)

Frames are composed here (pan and zoom, fades, Arabic captions rendered by Chrome so the text shapes
correctly) and piped to ffmpeg. Scenes are described in SCENES at the bottom.
"""

import io
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
FR = ROOT / "video" / "frames"
RAW = ROOT / "video" / "assets" / "raw"
OUT = ROOT / "video" / "farm-demo-ar.mp4"
PREVIEW = "--preview" in sys.argv
W, H, FPS = (640, 360, 10) if PREVIEW else (1920, 1080, 30)
BG = (11, 20, 26)
FADE = 0.45  # seconds, to and from black at every scene boundary

# ── captions: HTML rendered by Chrome into transparent PNGs ──────────────────
_CAPTIONS: dict[str, Image.Image] = {}
_browser = None


def caption_png(text: str, big: bool = False) -> Image.Image:
    key = f"{big}|{text}"
    if key in _CAPTIONS:
        return _CAPTIONS[key]
    global _browser
    if _browser is None:
        _pw = sync_playwright().start()
        _browser = _pw.chromium.launch(channel="chrome", headless=True)
    page = _browser.new_page(viewport={"width": 1920, "height": 1080})
    size, pad, bottom = (96, "26px 64px", "42%") if big else (50, "16px 40px", "56px")
    page.set_content(f"""<html dir="rtl"><body style="margin:0;background:transparent;width:1920px;height:1080px;position:relative;
      font-family:'IBM Plex Sans Arabic','Segoe UI',Tahoma,sans-serif">
      <div style="position:absolute;left:0;right:0;bottom:{bottom};display:flex;justify-content:center;padding:0 80px">
        <div style="background:rgba(11,20,26,{0.0 if big else 0.72});color:#F0F5F5;font-size:{size}px;font-weight:{700 if big else 600};
          padding:{pad};border-radius:18px;{'text-shadow:0 4px 30px rgba(0,0,0,.85);' if big else 'border:1px solid rgba(112,220,203,.35);'}
          text-align:center;line-height:1.35;max-width:1700px">{text}</div></div></body></html>""")
    img = Image.open(io.BytesIO(page.screenshot(omit_background=True))).convert("RGBA")
    page.close()
    if (W, H) != (1920, 1080):
        img = img.resize((W, H), Image.LANCZOS)
    _CAPTIONS[key] = img
    return img


# ── frame helpers ────────────────────────────────────────────────────────────
def ease(t: float) -> float:
    return t * t * (3 - 2 * t)


def fit169(img: Image.Image) -> Image.Image:
    w, h = img.size
    if w * 9 > h * 16:  # too wide: crop the sides
        nw = int(h * 16 / 9)
        return img.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    nh = int(w * 9 / 16)  # too tall: crop top and bottom
    return img.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))


def letterbox(img: Image.Image, canvas=(1920, 1080), margin=0.0) -> Image.Image:
    """The image centred on the dark background, as large as fits."""
    cw, ch = canvas
    s = min(cw * (1 - margin) / img.width, ch * (1 - margin) / img.height)
    im = img.resize((int(img.width * s), int(img.height * s)), Image.LANCZOS)
    out = Image.new("RGB", canvas, BG)
    out.paste(im, ((cw - im.width) // 2, (ch - im.height) // 2))
    return out


def kenburns(img: Image.Image, dur: float, views: list[tuple[float, float, float]]):
    """views: (zoom, cx, cy) keyframes, evenly spaced; cx, cy in 0..1. Yields RGB arrays."""
    img = img.convert("RGB")
    iw, ih = img.size
    n = max(1, int(dur * FPS))
    for i in range(n):
        t = i / max(1, n - 1) * (len(views) - 1)
        k = min(int(t), len(views) - 2) if len(views) > 1 else 0
        f = ease(t - k) if len(views) > 1 else 0
        a = views[k]
        b = views[k + 1] if len(views) > 1 else views[k]
        z, cx, cy = (a[j] + (b[j] - a[j]) * f for j in range(3))
        bw = iw / z
        bh = bw * 9 / 16
        if bh > ih:
            bh = ih / z
            bw = bh * 16 / 9
        x0 = min(max(cx * iw - bw / 2, 0), iw - bw)
        y0 = min(max(cy * ih - bh / 2, 0), ih - bh)
        yield np.asarray(img.crop((int(x0), int(y0), int(x0 + bw), int(y0 + bh))).resize((W, H), Image.BICUBIC))


def clip_frames(path: Path, start: float, dur: float, speed: float = 1.0):
    """Frames of a recorded clip, fitted on the dark canvas."""
    vf = f"setpts=PTS/{speed},fps={FPS},scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x0b141a"
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", str(start), "-t", str(dur * speed), "-i", str(path), "-vf", vf,
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    size = W * H * 3
    n = 0
    while n < int(dur * FPS):
        buf = p.stdout.read(size)
        if len(buf) < size:
            break
        yield np.frombuffer(buf, dtype=np.uint8).reshape(H, W, 3)
        n += 1
    p.stdout.close()
    p.wait()


def still(frame: np.ndarray, dur: float):
    for _ in range(int(dur * FPS)):
        yield frame


def static_canvas(img: Image.Image) -> np.ndarray:
    return np.asarray(letterbox(img, (W, H), 0.0).convert("RGB"))


def phones(names: list[str]) -> Image.Image:
    """Phone screenshots side by side on the dark background."""
    ph = [Image.open(FR / f"phone_{n}.png").convert("RGB") for n in names]
    h = int(H * 0.86)
    ims = [im.resize((int(im.width * h / im.height), h), Image.LANCZOS) for im in ph]
    total = sum(i.width for i in ims) + 60 * (len(ims) - 1)
    out = Image.new("RGB", (W, H), BG)
    x = (W - total) // 2
    for im in ims:
        out.paste(im, (x, (H - h) // 2))
        x += im.width + 60
    return out


# ── scene description ────────────────────────────────────────────────────────
def A(name: str) -> Image.Image:
    return Image.open(FR / f"{name}.png")


def S(name: str) -> Image.Image:
    return fit169(Image.open(RAW / f"{name}.png"))


def scenes():
    """(label, frames-generator factory, duration seconds, captions [(start, end, text, big)])."""
    dash = A("app_dashboard")
    hmi = lambda n: static_canvas(A(f"hmi_{n}"))
    yield ("title", lambda: kenburns(S("still_dawn"), 12, [(1.0, .5, .5), (1.14, .5, .5)]), 12,
           [(1.0, 11, "مزرعة الجروشي<br><span style='font-size:54px;font-weight:500'>ري ذكي بالكامل</span>", True)])
    yield ("problem", lambda: kenburns(S("still_manual"), 13, [(1.0, .5, .5), (1.18, .35, .5)]), 13,
           [(1.2, 12, "كل صمام يُفتح باليد، في كل موسم", False)])
    yield ("one_screen", lambda: kenburns(dash, 26, [(1.0, .5, .5), (1.9, .42, .72), (2.4, .12, .75), (2.1, .45, .12), (1.0, .5, .5)]), 26,
           [(1.0, 8, "كل المزرعة على شاشة واحدة", False), (8, 14, "الخريطة الحية: كل منطقة وحالتها", False),
            (14, 20, "الخزان والمضخات والضغط", False), (20, 25.5, "وموجز صباحي كتبه المستشار الذكي", False)])
    yield ("day", lambda: kenburns(A("app_schedules"), 10, [(1.0, .5, .5), (1.6, .55, .3)]), 10,
           [(1.0, 9.5, "جدول الري يعمل وحده: منطقة بعد منطقة", False)])
    yield ("running", lambda: clip_frames(FR / "live_session.webm", 8, 24), 24,
           [(1.0, 23, "الري يبدأ فعلاً: تدفق وضغط حقيقيان من وحدة التحكم", False)])
    yield ("zones", lambda: kenburns(A("app_zones"), 14, [(1.0, .5, .5), (1.8, .72, .2), (1.8, .3, .2)]), 14,
           [(1.0, 13.5, "كل منطقة: حالتها وتدفقها وضغطها لحظة بلحظة", False)])
    yield ("fault", lambda: clip_frames(FR / "live_session.webm", 38, 22), 22,
           [(1.5, 9, "عطل في مضخة التعزيز", False), (9, 21, "إنذار فوري بالعربية وإيقاف آمن للري", False)])
    yield ("advisor", lambda: kenburns(dash, 14, [(1.0, .5, .5), (2.7, .5, .12), (2.9, .45, .1)]), 14,
           [(1.0, 13.5, "مستشار ذكي: ماذا نسقي ومتى ولماذا", False)])
    yield ("panel_a", lambda: still(hmi("overview_idle"), 5), 5,
           [(0.8, 4.5, "وحدة تحكم صناعية، وشاشة لمس في غرفة التحكم", False)])
    yield ("panel_b", lambda: clip_frames(FR / "hmi_session.webm", 22, 20, 1.5), 20,
           [(1.0, 19, "من الشاشة: اختيار منطقة، ثم تشغيل", False)])
    yield ("panel_c", lambda: still(hmi("pumps_running"), 6), 6,
           [(0.8, 5.5, "المضخات والخزان والشبكة", False)])
    yield ("panel_d", lambda: kenburns(A("hmi_schedule"), 9, [(1.0, .5, .5), (1.5, .55, .4)]), 9,
           [(1.0, 8.5, "حتى لو انقطع الإنترنت يستمر الري بالجدول المحفوظ", False)])
    yield ("settings", lambda: still(hmi("settings"), 5), 5,
           [(0.8, 4.5, "تغيير وضع النظام من الشاشة مباشرة", False)])
    yield ("pocket", lambda: still(static_canvas(phones(["dashboard", "alarms", "zones"])), 14), 14,
           [(1.0, 13.5, "وفي جيبك: التقارير والإنذارات من أي مكان", False)])
    yield ("next_a", lambda: kenburns(S("still_soil"), 6, [(1.0, .5, .5), (1.12, .5, .5)]), 6,
           [(0.8, 5.5, "قريباً: حساسات رطوبة التربة", False)])
    yield ("next_b", lambda: kenburns(S("still_solar"), 6, [(1.0, .5, .5), (1.12, .5, .5)]), 6,
           [(0.8, 5.5, "الضخ بالطاقة الشمسية", False)])
    yield ("next_c", lambda: kenburns(S("still_camera"), 6, [(1.0, .5, .5), (1.12, .5, .5)]), 6,
           [(0.8, 5.5, "ومراقبة بالكاميرات", False)])
    yield ("close", lambda: kenburns(S("still_close"), 10, [(1.0, .5, .5), (1.12, .5, .5)]), 10,
           [(1.0, 9.5, "مزرعة الجروشي<br><span style='font-size:54px;font-weight:500'>ري أذكى لموسم أفضل</span>", True)])


def render() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    silent = OUT.with_suffix(".silent.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                           "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20" if not PREVIEW else "28",
                           "-preset", "medium" if not PREVIEW else "veryfast", str(silent)], stdin=subprocess.PIPE)
    total = 0.0
    for label, make, dur, caps in scenes():
        n = int(dur * FPS)
        overlays = [(a, b, caption_png(text, big)) for a, b, text, big in caps]
        count = 0
        for i, frame in enumerate(make()):
            t = i / FPS
            if i >= n:
                break
            im = frame
            for a, b, cap in overlays:
                if a <= t <= b:
                    k = min(1.0, (t - a) / 0.35, (b - t) / 0.35)
                    arr = np.asarray(cap, dtype=np.float32)
                    alpha = arr[..., 3:4] / 255.0 * max(0.0, k)
                    im = (im.astype(np.float32) * (1 - alpha) + arr[..., :3] * alpha).astype(np.uint8)
            fade = min(1.0, t / FADE, (dur - t) / FADE)
            if fade < 1.0:
                im = (im.astype(np.float32) * max(0.0, fade)).astype(np.uint8)
            ff.stdin.write(np.ascontiguousarray(im).tobytes())
            count += 1
        # a clip that ended early: hold the last frame so the scene keeps its length
        total += count / FPS
        print(f"{label}: {count / FPS:.1f}s", flush=True)
    ff.stdin.close()
    ff.wait()
    print(f"total {total:.0f}s -> {silent}")
    music = next(iter(sorted((ROOT / 'video' / 'music').glob('track.*'))), None)
    if music and not PREVIEW:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(silent), "-stream_loop", "-1", "-i", str(music), "-t", str(total),
                        "-af", f"afade=t=in:d=2,afade=t=out:st={total - 4}:d=4,volume=0.7", "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                        "-c:a", "libvo_aacenc", "-b:a", "192k", str(OUT)], check=True)
        print("music mixed ->", OUT)
    else:
        silent.replace(OUT)
        print("no music track: silent ->", OUT)


if __name__ == "__main__":
    render()

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
_CAPTIONS: dict = {}
_browser = None


def caption_png(text: str, big: bool = False):
    key = f"{big}|{text}"
    if key in _CAPTIONS:
        return _CAPTIONS[key]
    global _browser
    if _browser is None:
        _pw = sync_playwright().start()
        _browser = _pw.chromium.launch(channel="chrome", headless=True)
    page = _browser.new_page(viewport={"width": 1920, "height": 1080})
    size, pad, bottom = (110, "26px 64px", "42%") if big else (68, "18px 48px", "64px")
    page.set_content(f"""<html dir="rtl"><body style="margin:0;background:transparent;width:1920px;height:1080px;position:relative;
      font-family:'IBM Plex Sans Arabic','Segoe UI',Tahoma,sans-serif">
      <div style="position:absolute;left:0;right:0;bottom:{bottom};display:flex;justify-content:center;padding:0 80px">
        <div style="background:rgba(11,20,26,{0.0 if big else 0.88});color:#F0F5F5;font-size:{size}px;font-weight:{700 if big else 600};
          padding:{pad};border-radius:18px;{'text-shadow:0 4px 30px rgba(0,0,0,.85);' if big else 'border:1px solid rgba(112,220,203,.35);'}
          text-align:center;line-height:1.35;max-width:1700px">{text}</div></div></body></html>""")
    img = Image.open(io.BytesIO(page.screenshot(omit_background=True))).convert("RGBA")
    page.close()
    if (W, H) != (1920, 1080):
        img = img.resize((W, H), Image.LANCZOS)
    bb = img.getbbox() or (0, 0, 1, 1)
    img = (img.crop(bb), bb[0], bb[1])
    _CAPTIONS[key] = img
    return img


_TAGS: dict[str, Image.Image] = {}


def tag_png(text: str, size: int = 44) -> Image.Image:
    """A tight label (rounded dark pill) for callouts, rendered by Chrome, scaled to the output size."""
    key = f"{size}|{text}"
    if key in _TAGS:
        return _TAGS[key]
    global _browser
    if _browser is None:
        _pw = sync_playwright().start()
        _browser = _pw.chromium.launch(channel="chrome", headless=True)
    page = _browser.new_page(viewport={"width": 1200, "height": 300})
    page.set_content(f"""<html dir="rtl"><body style="margin:0;background:transparent"><div id="t" style="display:inline-block;
      background:#0b141a;color:#70dccb;border:3px solid #70dccb;border-radius:14px;padding:8px 22px;white-space:nowrap;
      font-family:'IBM Plex Sans Arabic','Segoe UI',Tahoma,sans-serif;font-size:{size}px;font-weight:700">{text}</div></body></html>""")
    box = page.locator("#t").bounding_box()
    img = Image.open(io.BytesIO(page.screenshot(omit_background=True, clip=box))).convert("RGBA")
    page.close()
    k = W / 1920
    if k != 1:
        img = img.resize((max(1, int(img.width * k)), max(1, int(img.height * k))), Image.LANCZOS)
    _TAGS[key] = img
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


def kenburns(img: Image.Image, dur: float, views: list[tuple[float, float, float]], post=None):
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
        arr = np.asarray(img.crop((int(x0), int(y0), int(x0 + bw), int(y0 + bh))).resize((W, H), Image.BICUBIC))
        yield post(arr, i / FPS, (x0, y0, bw, bh)) if post else arr


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


# ── effects: callouts, counters, dust, phone ─────────────────────────────────
import math

from PIL import ImageDraw, ImageFont

FONT = "C:/Windows/Fonts/segoeuib.ttf"
TEAL = (112, 220, 203)


def _with_alpha(img: Image.Image, a: float) -> Image.Image:
    if a >= 1:
        return img
    img = img.copy()
    img.putalpha(img.getchannel("A").point(lambda v: int(v * a)))
    return img


def _paste(base: Image.Image, img: Image.Image, x: float, y: float) -> None:
    x = int(min(max(x, 0), W - img.width))
    y = int(min(max(y, 0), H - img.height))
    base.alpha_composite(img, (x, y))


def fx(items: list[dict]):
    """Callouts in image coordinates: rings (x, y) or boxes (x, y, w, h), each with an optional label."""
    k = W / 1920

    def post(arr, t, g):
        x0, y0, bw, bh = g if g else (0, 0, W, H)
        base = Image.fromarray(arr).convert("RGBA")
        d = ImageDraw.Draw(base, "RGBA")
        for it in items:
            a = min(1.0, (t - it["t0"]) / 0.4, (it["t1"] - t) / 0.4)
            if a <= 0:
                continue
            sx, sy = (it["x"] - x0) / bw * W, (it["y"] - y0) / bh * H
            col = (*TEAL, int(255 * a))
            if "w" in it:
                ex, ey = (it["x"] + it["w"] - x0) / bw * W, (it["y"] + it["h"] - y0) / bh * H
                d.rounded_rectangle((sx, sy, ex, ey), 12 * k, outline=col, width=max(2, int(6 * k)))
                ax, ay_top, ay_bot = (sx + ex) / 2, sy, ey
            else:
                r = (52 + 9 * math.sin(t * 6)) * k * it.get("s", 1)
                d.ellipse((sx - r, sy - r, sx + r, sy + r), outline=col, width=max(2, int(6 * k)))
                ax, ay_top, ay_bot = sx, sy - r, sy + r
            if it.get("label"):
                tg = _with_alpha(tag_png(it["label"]), a)
                if it.get("below"):
                    _paste(base, tg, ax - tg.width / 2, ay_bot + 10 * k)
                else:
                    _paste(base, tg, ax - tg.width / 2, ay_top - tg.height - 10 * k)
        return np.asarray(base.convert("RGB"))

    return post


def counter(value: float, t0: float, dur: float, cx: float, cy: float, decimals=2, size=150, label=""):
    """A number counting up, centred at (cx, cy) as fractions of the frame."""
    k = W / 1920
    font = ImageFont.truetype(FONT, int(size * k))

    def post(arr, t, g):
        if t < t0:
            return arr
        a = min(1.0, (t - t0) / 0.3)
        txt = f"{value * ease(min(1.0, (t - t0) / dur)):.{decimals}f}"
        base = Image.fromarray(arr).convert("RGBA")
        d = ImageDraw.Draw(base, "RGBA")
        bb = d.textbbox((0, 0), txt, font=font)
        w, h = bb[2] - bb[0], bb[3] - bb[1]
        x, y = cx * W - w / 2, cy * H - h / 2
        pad = 32 * k
        d.rounded_rectangle((x - pad, y - pad, x + w + pad, y + h + pad), 22 * k, fill=(11, 20, 26, int(225 * a)),
                            outline=(*TEAL, int(255 * a)), width=max(2, int(4 * k)))
        d.text((x, y - bb[1]), txt, font=font, fill=(*TEAL, int(255 * a)))
        if label:
            tg = _with_alpha(tag_png(label, 46), a)
            _paste(base, tg, cx * W - tg.width / 2, y + h + pad + 12 * k)
        return np.asarray(base.convert("RGB"))

    return post


def dust(seed: int = 1, n: int = 36):
    """Slow drifting light motes over a still, so a photograph is never perfectly static."""
    rng = np.random.default_rng(seed)
    px, py = rng.random(n) * W, rng.random(n) * H
    vx, vy = (rng.random(n) - 0.3) * 22 * W / 1920, -(rng.random(n) * 14 + 4) * H / 1080
    rr = (rng.random(n) * 3.5 + 1.5) * W / 1920
    al = (rng.random(n) * 90 + 40).astype(int)

    def post(arr, t, g):
        base = Image.fromarray(arr).convert("RGBA")
        over = Image.new("RGBA", base.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(over)
        for i in range(n):
            x, y = (px[i] + vx[i] * t) % W, (py[i] + vy[i] * t) % H
            d.ellipse((x - rr[i], y - rr[i], x + rr[i], y + rr[i]), fill=(255, 240, 210, int(al[i])))
        base.alpha_composite(over)
        return np.asarray(base.convert("RGB"))

    return post


def darken(amount: float):
    def post(arr, t, g):
        return (arr.astype(np.float32) * (1 - amount)).astype(np.uint8)

    return post


def compose(*posts):
    posts = [p for p in posts if p]

    def post(arr, t, g):
        for p in posts:
            arr = p(arr, t, g)
        return arr

    return post


def phone_post(shot: str, tags: list[tuple[float, float, float, str]]):
    """A phone sliding up over the frame showing a real screenshot; tags = (t0, y_frac_of_phone, x_offset, label)."""
    ph = Image.open(FR / f"phone_{shot}.png").convert("RGB")
    h = int(H * 0.9)
    w = int(ph.width * h / ph.height)
    ph = ph.resize((w, h), Image.LANCZOS)
    r = int(40 * W / 1920)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w, h), r, fill=255)
    bez = int(12 * W / 1920)
    frame = Image.new("RGBA", (w + 2 * bez, h + 2 * bez), (0, 0, 0, 0))
    ImageDraw.Draw(frame).rounded_rectangle((0, 0, w + 2 * bez - 1, h + 2 * bez - 1), r + bez, fill=(30, 40, 46, 255),
                                            outline=(112, 220, 203, 255), width=max(2, int(3 * W / 1920)))
    frame.paste(ph, (bez, bez), mask)

    def post(arr, t, g):
        f = ease(min(1.0, t / 0.9))
        top = (H - frame.height) / 2
        y = top + (1 - f) * (H - top)
        base = Image.fromarray(arr).convert("RGBA")
        x = (W - frame.width) / 2
        base.alpha_composite(frame, (int(x), int(y))) if y < H else None
        for t0, yf, xo, label in tags:
            if t >= t0:
                a = min(1.0, (t - t0) / 0.4)
                tg = _with_alpha(tag_png(label), a)
                _paste(base, tg, x + frame.width + xo * W / 1920 if xo >= 0 else x + xo * W / 1920 - tg.width, top + yf * frame.height - tg.height / 2)
        return np.asarray(base.convert("RGB"))

    return post


# ── scene description ────────────────────────────────────────────────────────
def A(name: str) -> Image.Image:
    return Image.open(FR / f"{name}.png")


def S(name: str) -> Image.Image:
    return fit169(Image.open(RAW / f"{name}.png"))


def scenes():
    """(label, frames factory, duration s, captions [(start, end, text, big)], fade seconds)."""
    dash = A("app_dashboard")
    live_alarm = A("live_alarms_fault")
    hmi = lambda n: static_canvas(A(f"hmi_{n}"))
    punch = lambda name, d, v=1.16, cx=.5, cy=.5, seed=1: (
        lambda: kenburns(S(name), d, [(1.0, cx, cy), (v, cx, cy)], dust(seed)))

    # the hook: pain, then the answer
    yield ("hook_valve", punch("s2_valve", 3.2, 1.18, .5, .55, 1), 3.2, [(0.2, 3.0, "كل صمام يُفتح باليد", False)], 0.15)
    yield ("hook_dry", punch("s2_dry", 2.6, 1.16, .5, .5, 2), 2.6, [(0.2, 2.4, "كل صباح... وكل موسم", False)], 0.15)
    yield ("hook_night", punch("s2_night", 3.6, 1.18, .5, .5, 3), 3.6, [(0.3, 3.4, "ماذا لو سقت المزرعة نفسها؟", False)], 0.25)
    yield ("title", lambda: kenburns(dash, 5, [(1.7, .62, .78), (2.1, .6, .8)], darken(.55)), 5,
           [(0.5, 4.6, "مزرعة الجروشي<br><span style='font-size:60px;font-weight:500'>ري ذكي بالكامل</span>", True)], 0.3)
    yield ("map", lambda: kenburns(dash, 12, [(1.9, .53, .76), (2.3, .53, .82)], fx([
        dict(x=1077, y=660, t0=1.5, t1=6, label="كل منطقة وحالتها"),
        dict(x=958, y=825, t0=6, t1=11.5, label="الخزان والمضخات")])), 12,
        [(0.6, 5.8, "كل المزرعة على شاشة واحدة", False), (6.2, 11.6, "الخريطة حيّة، لحظة بلحظة", False)], 0.4)
    yield ("advisor", lambda: kenburns(dash, 11, [(1.25, .5, .19), (1.25, .5, .19), (1.7, .3, .22)], fx([
        dict(x=75, y=158, w=1545, h=82, t0=1.2, t1=5.6, label="ملخص كتبه المستشار الذكي"),
        dict(x=45, y=275, w=515, h=70, t0=6.2, t1=10.4, label="توقعات الطقس")])), 11,
        [(0.6, 5.8, "مستشار ذكي يكتب موجز الصباح", False), (6.2, 10.6, "من الطقس والمياه والإنذارات", False)], 0.4)
    yield ("running", lambda: clip_frames(FR / "live_session.webm", 9, 12), 12,
           [(0.6, 11.4, "الري يبدأ فعلاً: تدفق وضغط حقيقيان", False)], 0.4)
    yield ("fault", lambda: clip_frames(FR / "live_session.webm", 38, 6), 6,
           [(0.4, 5.6, "عطل في مضخة التعزيز", False)], 0.3)
    yield ("alarm", lambda: kenburns(live_alarm, 7, [(1.0, .5, .5), (1.9, .6, .2)], fx([
        dict(x=24, y=212, w=1290, h=58, t0=1.5, t1=6.6, label="إنذار فوري بالعربية")])), 7,
        [(0.5, 6.5, "إنذار فوري، وإيقاف آمن للري", False)], 0.3)
    yield ("reports", lambda: kenburns(A("app_reports"), 11, [(1.0, .5, .5), (1.25, .5, .42)], counter(
        115.79, 1.2, 3.5, .5, .64, 2, 130, "م³ مياه في 7 أيام")), 11,
        [(0.6, 5.5, "تقارير الري واستهلاك المياه", False), (5.8, 10.6, "كل منطقة، كل يوم، كل دورة", False)], 0.4)
    yield ("phone", lambda: kenburns(S("s2_night"), 9, [(1.1, .5, .5), (1.25, .5, .5)], compose(
        darken(.55), phone_post("alarms", [(2.0, .38, 30, "خطأ متكرر في المنطقة"), (3.2, .59, 30, "لم يتم اكتشاف تدفق")]))), 9,
        [(0.6, 8.6, "الإنذارات في جيبك، أينما كنت", False)], 0.4)
    yield ("panel", lambda: clip_frames(FR / "hmi_session.webm", 22, 12, 1.5), 12,
           [(0.6, 11.4, "وشاشة لمس في غرفة التحكم", False)], 0.4)
    yield ("offline", lambda: kenburns(A("hmi_schedule"), 5, [(1.0, .5, .5), (1.4, .55, .4)]), 5,
           [(0.4, 4.6, "وبلا إنترنت: الري يستمر بجدوله", False)], 0.3)
    yield ("next_a", punch("s2_soil", 3.5, 1.14, .5, .5, 4), 3.5, [(0.3, 3.3, "قريباً: حساسات رطوبة التربة", False)], 0.25)
    yield ("next_b", punch("s2_solar", 3.5, 1.14, .5, .5, 5), 3.5, [(0.3, 3.3, "ضخٌّ بالطاقة الشمسية", False)], 0.25)
    yield ("next_c", punch("s2_camera", 3.5, 1.14, .5, .5, 6), 3.5, [(0.3, 3.3, "ومراقبة بالكاميرات", False)], 0.25)
    yield ("close", lambda: kenburns(S("s2_close"), 6, [(1.0, .5, .5), (1.12, .5, .5)], compose(dust(7), darken(.25))), 6,
           [(0.5, 5.6, "مزرعة الجروشي<br><span style='font-size:60px;font-weight:500'>ري أذكى لموسم أفضل</span>", True)], 0.5)



def render() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    silent = OUT.with_suffix(".silent.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                           "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20" if not PREVIEW else "28",
                           "-preset", "medium" if not PREVIEW else "veryfast", str(silent)], stdin=subprocess.PIPE)
    total = 0.0
    for label, make, dur, caps, fade_s in scenes():
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
                    ci, cx0, cy0 = cap
                    arr = np.asarray(ci, dtype=np.float32)
                    alpha = arr[..., 3:4] / 255.0 * max(0.0, k)
                    im = np.array(im, copy=True)
                    reg = im[cy0:cy0 + arr.shape[0], cx0:cx0 + arr.shape[1]]
                    im[cy0:cy0 + arr.shape[0], cx0:cx0 + arr.shape[1]] = (reg.astype(np.float32) * (1 - alpha) + arr[..., :3] * alpha).astype(np.uint8)
            fade = min(1.0, t / fade_s, (dur - t) / fade_s)
            if fade < 1.0:
                im = ((im.astype(np.uint16) * int(255 * max(0.0, fade))) >> 8).astype(np.uint8)
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

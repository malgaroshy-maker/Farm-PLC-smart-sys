"""The family video of 2026-11-27 (about 2:50) (docs/DEMO_VIDEO_PLAN.md).

    python tools/video/build_video3.py [--preview]      # --preview: 640x360 at 10 fps

Inputs: video/assets/v3/clips (MAGI-2), video/assets/v3/*.png (Codex stills), video/assets/v3/app (capture3.py, capture4.py),
video/frames/hmi_session.webm (capture.py hmi), video/refs (the owners' photos, no people used),
video/music/track.*. The drawing helpers come from build_video.py.
"""

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

import build_video as bv

V3 = bv.ROOT / "video" / "assets" / "v3"
APP = V3 / "app"
CLIPS = V3 / "clips"
bv.OUT = bv.ROOT / "video" / "farm-demo-ar.mp4"
if bv.PREVIEW:
    bv.OUT = bv.ROOT / "video" / "_pv" / "farm-demo-ar-preview.mp4"
W, H = bv.W, bv.H
K = W / 1920
CLIP_SECONDS = 4.2

# warm, blurred and darkened farm view behind every screen
_BACK = (
    Image.open(V3 / "v8_evening.png")
    .convert("RGB")
    .resize((W, H), Image.LANCZOS)
    .filter(ImageFilter.GaussianBlur(18 * K))
    .point(lambda v: int(v * 0.34))
)


def app(name: str) -> Image.Image:
    """A capture, lifted a little: the app's dark theme is hard to read on a phone screen."""
    shot = Image.open(APP / f"{name}.png").convert("RGB")
    shot = shot.point([min(255, round(255 * (v / 255) ** 0.8 * 1.06)) for v in range(256)] * 3)
    return ImageEnhance.Sharpness(shot).enhance(1.2)


def ring(shot: Image.Image, x: int, y: int, w: int, h: int) -> Image.Image:
    """Marks the button being pressed."""
    d = ImageDraw.Draw(shot)
    d.rounded_rectangle((x - w // 2, y - h // 2, x + w // 2, y + h // 2), h // 3, outline=(255, 213, 79), width=7)
    return shot


def clip(name: str, seconds: float, post=None):
    """A MAGI-2 clip slowed just enough to fill the scene."""

    def make():
        speed = min(1.0, CLIP_SECONDS / seconds)
        for i, frame in enumerate(bv.clip_frames(CLIPS / f"{name}.mp4", 0, seconds, speed)):
            yield post(frame, i / bv.FPS, None) if post else frame

    return make


def _rounded(img: Image.Image, radius: int) -> Image.Image:
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.width - 1, img.height - 1), radius, fill=255)
    out = img.convert("RGBA")
    out.putalpha(mask)
    return out


def device(shot: Image.Image, width: int, bezel: int, radius: int, base: int = 0) -> Image.Image:
    """A screen in a dark frame; base > 0 adds a laptop foot."""
    shot = shot.convert("RGB")
    height = round(shot.height * width / shot.width)
    screen = _rounded(shot.resize((width, height), Image.LANCZOS), radius // 2)
    out = Image.new("RGBA", (width + 2 * bezel + 2 * base, height + 2 * bezel + (base // 2)), (0, 0, 0, 0))
    d = ImageDraw.Draw(out)
    d.rounded_rectangle((base, 0, base + width + 2 * bezel - 1, height + 2 * bezel - 1), radius,
                        fill=(24, 30, 34, 255), outline=(92, 104, 112, 255), width=max(1, int(2 * K)))
    out.alpha_composite(screen, (base + bezel, bezel))
    if base:
        d.rounded_rectangle((0, height + 2 * bezel - 2, out.width - 1, out.height - 1), base // 4, fill=(70, 80, 88, 255))
    return out


def canvas(*items: tuple[Image.Image, float, float]) -> Image.Image:
    """Devices placed by their centre (fractions of the frame) on the farm background."""
    out = _BACK.convert("RGBA")
    for img, cx, cy in items:
        x, y = int(cx * W - img.width / 2), int(cy * H - img.height / 2)
        shadow = Image.new("RGBA", out.size, (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle((x + 8, y + 22, x + img.width + 8, y + img.height + 22), int(30 * K),
                                                 fill=(0, 0, 0, 150))
        out.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(22 * K)))
        out.alpha_composite(img, (x, y))
    return out.convert("RGB")


def simulation_label():
    """Every screen says what it is: nothing here was filmed on the installed system."""
    tag = bv.tag_png("محاكاة", 30)

    def post(arr, t, g):
        base = Image.fromarray(arr).convert("RGBA")
        base.alpha_composite(tag, (int(36 * K), int(30 * K)))
        return np.asarray(base.convert("RGB"))

    return post


def laptop(name: str, seconds: float, views=((1.0, 0.5, 0.5), (1.14, 0.5, 0.45)), crop=None):
    def make():
        shot = app(name)
        if crop:
            shot = shot.crop(crop)
        framed = device(shot, int(1500 * K), int(16 * K), int(30 * K), base=int(70 * K))
        return bv.kenburns(canvas((framed, 0.5, 0.455)), seconds, list(views), simulation_label())

    return make


def card(name: str, seconds: float, boxes: list[tuple[int, int, int, int]], width: int = 900, tap=None):
    """Parts of one real screen, stacked, for text that is too small on the whole page."""

    def make():
        shot = app(name)
        if tap:
            shot = ring(shot, *tap)
        parts = [shot.crop(box) for box in boxes]
        joined = Image.new("RGB", (parts[0].width, sum(part.height for part in parts)), (30, 30, 34))
        y = 0
        for part in parts:
            joined.paste(part, (0, y))
            y += part.height
        # never taller than the space above the caption
        fitted = min(width, int(880 * joined.width / joined.height))
        framed = device(joined, int(fitted * K), int(16 * K), int(30 * K))
        return bv.kenburns(canvas((framed, 0.5, 0.445)), seconds, [(1.0, 0.5, 0.5), (1.05, 0.5, 0.47)],
                           simulation_label())

    return make


def panel_still(name: str, seconds: float):
    def make():
        framed = device(Image.open(bv.FR / f"{name}.png"), int(1340 * K), int(20 * K), int(26 * K))
        return bv.kenburns(canvas((framed, 0.5, 0.455)), seconds, [(1.0, 0.5, 0.5), (1.18, 0.5, 0.4)], simulation_label())

    return make


def phones(names: list[str], seconds: float):
    """Two phone screens; the first one is on the right, as Arabic is read."""

    def make():
        first, second = (device(app(n), int(405 * K), int(14 * K), int(54 * K)) for n in names)
        return bv.kenburns(canvas((first, 0.65, 0.445), (second, 0.35, 0.445)), seconds,
                           [(1.0, 0.5, 0.5), (1.05, 0.5, 0.47)], simulation_label())

    return make


def panel(seconds: float, start: float, speed: float = 1.0):
    def make():
        label = simulation_label()
        for i, frame in enumerate(bv.clip_frames(bv.FR / "hmi_session.webm", start, seconds, speed)):
            screen = Image.fromarray(frame)
            # the recording is 16:10, so clip_frames pads its sides
            inner = int(H * 1.6)
            screen = screen.crop(((W - inner) // 2, 0, (W + inner) // 2, H))
            framed = device(screen, int(1340 * K), int(20 * K), int(26 * K))
            yield label(np.asarray(canvas((framed, 0.5, 0.455))), i / bv.FPS, None)

    return make


def photo(path: Path, seconds: float, shade: float, views=((1.0, 0.5, 0.5), (1.12, 0.5, 0.48)), post=None):
    def make():
        img = bv.fit169(Image.open(path))
        return bv.kenburns(img, seconds, list(views), bv.compose(bv.darken(shade) if shade else None, post))

    return make


def two(first: str, second: str, seconds: float):
    """Two captions that share a scene."""
    middle = seconds / 2
    return [(0.25, middle - 0.05, first, False), (middle + 0.05, seconds - 0.2, second, False)]


def one(text: str, seconds: float, big: bool = False):
    return [(0.3, seconds - 0.2, text, big)]


def sub(title: str, line: str) -> str:
    return f"{title}<br><span style='font-size:58px;font-weight:500'>{line}</span>"


HEADER = (0, 0, 690, 112)
START_PARTS = [HEADER, (0, 750, 690, 1080)]
RUN_PARTS = [HEADER, (0, 140, 690, 540), (0, 800, 690, 1080)]


def ask(name: str, question: str, seconds: float, top: int):
    """A question put to the assistant, and its real answer (the chat's message area)."""
    caption = f"<span style='font-size:48px;font-weight:500'>نسأل المساعد: </span><span style='font-size:54px'>{question}</span>"
    return (f"ai_{name}", card(f"ai_{name}", seconds, [(24, top, 654, 826)], 1400), seconds, one(caption, seconds), 0.25)


def scenes():
    # ── the problem ──
    yield ("valve", clip("v1_valve", 5.4), 5.4, one("كل صمام يُفتح ويُغلق باليد", 5.4), 0.15)
    yield ("night", clip("v2_night", 7), 7, two("وإن مرض العامل أو نسي الموعد؟", "الترتيب والتوقيت لا يعرفهما إلا هو", 7), 0.2)
    yield ("leak", clip("v3_leak", 5.4), 5.4, one("تسرّب لا يلاحظه أحد: ماء ووقود يضيعان", 5.4), 0.2)
    yield ("power", clip("v4_pump", 6.4), 6.4, two("انقطعت الكهرباء؟ تعطلت المضخة؟", "ومن يعيد التشغيل؟", 6.4), 0.2)
    yield ("heat", clip("v5_heat", 7), 7, two("ماء أقل أو أكثر من الحاجة، وسقيٌ قبل المطر", "ولا نكتشف ذلك إلا متأخرين", 7), 0.2)
    yield ("unaware", photo(V3 / "v6_unaware.png", 6.6, 0.0, ((1.0, 0.5, 0.5), (1.14, 0.42, 0.62))), 6.6,
           two("ونحن أصحابها لا نعرف شيئاً إلا إذا ذهبنا", "ولا سجلّ للماء", 6.6), 0.25)
    # ── the turn ──
    yield ("water", clip("v7_water", 6.4), 6.4, two("ماذا لو سقت المزرعة نفسها…", "وأخبرتنا بكل شيء؟", 6.4), 0.3)
    yield ("title", photo(V3 / "refs" / "ref_03.jpg", 4, 0.42), 4, one(sub("مزرعة الجروشي", "ري ذكي"), 4, True), 0.35)
    # ── the whole farm ──
    yield ("map", laptop("map_running", 7, ((1.1, 0.45, 0.55), (1.9, 0.44, 0.66))), 7,
           two("كل المزرعة على شاشة واحدة", "ونرى أي منطقة تُروى الآن", 7), 0.3)
    yield ("schedules", laptop("schedules", 4.4, ((1.15, 0.42, 0.42), (1.35, 0.42, 0.42))), 4.4,
           one("الجدول يعمل وحده", 4.4), 0.3)
    # ── each zone, by hand when we want ──
    yield ("zones", laptop("zones_list", 4.2, ((1.2, 0.38, 0.5), (1.45, 0.38, 0.55))), 4.2,
           one("اثنتا عشرة منطقة، ولكل منطقة حالتها", 4.2), 0.3)
    yield ("choose", card("desk_choose", 4.2, START_PARTS, 1000, tap=(321, 1035, 600, 76)), 4.2,
           one("نختار المنطقة والمدة، ثم «بدء الري»", 4.2), 0.25)
    yield ("confirm", card("desk_confirm", 3.6, START_PARTS, 1000, tap=(400, 1035, 500, 76)), 3.6,
           one("وضغطة ثانية للتأكيد", 3.6), 0.2)
    yield ("running", card("desk_running", 5.4, RUN_PARTS, 1000), 5.4,
           one("تعمل المنطقة: التدفق والضغط والوقت المتبقي", 5.4), 0.25)
    yield ("stopzone", card("desk_stop_button", 3.6, RUN_PARTS, 1000, tap=(339, 900, 590, 80)), 3.6,
           one("ونوقفها متى شئنا", 3.6), 0.2)
    # ── safety ──
    yield ("fault", laptop("alarms", 5, ((1.15, 0.45, 0.3), (1.6, 0.45, 0.27))), 5,
           one("عطل في المضخة؟ إنذار فوري وإيقاف آمن", 5), 0.3)
    yield ("stop", laptop("stop_all_confirmed", 4.8, ((1.2, 0.4, 0.25), (1.6, 0.35, 0.18))), 4.8,
           one("زر واحد يوقف كل شيء", 4.8), 0.3)
    yield ("offline", laptop("offline", 4.4, ((1.35, 0.45, 0.2), (1.5, 0.45, 0.2))), 4.4,
           one("انقطع الاتصال؟ يخبرنا التطبيق بوضوح", 4.4), 0.3)
    yield ("keeps", panel_still("hmi_schedule", 4.6), 4.6, one("ووحدة التحكم تحفظ الجدول بلا إنترنت", 4.6), 0.3)
    # ── an assistant we can ask about anything on the farm ──
    yield ("assistant", photo(V3 / "v7_water.png", 3.8, 0.62), 3.8,
           one(sub("مساعد ذكي", "نسأله بالعربية عن المزرعة"), 3.8, True), 0.3)
    yield ask("now", "ما حالة المزرعة الآن؟", 6.8, 532)
    yield ask("next", "متى الري القادم ولأي منطقة؟", 5.6, 588)
    yield ask("weather", "هل أسقي الرمان اليوم مع هذا الطقس؟", 8, 532)
    yield ask("pump", "لماذا تعطلت المضخة وماذا أفعل؟", 8, 474)
    # ── the phone does it all ──
    yield ("ph_home", phones(["ph_home", "ph_map"], 5), 5, one("وفي الهاتف: المزرعة والخريطة والخزان", 5), 0.3)
    yield ("ph_start", phones(["ph_zones", "ph_confirm"], 4.8), 4.8, one("نشغّل أي منطقة من الهاتف", 4.8), 0.25)
    yield ("ph_run", phones(["ph_running", "ph_stopped"], 4.8), 4.8, one("نتابعها وهي تروي، ثم نوقفها", 4.8), 0.25)
    yield ("ph_more", phones(["ph_schedules", "phone_alarms"], 4.8), 4.8, one("والجداول والإنذارات معنا أينما كنا", 4.8), 0.25)
    # ── the control room, and each of us ──
    yield ("panel", panel(5, 18, 1.4), 5, one("وشاشة لمس عربية في غرفة التحكم", 5), 0.3)
    yield ("users", laptop("users", 3.8, ((1.3, 0.42, 0.28), (1.45, 0.42, 0.28))), 3.8, one("ولكلٍّ منا حسابه", 3.8), 0.25)
    # ── where we are, and the ending ──
    yield ("today", photo(V3 / "v1_valve.png", 7.4, 0.7), 7.4, [
        (0.4, 7.1, "<div style='margin-bottom:12px'>جُرّب النظام بالمحاكاة مع وحدة تحكم افتراضية</div>"
                   "<span style='font-size:52px;font-weight:500'>الخطوة القادمة: تجربة ميدانية على منطقة واحدة</span>", False)
    ], 0.4)
    yield ("peace", clip("v8_evening", 7, bv.darken(0.12)), 7,
           [(0.5, 3.4, "مزرعتنا بخير… ونحن مطمئنون", False),
            (3.7, 6.8, sub("مزرعة الجروشي", "ري أذكى لموسم أفضل"), True)], 0.6)


bv.scenes = scenes

if __name__ == "__main__":
    bv.render()

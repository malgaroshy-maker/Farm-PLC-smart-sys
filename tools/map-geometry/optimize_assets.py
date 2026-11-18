"""Raw Codex images (design/assets-raw) → web-ready WebP.

apps/web/public/map/
- tex_*:  resized to 512 px wide (tiles in SVG patterns)
- spr_*:  magenta (#FF00FF) chroma-keyed to alpha, trimmed, 384 px max
- tree_*: chroma-keyed, trimmed, 256 px max (one sprite per tree on the map)
- logo:   keeps its alpha, 256 px
apps/web/public/art/
- detail_*, empty_*: 900 px wide photos;  login_*: 1600 px wide
"""

import glob
import os
import sys

import cv2
import numpy as np

src, dst = sys.argv[1], sys.argv[2]
os.makedirs(dst, exist_ok=True)


def key_magenta(img):
    """Chroma-key a #FF00FF background with colour un-mixing (no purple halo).

    Each edge pixel is modelled as  observed = a*fg + (1-a)*magenta.  Alpha comes from
    how magenta-ish the pixel is; the true foreground colour is then solved for, so
    fine foliage keeps its real green instead of a pink fringe.
    """
    bgr = img[:, :, :3].astype(np.float32)
    b, g, r = bgr[:, :, 0], bgr[:, :, 1], bgr[:, :, 2]
    magentaness = np.clip((np.minimum(r, b) - g) / 255.0, 0, 1)  # 1 for pure #FF00FF
    alpha = np.clip(1.0 - (magentaness - 0.08) / 0.55, 0, 1)
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0)
    key = np.array([255.0, 0.0, 255.0], np.float32)  # BGR magenta
    a = np.maximum(alpha, 1e-3)[..., None]
    fg = (bgr - (1 - a) * key) / a
    fg = np.clip(fg, 0, 255)
    # remaining edge tint: never let an edge pixel be more magenta than its interior allows
    edge = (alpha < 0.95)[..., None]
    gch = fg[:, :, 1:2]
    fg[:, :, 0:1] = np.where(edge, np.minimum(fg[:, :, 0:1], gch + 25), fg[:, :, 0:1])
    fg[:, :, 2:3] = np.where(edge, np.minimum(fg[:, :, 2:3], gch + 40), fg[:, :, 2:3])
    alpha[alpha < 0.04] = 0
    return np.dstack([fg.astype(np.uint8), (alpha * 255).astype(np.uint8)])


def trim(rgba, pad=6):
    ys, xs = np.where(rgba[:, :, 3] > 8)
    y0, y1 = max(ys.min() - pad, 0), min(ys.max() + pad, rgba.shape[0])
    x0, x1 = max(xs.min() - pad, 0), min(xs.max() + pad, rgba.shape[1])
    return rgba[y0:y1, x0:x1]


def fit(img, max_side):
    h, w = img.shape[:2]
    s = max_side / max(h, w)
    return cv2.resize(img, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA) if s < 1 else img


art = os.path.join(os.path.dirname(dst.rstrip("/\\")), "art")
os.makedirs(art, exist_ok=True)

for path in sorted(glob.glob(os.path.join(src, "*.png"))):
    name = os.path.splitext(os.path.basename(path))[0]
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    out_dir = dst
    if name.startswith(("detail_", "empty_", "login_")):
        width = 1600 if name.startswith("login_") else 900
        h, w = img.shape[:2]
        img = cv2.resize(img[:, :, :3], (width, round(width * h / w)), interpolation=cv2.INTER_AREA)
        out = os.path.join(art, f"{name}.webp")
        cv2.imwrite(out, img, [cv2.IMWRITE_WEBP_QUALITY, 80])
        print(f"{name:24s} {img.shape[1]}x{img.shape[0]}  {os.path.getsize(out) // 1024} KB  (art)")
        continue
    if name.startswith("tree_"):
        img = fit(trim(key_magenta(img[:, :, :3])), 256)
        q = 86
    elif name.startswith("spr_"):
        if img.shape[2] == 3 or img[:, :, 3].min() == 255:
            img = key_magenta(img if img.shape[2] == 3 else img[:, :, :3])
        img = fit(trim(img), 384)
        q = 88
    elif name == "logo":
        img = fit(trim(img), 256)
        q = 92
    else:
        h, w = img.shape[:2]
        img = cv2.resize(img[:, :, :3], (512, round(512 * h / w)), interpolation=cv2.INTER_AREA)
        q = 80
    out = os.path.join(dst, f"{name}.webp")
    cv2.imwrite(out, img, [cv2.IMWRITE_WEBP_QUALITY, q])
    print(f"{name:24s} {img.shape[1]}x{img.shape[0]}  {os.path.getsize(out) // 1024} KB")

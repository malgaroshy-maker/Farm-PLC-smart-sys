"""Raw Codex images (design/assets-raw) → web-ready WebP (apps/web/public/map).

- textures: resized to 512 px wide (tiles in SVG patterns)
- spr_*: magenta (#FF00FF) chroma-keyed to alpha, trimmed, 384 px max
- logo: keeps its alpha, 256 px
"""

import glob
import os
import sys

import cv2
import numpy as np

src, dst = sys.argv[1], sys.argv[2]
os.makedirs(dst, exist_ok=True)


def key_magenta(img):
    bgr = img[:, :, :3].astype(np.int16)
    b, g, r = bgr[:, :, 0], bgr[:, :, 1], bgr[:, :, 2]
    # distance from pure magenta; soft edge for anti-aliased borders
    mag = np.clip((np.minimum(r, b) - g - 60) / 80.0, 0, 1)  # 1 = magenta
    alpha = ((1 - mag) * 255).astype(np.uint8)
    # despill: pull magenta tint out of edge pixels
    spill = (np.minimum(r, b) - g).clip(0) * mag
    out = img[:, :, :3].astype(np.float32)
    out[:, :, 0] -= spill * 0.8
    out[:, :, 2] -= spill * 0.8
    out = out.clip(0, 255).astype(np.uint8)
    return np.dstack([out, alpha])


def trim(rgba, pad=6):
    ys, xs = np.where(rgba[:, :, 3] > 8)
    y0, y1 = max(ys.min() - pad, 0), min(ys.max() + pad, rgba.shape[0])
    x0, x1 = max(xs.min() - pad, 0), min(xs.max() + pad, rgba.shape[1])
    return rgba[y0:y1, x0:x1]


def fit(img, max_side):
    h, w = img.shape[:2]
    s = max_side / max(h, w)
    return cv2.resize(img, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA) if s < 1 else img


for path in sorted(glob.glob(os.path.join(src, "*.png"))):
    name = os.path.splitext(os.path.basename(path))[0]
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if name.startswith("spr_"):
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
    print(f"{name:18s} {img.shape[1]}x{img.shape[0]}  {os.path.getsize(out) // 1024} KB")

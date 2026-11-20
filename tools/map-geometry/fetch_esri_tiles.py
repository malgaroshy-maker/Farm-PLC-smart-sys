"""Stitch Esri World Imagery tiles for the farm bbox for TRACING/CHECKING only (not shipped in the app).
Attribution: Source: Esri, Maxar, Earthstar Geographics. Usage: python fetch_esri_tiles.py [zoom=17] -> farm_esri_z17.jpg + .json
Run it inside design/satellite/ (git-ignored)."""

import io
import json
import math
import sys

import httpx
from PIL import Image

LAT_MIN, LAT_MAX = 32.51265, 32.51985
LON_MIN, LON_MAX = 14.06610, 14.07462
Z = int(sys.argv[1]) if len(sys.argv) > 1 else 17
URL = "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"


def to_px(lat, lon, z):
    n = 256 * 2**z
    x = (lon + 180) / 360 * n
    s = math.sin(math.radians(lat))
    y = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n
    return x, y


x0, y0 = to_px(LAT_MAX, LON_MIN, Z)
x1, y1 = to_px(LAT_MIN, LON_MAX, Z)
tx0, ty0, tx1, ty1 = int(x0 // 256), int(y0 // 256), int(x1 // 256), int(y1 // 256)
mosaic = Image.new("RGB", ((tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256))
with httpx.Client(timeout=20, headers={"User-Agent": "farm-map-check/1.0"}) as c:
    n = 0
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            r = c.get(URL.format(z=Z, y=ty, x=tx))
            r.raise_for_status()
            mosaic.paste(Image.open(io.BytesIO(r.content)).convert("RGB"), ((tx - tx0) * 256, (ty - ty0) * 256))
            n += 1
crop = (round(x0 - tx0 * 256), round(y0 - ty0 * 256), round(x1 - tx0 * 256), round(y1 - ty0 * 256))
img = mosaic.crop(crop)
img.save(f"farm_esri_z{Z}.jpg", quality=90)
mpp = 156543.03392 * math.cos(math.radians((LAT_MIN + LAT_MAX) / 2)) / 2**Z
json.dump({"z": Z, "tiles": n, "size": img.size, "m_per_px": round(mpp, 3),
           "bbox": [LON_MIN, LAT_MIN, LON_MAX, LAT_MAX], "attribution": "Esri, Maxar, Earthstar Geographics"},
          open(f"farm_esri_z{Z}.json", "w"), indent=1)
print(n, "tiles", img.size, f"{mpp:.2f} m/px")

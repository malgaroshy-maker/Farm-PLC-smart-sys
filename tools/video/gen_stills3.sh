#!/usr/bin/env bash
# Starting images for the 2:00 video (docs/DEMO_VIDEO_PLAN.md), made with the Codex CLI.
#   bash tools/video/gen_stills3.sh        # outputs video/assets/v3/<name>.png
# The reference photos are copied without their metadata first (no GPS position, date or device leaves the PC).
# Photos with people (ref_09, ref_12, ref_13) are never used.
cd "$(dirname "$0")/../.." || exit 1
OUT="$PWD/video/assets/v3"; REF="$PWD/video/refs"; CLEAN="$OUT/refs"
mkdir -p "$CLEAN"
python - "$REF" "$CLEAN" <<'PY'
import sys
from pathlib import Path
from PIL import Image, ImageOps
src, dst = Path(sys.argv[1]), Path(sys.argv[2])
for n in ("00", "01", "02", "04", "03", "05", "06", "07", "08", "11", "16"):
    im = ImageOps.exif_transpose(Image.open(src / f"ref_{n}.jpg")).convert("RGB")
    im.thumbnail((1600, 1600))
    clean = Image.new("RGB", im.size)
    clean.paste(im)
    clean.save(dst / f"ref_{n}.jpg", quality=90)
PY

STYLE='Cinematic photograph, 16:9 landscape, warm film look, natural and believable, real dusty red-brown soil, dry rolling hills and Libyan sky as in the reference photos, no text, no captions, no logos, no watermark, no faces visible. Match the vegetation, soil colour and landscape of the attached reference photos exactly (a Libyan farm, not a lush European orchard). Subject:'

declare -A JOBS=(
  [v1_valve]="$STYLE close view of a farmer's two weathered hands straining to turn a stiff rusty irrigation valve wheel on a pipe, dry cracked red soil around it, pomegranate rows soft behind, harsh morning sun."
  [v2_night]="$STYLE night, a lone farm worker seen only from behind, walking between orchard rows with a torch whose beam is the only light, deep blue sky with stars, tired lonely mood."
  [v3_leak]="$STYLE a split black drip irrigation pipe in the orchard spraying and pooling water into a wasteful muddy puddle, nobody anywhere, late afternoon long shadows."
  [v4_pump]="$STYLE outdoors next to a BIG fully roofed concrete water reservoir building: a tall closed square grey concrete block, clearly larger than a person, with a flat concrete roof, a small square steel hatch near one corner of the roof, a short vent pipe, a steel ladder on one side, and no open water anywhere. At its base an electric water pump on a small concrete plinth with pipes and a pressure gauge. Beside it a small flat-roofed concrete control room with an outdoor air conditioner unit and a weathered electrical box with unlit lamps: the power has just gone off, everything silent, late afternoon, worrying quiet mood. View from a little distance so the whole reservoir and its flat roof edge are visible. The last attached picture shows our own drawings of these buildings (left: reservoir roof seen from above, middle: reservoir shape with hatch, ladder and outlet pipe, right: control room roof); use them only for shape, and render a real photograph."
  [v5_heat]="$STYLE midday summer heat over the orchard, tired young trees with drooping dusty curled leaves in cracked dry red soil, heat haze, bleached sky."
  [v6_unaware]="$STYLE indoors in a normal modern Libyan family living room in the evening, with a contemporary sofa, plain painted walls and soft electric light (no oil lamp, nothing old-fashioned), the hands of a man in everyday modern clothes holding a dark silent smartphone, and through a modern aluminium window far away the farm hills at dusk, quiet worried mood."
  [v7_water]="$STYLE low view at the foot of a healthy pomegranate tree that stands in its own watering basin: a clear round shallow pool of earth around the trunk, held by a raised ring of red soil, as dug around trees on this farm (see the reference photo with the round pit). Drip irrigation is beginning: water drops fall from a black drip line into the basin, where water is collecting in a shallow pool and darkening the soil. Neighbouring trees behind also each have their own round earth basin. Golden sunrise backlight, hopeful mood."
  [v8_evening]="$STYLE the farm at golden sunset from a gentle rise, an old olive tree in the foreground, neat irrigated rows with darker moist soil, a low farm building on the horizon, calm and prosperous, peaceful mood."
)
declare -A REFS=(
  [v1_valve]="16 00 05" [v2_night]="05 07 00" [v3_leak]="16 00" [v4_pump]="01 04 06 map"
  [v5_heat]="05 11 16" [v6_unaware]="08 05" [v7_water]="04 02 00" [v8_evening]="08 06 05"
)

run_one() {
  local name="$1" prompt="$2" args=() r
  [ -s "$OUT/$name.png" ] && { echo "skip $name"; return; }
  for r in ${REFS[$name]}; do args+=(-i "$CLEAN/ref_$r.jpg"); done
  codex exec -m gpt-6.1-terra --skip-git-repo-check --sandbox workspace-write -C "$OUT" "${args[@]}" \
    -- "Use your image generation tool to create ONE image and save it in the current directory as $name.png. The attached photos are real reference photos of the farm: keep their look. $prompt" \
    > "$OUT/$name.log" 2>&1 < /dev/null
  [ -s "$OUT/$name.png" ] && echo "ok   $name" || echo "FAIL $name"
}
n=0
for name in v1_valve v2_night v3_leak v4_pump v5_heat v6_unaware v7_water v8_evening; do
  run_one "$name" "${JOBS[$name]}" &
  n=$((n + 1)); if (( n % 4 == 0 )); then wait; fi
done
wait; echo done

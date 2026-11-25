#!/usr/bin/env bash
# Round 2 stills: generated from the owner's real farm photos (video/refs/ref_NN.jpg, git-ignored).
#   bash tools/video/gen_stills2.sh      # outputs video/assets/raw/s2_<name>.png
cd "$(dirname "$0")/../.." || exit 1
OUT="$PWD/video/assets/raw"; REF="$PWD/video/refs"
mkdir -p "$OUT"
STYLE='Documentary photograph taken on a modern phone, wide 16:9 landscape, natural unretouched look, slightly imperfect framing, real dusty red-brown soil, dry rolling hills and a pale blue Libyan sky as in the reference photos, no text, no logos, no watermark, no faces visible. Match the vegetation, soil colour and light of the attached reference photos exactly (not a lush European orchard). Subject:'

declare -A JOBS=(
  [valve]="$STYLE early morning, a farmer seen only from behind and from the hands, crouching to turn a rusty metal irrigation valve beside a black drip line in red dusty soil, pomegranate rows behind, low golden light."
  [dry]="$STYLE wide view of long rows of pomegranate trees in dry red soil at dawn, black drip lines along the rows, hills in the distance, soft haze, calm and a little worn."
  [tank]="$STYLE a square plain concrete water reservoir building (flat roof, grey cement blocks, a steel inlet pipe and valve) at the edge of a pomegranate orchard, red soil path, late afternoon light."
  [rows]="$STYLE low angle along a black drip irrigation line running between young pomegranate trees, small water droplets on the emitters, red soil, shallow depth of field."
  [fruit]="$STYLE macro close-up of a ripe pink-red pomegranate on the branch with water drops on its skin and leaves, soft morning light."
  [soil]="$STYLE a soil moisture sensor probe pushed into dark moist red soil beside a young pomegranate tree trunk, a small white wireless box on a short stake, black drip line, orchard rows blurred behind."
  [solar]="$STYLE a small group of solar panels on a steel frame at the edge of a pomegranate orchard beside a concrete pump house and pipework, red soil, clear sky."
  [camera]="$STYLE a weatherproof security camera on a pole above a pomegranate orchard at golden hour, red soil path and hills behind."
  [close]="$STYLE the same orchard at golden hour, fine drip irrigation working along the rows, wet dark soil lines in the red earth, peaceful and prosperous mood, hills behind."
  [night]="$STYLE the orchard at blue dusk, a farmer's silhouette far away walking home along the dirt path, a faint glow of a phone in the hand, rows of trees, hills."
)
declare -A REFS=(
  [valve]="16 00 05" [dry]="05 06 07" [tank]="04 06" [rows]="00 16 07" [fruit]="02 03 01"
  [soil]="16 11" [solar]="06 08" [camera]="05 08" [close]="06 08 00" [night]="05 07"
)

run_one() {
  local name="$1" prompt="$2" args=() r
  [ -s "$OUT/s2_$name.png" ] && { echo "skip $name"; return; }
  for r in ${REFS[$name]}; do args+=(-i "$REF/ref_$r.jpg"); done
  codex exec -m gpt-6.1-terra --skip-git-repo-check --sandbox workspace-write -C "$OUT" "${args[@]}" \
    -- "Use your image generation tool to create ONE image and save it in the current directory as s2_$name.png. The attached photos are real reference photos of the farm: keep their look. $prompt" \
    > "$OUT/s2_$name.log" 2>&1
  [ -s "$OUT/s2_$name.png" ] && echo "ok   $name" || echo "FAIL $name"
}
n=0
for name in "${!JOBS[@]}"; do
  run_one "$name" "${JOBS[$name]}" &
  n=$((n + 1)); if (( n % 5 == 0 )); then wait; fi
done
wait; echo done

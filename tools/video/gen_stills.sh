#!/usr/bin/env bash
# Still scenes for the demo video, made with Codex (the owner's ChatGPT subscription).
#   bash tools/video/gen_stills.sh      # outputs video/assets/raw/<name>.png, 6 at a time
cd "$(dirname "$0")/../.." || exit 1
OUT="$PWD/video/assets/raw"
mkdir -p "$OUT"

STYLE='Cinematic photorealistic photograph, wide 16:9 landscape composition, natural warm light, shallow depth of field, rich but natural colours, no text, no logos, no watermark, no people looking at the camera. Subject:'

declare -A JOBS=(
  [still_dawn]="$STYLE a Mediterranean fruit farm at dawn in North Africa: long rows of young pomegranate and olive trees, black drip irrigation lines glinting with dew, a square concrete water reservoir building in the background, soft golden sunrise over low hills, gentle mist."
  [still_manual]="$STYLE a farmer in a worn cap crouching in an orchard and turning a rusty manual irrigation valve by hand at early morning, water pipes and hoses across the dusty rows behind him, tired and patient mood."
  [still_soil]="$STYLE a close-up of a soil moisture sensor probe pushed into dark soil beside an olive tree trunk, a small white wireless antenna box on a stake, out-of-focus orchard rows behind, morning light."
  [still_solar]="$STYLE a row of solar panels in a pomegranate orchard next to an old well with a water pump and neat pipework, clear blue sky, late afternoon sun."
  [still_camera]="$STYLE a weatherproof security camera mounted on a pole overlooking an olive and pomegranate orchard at golden hour dusk, soft glow on the trees."
  [still_close]="$STYLE the same Mediterranean orchard at golden hour with fine water jets irrigating the rows, rainbow mist in the low sun, peaceful and prosperous mood."
)

run_one() {
  local name="$1" prompt="$2"
  [ -s "$OUT/$name.png" ] && { echo "skip $name"; return; }
  codex exec -m gpt-6.1-terra --skip-git-repo-check --sandbox workspace-write -C "$OUT" \
    "Use your image generation tool to create ONE image and save it in the current directory as $name.png. $prompt" \
    > "$OUT/$name.log" 2>&1
  [ -s "$OUT/$name.png" ] && echo "ok   $name" || echo "FAIL $name"
}

n=0
for name in "${!JOBS[@]}"; do
  run_one "$name" "${JOBS[$name]}" &
  n=$((n + 1))
  if (( n % 6 == 0 )); then wait; fi
done
wait
echo "done"

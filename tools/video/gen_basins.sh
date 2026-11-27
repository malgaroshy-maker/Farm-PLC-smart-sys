#!/usr/bin/env bash
# Owner's corrections (2026-11-27): every tree stands in its own small earth watering basin, and water
# drips from a blue dripper on the side of the pipe, not from the pipe's open end.
# Edits the approved images in place; the earlier versions are kept in video/assets/v3/old/.
#   bash tools/video/gen_basins.sh
cd "$(dirname "$0")/../../video/assets/v3" || exit 1
mkdir -p old

BASIN='every fruit tree stands in its own SMALL watering basin: a shallow round bowl of earth dug around the trunk, about one metre across, with a low ring of red soil only a few centimetres high (small and modest, as on a real small farm, never a wide or tall wall)'
KEEP='Edit the attached photograph. Keep the same composition, camera angle, light, colours, objects and photographic realism. Add no people, no text, no logos. The only change:'

declare -A JOBS=(
  [v1_valve]="$KEEP $BASIN. Add them to the trees that are visible behind; the hands, valve and pipe stay exactly as they are."
  [v3_leak]="$KEEP $BASIN. Add them around the visible trees (they are dry); the split pipe, spray and puddle stay exactly as they are, so the water is visibly wasted outside the basins."
  [v5_heat]="$KEEP $BASIN. Add them around the visible young trees; the basins are dry and cracked in the heat."
  [v8_evening]="$KEEP $BASIN. Add them around the trees in the rows, with dark moist soil inside the basins."
)
V7="Edit the first attached photograph (it shows a pomegranate tree in a basin). Keep the same tree, fruit, sunset light and realism. Changes: (1) make the earth basin clearly SMALLER and shallower, about one metre across with a low ring only a few centimetres high, and make the other trees' basins equally small; (2) the black drip pipe runs straight PAST the tree and continues out of the picture, with no open end visible; (3) a small BLUE dripper nozzle is fitted on the side of the pipe, and clear water drops fall one after another from that blue dripper into the basin, like the dripper under the pipe in the second attached photograph. Only a little water has collected. No people, no text."

run() {
  local name="$1" prompt="$2"; shift 2
  local args=() f
  for f in "$@"; do args+=(-i "$f"); done
  codex exec -m gpt-6.1-terra --skip-git-repo-check --sandbox workspace-write -C "$PWD" "${args[@]}" \
    -- "Use your image generation tool to create ONE edited image and save it in the current directory as $name.png (16:9 landscape). $prompt" \
    > "$name.log" 2>&1 < /dev/null
  [ -s "$name.png" ] && echo "ok   $name" || echo "FAIL $name"
}

for name in v1_valve v3_leak v5_heat v8_evening; do
  mv "$name.png" "old/${name}_nobasin.png" || exit 1
done
mv v7_water.png old/v7_water_bigbasin.png || exit 1
for name in v1_valve v3_leak v5_heat v8_evening; do
  run "$name" "${JOBS[$name]}" "old/${name}_nobasin.png" refs/ref_04.jpg &
done
run v7_water "$V7" old/v7_water_bigbasin.png old/v7_water_nobasin.png &
wait; echo done

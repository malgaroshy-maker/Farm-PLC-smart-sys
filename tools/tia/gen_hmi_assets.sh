#!/usr/bin/env bash
# Generates the HMI icons and illustrations with Codex (the owner's ChatGPT subscription).
#   bash tools/tia/gen_hmi_assets.sh            # all assets, 6 at a time
# Outputs: hmi/assets/raw/<name>.png (about 1254 px, transparent background)
cd "$(dirname "$0")/../.." || exit 1
OUT="$PWD/hmi/assets/raw"
mkdir -p "$OUT"

ICON='Minimal professional line icon for an industrial touch-panel HMI. Thin uniform outline stroke (about 3% of the canvas width) with rounded line caps and rounded joins, single colour teal #70DCCB only, NO fill, NO gradient, NO shadow, NO text, NO background. Fully transparent background, the icon centred with generous padding on a square canvas. Subject:'
ILLU='Clean flat vector-style illustration for a dark industrial touch-panel HMI. Limited palette: dark slate #172832, outline slate #31454F, teal #70DCCB accents, soft light grey #A6BDC4. Subtle and professional, no text, no glow, no drop shadow. Fully transparent background, centred with padding. Subject:'

declare -A JOBS=(
  [icon_irrigation]="$ICON an irrigation water drop above two gentle wave lines."
  [icon_tank]="$ICON a water storage tank, rounded rectangle with a wave line inside near the middle and two short legs."
  [icon_pump]="$ICON a centrifugal water pump: circular housing with an impeller circle, an outlet pipe on top right and a base."
  [icon_gauge]="$ICON a pressure gauge: semicircle dial with a needle and four small tick marks."
  [icon_bolt]="$ICON a lightning bolt for electrical power."
  [icon_overview]="$ICON four rounded squares in a 2 by 2 grid (overview)."
  [icon_zones]="$ICON a farm field seen in perspective: three stacked diamond planes (field layers)."
  [icon_bell]="$ICON an alarm bell with a small clapper."
  [icon_calendar]="$ICON a calendar with two binding rings on top and a small grid of dots."
  [icon_settings]="$ICON three horizontal sliders with round knobs (settings)."
  [icon_warning]="$ICON a warning triangle with an exclamation mark."
  [icon_hand]="$ICON an open hand for manual control mode."
  [icon_chevron]="$ICON a single thin chevron arrow pointing left."
  [logo_mark]="$ICON a rounded-square badge containing a stylised irrigation drop and a single field row line; slightly bolder stroke, still outline only."
  [illu_tank]="$ILLU a front view of a cylindrical water storage tank with a ladder and a level window, half full of teal water."
  [illu_pump]="$ILLU a side view of a booster water pump with motor, pipe flanges and base plate."
  [tex_card]="Seamless subtle dark texture for a UI card background: very fine diagonal micro-grain in dark slate #172832 with barely visible lighter specks, extremely low contrast, no pattern lines, no text. Opaque square tile."
  [tex_header]="A wide dark header banner background for an industrial HMI: dark slate #172832 with a very soft teal #70DCCB horizon glow fading out at the bottom edge and faint contour lines like farm terraces, extremely low contrast, no text. Opaque, wide 16:3 aspect."
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

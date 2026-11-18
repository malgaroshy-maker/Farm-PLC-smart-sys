#!/usr/bin/env bash
# usage: gen.sh <out.png> <prompt>  — Codex generates; we copy the file it reports.
out="$1"; prompt="$2"
log="log_${out}.txt"
timeout 900 codex exec ${REF:+-i "$REF"} -m gpt-6.1-terra --skip-git-repo-check --sandbox read-only -C . \
  "Use your image generation tool to create ONE image. Image: ${prompt} Do not try to save or copy it anywhere. When done, print exactly one line: GENERATED=<absolute path of the generated image file>." > "$log" 2>&1
path=$(grep -o 'GENERATED=[^ `]*\.png' "$log" | tail -1 | sed 's/GENERATED=//')
[ -z "$path" ] && path=$(grep -o '[A-Za-z]:\[^ `]*generated_images[^ `]*\.png' "$log" | tail -1)
if [ -z "$path" ]; then echo "FAIL $out (no image path in log)"; exit 1; fi
# parallel runs can report another run's image: refuse exact duplicates of existing assets
for other in *.png; do
  [ "$other" = "$out" ] && continue
  if cmp -s "$path" "$other"; then echo "FAIL $out (same image as $other - rerun alone)"; exit 1; fi
done
cp "$path" "$out" && echo "OK $out" || echo "FAIL $out"

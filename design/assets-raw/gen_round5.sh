#!/usr/bin/env bash
# Milestone F round 5: block 8 art (owner 2026-11-23). Run inside design/assets-raw.
BG="on a perfectly flat solid pure magenta (#FF00FF) background with nothing else, no ground, no text."
export REF=tree_pomegranate_green.png
./gen.sh tree_pomhedge_green.png "A short straight segment of a dense HEDGE ROW of young mother pomegranate plants (stock plants grown close together for cuttings), viewed from DIRECTLY OVERHEAD (90-degree nadir drone view), photorealistic, same leaf style and lighting as the attached reference. The hedge runs HORIZONTALLY across the frame, about 4 times longer than wide, continuous dense small dark-green leaves with a few thin shoots sticking out, soft short shadow toward the lower right, $BG" &
./gen.sh tree_pomhedge_fruit.png "A short straight segment of a dense HEDGE ROW of young mother pomegranate plants in autumn, viewed from DIRECTLY OVERHEAD (90-degree nadir drone view), photorealistic, same leaf style and lighting as the attached reference. The hedge runs HORIZONTALLY across the frame, about 4 times longer than wide, continuous dense small dark-green leaves with a few small red pomegranates and orange-red flowers visible, soft short shadow toward the lower right, $BG" &
unset REF
./gen.sh detail_ummahat.png "Photorealistic eye-level photo in a Libyan farm: dense hedge rows of young mother pomegranate plants (stock plants for cuttings) planted very close together in long tight rows, drip irrigation hose along the base, sandy orange soil, bright midday light, desert hills far behind, shallow depth of field. Landscape 3:2, no people, no text." &
./gen.sh detail_olive_old.png "Photorealistic eye-level photo in a Libyan farm: three rows of big old olive trees with thick gnarled trunks and wide silvery-green canopies, drip hose at the base, sandy orange soil, bright midday light, desert hills far behind. Landscape 3:2, no people, no text." &
wait
echo DONE

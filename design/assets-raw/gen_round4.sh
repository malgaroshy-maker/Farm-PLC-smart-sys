#!/usr/bin/env bash
# Milestone F round 4 map assets (owner asked 2026-11-23). Run inside design/assets-raw.
TOP="Viewed from DIRECTLY OVERHEAD (90-degree nadir drone view): only the roof is visible, no walls, no horizon, no perspective. Photorealistic, warm late-morning North African light, soft short shadow toward the lower right."
BG="on a perfectly flat solid pure magenta (#FF00FF) background with nothing else, no ground, no text, no labels."
TREE="Viewed from DIRECTLY OVERHEAD (90-degree nadir drone view): only the top of the canopy, no trunk side, no horizon. Photorealistic, same style and lighting as the attached reference tree. ONE single tree only, centered, filling about 80% of a square frame, soft short shadow toward the lower right,"

export REF=spr_control_room.png
./gen.sh spr_bld_barn.png "A long, narrow single-storey chicken barn (poultry house) on a Libyan farm. $TOP Long axis HORIZONTAL, about 4 times longer than wide, filling the frame width. Weathered light-grey corrugated metal roof with a ridge line along its length, small roof vents in a row, slight rust streaks. $BG" &
./gen.sh spr_bld_brooder.png "A wide single-storey poultry brooder hall on a Libyan farm. $TOP Long axis HORIZONTAL, about 1.5 times longer than wide. Blue-grey painted corrugated metal roof (like faded blue sheeting), two ridge vents, a few patched panels. $BG" &
./gen.sh spr_bld_rooms.png "A small single-storey block of workers' rooms on a Libyan farm. $TOP Long axis HORIZONTAL, about 1.8 times longer than wide. Flat whitewashed concrete roof with a low parapet, a water tank drum and a satellite dish on the roof, a few small vents. $BG" &
./gen.sh spr_bld_resthouse.png "A small farm rest house (istiraha) on a Libyan farm. $TOP Roughly square footprint, slightly wider than tall. Flat light-beige concrete roof with a low parapet, a shaded pergola terrace on one side, a small courtyard with tiles. $BG" &
./gen.sh spr_well_cap.png "An underground water well access cap set flush in the ground: a square concrete slab about 2 m wide with a round steel manhole lid and a small pipe stub, seen from directly overhead, photorealistic, soft shadow. $BG" &
./gen.sh tex_sand.png "Seamless tileable texture, viewed from directly overhead: dry North African farm ground, orange-tan sandy soil with fine pebbles, faint wind ripples, a few tiny dry weed tufts, low contrast so it can tile without visible seams, no objects, no shadows of objects, even lighting, colour close to #C8A273. Square image, edges must tile seamlessly." &
wait
export REF=tree_pomegranate_green.png
./gen.sh tree_almond_green.png "A mature almond tree in summer leaf: light grey-green narrow leaves, open airy rounded canopy. $TREE $BG" &
./gen.sh tree_citrus_green.png "A mature citrus tree (lemon/orange) without fruit: very dense, glossy dark-green round canopy. $TREE $BG" &
./gen.sh tree_lemon_fruit.png "A mature lemon tree in season: dense glossy dark-green round canopy dotted with many small bright yellow lemons visible from above. $TREE $BG" &
./gen.sh tree_orange_fruit.png "A mature orange tree in season: dense glossy dark-green round canopy dotted with many bright orange oranges visible from above. $TREE $BG" &
./gen.sh tree_almond_fruit.png "A mature almond tree at harvest: grey-green narrow leaves, open rounded canopy with many small pale green-beige almond hulls visible. $TREE $BG" &
wait
echo DONE

# Demo video plan (Milestone G)

**Decided 2026-11-25.** A 4-minute, story-led video in Arabic: music and Arabic captions only, no voice. It shows the finished app, the PLC and the control-room panel, then the road ahead.

## How it is made
- **Footage:** real captures of the running app (1920 x 1080, Playwright), the panel in the Unified runtime simulation, and the simulator at time-lapse speed. Nothing is faked: every number on screen comes from the running system.
- **Scenes without a screen** (intro, the "before" picture, the closing): still images made with Codex, animated with slow pan and zoom. No video-generation credits.
- **Captions:** Arabic, burned into the picture, written to be read in about 3 seconds each.
- **Music:** one calm instrumental track under everything (source to be chosen by the owner).
- **Output:** `video/farm-demo-ar.mp4`, 1920 x 1080, 30 fps. Scenes are assembled by `tools/video/` (HTML scenes recorded with Playwright, mixed with ffmpeg).

## Storyboard (about 4:00)

| Time | Scene | Picture | Caption (Arabic) |
|---|---|---|---|
| 0:00 | Title | Codex still: the farm at dawn, slow zoom; the title | مزرعة الجروشي: ري ذكي بالكامل |
| 0:12 | The problem | Codex still: a farmer opening valves by hand across the rows | كل صمام يُفتح باليد، في كل موسم |
| 0:25 | One screen | App: dashboard and farm map, pan over the 12 zones | كل المزرعة على شاشة واحدة |
| 0:50 | A day of irrigation | App: the schedule, then the time-lapse: zones start in turn, flow and tank level move | الجدول يعمل وحده: منطقة بعد منطقة |
| 1:25 | The farm explains itself | App: zone drawer with state, runtime, flow, pressure | كل منطقة: حالتها وتدفقها وضغطها لحظة بلحظة |
| 1:45 | When something fails | Simulator: booster trip, the alarm card in Arabic, the zone stops safely, the phone notification | عطل في المضخة؟ إنذار فوري وإيقاف آمن |
| 2:15 | The advisor | App: AI advisor with weather and soil reasoning in Arabic | مستشار ذكي: ماذا نسقي ومتى ولماذا |
| 2:45 | The controller | PLC in PLCSIM and the panel: Overview, Zone Start, Pumps and water | وحدة تحكم صناعية، وشاشة لمس في غرفة التحكم |
| 3:15 | It never stops | Panel Schedule screen; app link goes amber, the PLC runs the stored schedule | حتى لو انقطع الإنترنت يستمر الري |
| 3:30 | In your pocket | Phone view and report: water used, cycles | في جيبك: التقارير والإنذارات |
| 3:45 | What is next | Codex stills: soil sensors, solar pumping, cameras (the hardware plan) | قريباً: حساسات التربة، الضخ بالطاقة الشمسية |
| 3:55 | Close | Title card | مزرعة الجروشي |

## Before shooting
- The app and the PLC run together (`run.bat demo plcsim`); the panel runs in the Unified simulation (Online > Simulation > Start).
- Demo data is real: the 12 zones, the schedule and the PLC's states. No invented customers or numbers.
- The photos and drawings use the farm's real layout (`docs/algaroshy_farm_layout_fixed.svg`).

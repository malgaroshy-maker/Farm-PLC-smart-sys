# Demo video plan

**Decided with the owner, 2026-11-27.** A new video built from scratch, about 2:00, for the family who owns the farm.
Cinematic farm look; app screens shown in laptop and phone frames with smooth zooms. Captions in simple standard
Arabic, no voice. The current calm music track; generated clip sound is switched off.

## Tools
- **Moving clips:** Higgsfield, model MAGI-2 (1080p, 2.5 credits per second). Seven clips of 4 s = 70 credits of the
  156.9 available. People appear only as hands or from behind. The owner approves before credits are spent.
- **Still images and first frames:** Codex CLI, based on the farm's reference photos in `video/refs/`.
- **Before any photo leaves the PC:** its metadata (GPS position, date, device) is removed, and photos with people are
  not uploaded.
- **Screens:** real captures of the running app and of the Arabic WinCC Unified panel. No invented numbers.

## Storyboard

| Time | Scene | Picture | Caption (Arabic) |
|---|---|---|---|
| 0:00 | Every valve by hand | MAGI: hands straining at a valve, dry cracked soil | كل صمام يُفتح ويُغلق باليد |
| 0:05 | One person | MAGI: a lone worker from behind, walking the rows at night with a torch | وإن مرض العامل أو نسي الموعد؟ · الترتيب والتوقيت لا يعرفهما إلا هو |
| 0:10 | Unnoticed leak | MAGI: water pooling from a split drip line, nobody there | تسرّب لا يلاحظه أحد: ماء ووقود يضيعان |
| 0:15 | Pump and power | MAGI: dark pump corner, the pump stops | انقطعت الكهرباء؟ احترقت المضخة؟ · من يعيد التشغيل؟ |
| 0:20 | The trees pay | MAGI from a farm photo: tired trees in midday heat | ماء أقل أو أكثر من الحاجة، وسقيٌ قبل المطر · ولا نكتشف إلا متأخرين |
| 0:26 | We cannot see | Codex still: the owner's hands and a silent phone, far from the farm | ونحن أصحابها لا نعرف شيئاً إلا إذا ذهبنا · ولا سجلّ للماء |
| 0:31 | The turn | MAGI: water arrives at the foot of a pomegranate tree | ماذا لو سقت المزرعة نفسها… وأخبرتنا بكل شيء؟ |
| 0:36 | Title | Real pomegranate photo | مزرعة الجروشي: ري ذكي |
| 0:41 | Daily irrigation | App: live map, schedule running by itself, flow, pressure, tank | كل المزرعة على شاشة واحدة · الجدول يعمل وحده · تدفق وضغط لحظة بلحظة |
| 1:01 | Safety | App: pump fault, Arabic alarm, safe stop; STOP ALL; "no connection" warning; controller keeps its schedule | عطل؟ إنذار فوري وإيقاف آمن · زر واحد يوقف كل شيء · وبلا إنترنت يستمر الري |
| 1:20 | Smart help | App: morning briefing, weather advice, alarm explained | موجز كل صباح · نصيحة من الطقس والتربة · وشرح كل إنذار |
| 1:32 | In our hands | Arabic touch panel, phone alerts, reports, one account per family member | شاشة في غرفة التحكم · وإنذارات في الجيب · سجلّ لكل قطرة · ولكلٍّ حسابه |
| 1:46 | Where we are | Calm card over the farm; screens carry a small "محاكاة" label throughout | جُرّب النظام بالمحاكاة مع وحدة تحكم افتراضية. الخطوة القادمة: تجربة ميدانية على منطقة واحدة |
| 1:53 | Peace of mind | MAGI from the sunset photo: evening at the farm; phone shows all is well | مزرعتنا بخير… ونحن مطمئنون · مزرعة الجروشي |

Output: `video/farm-demo-ar.mp4` (1920 x 1080, 30 fps) and a smaller share copy. Assembled by `tools/video/`.

## Notes
- A "silent phone" and a caption never claim a feature the app does not have. Burned-out pumps and wasted fuel are
  shown as the family's problems, not as faults the system can always prevent.
- The "pump fault" and "no connection" scenes are recorded from the running app in simulation.

## Final version (approved by the owner, 2026-11-27)

2:54, after the owner's two rounds of changes. It differs from the first storyboard above:
- every orchard tree stands in a small earth basin, and water drips from a blue dripper;
- the pump scene shows the roofed reservoir and the control room, as on the map;
- zones are started and stopped on screen, on desktop and phone;
- the assistant answers four questions with real answers from the configured AI;
- app screens are closer and brighter, and captions stay longer.

The scene list is in `tools/video/build_video3.py`. To rebuild: `gen_stills3.sh` and `gen_basins.sh` (Codex images),
MAGI-2 clips on Higgsfield, `capture.py hmi`, `capture3.py` and `capture4.py` (throwaway app on PLCSIM), then
`build_video3.py` and `mix_music.py`.

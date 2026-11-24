# HMI build guide: MTP1000 Unified Comfort (G5)

You build the screens in TIA Portal; this guide is the spec. The panel device `FarmHMI` (MTP1000 Unified Comfort, 1280 x 800) is already in the project `AlgaroshyFarm`. The PLC side is done and tested in PLCSIM (the HMI buttons, section 5). Design decisions are in [PLC_PROGRAM.md](PLC_PROGRAM.md) section 7: **match the app** (dark theme, Arabic RTL default, EN switch) and **overview layout A** (zone grid).

WinCC Unified Openness is not installed here, so none of this can be generated from code.

## 1. Connect the panel to the PLC
1. **Devices & networks**: draw a PROFINET line from the panel's interface to the PLC's X1 (192.168.0.1). Give the panel 192.168.0.2 / 255.255.255.0.
2. **HMI connections**: create a connection from `FarmHMI` to `FarmPLC` (S7 communication). All farm DBs use optimized access, which Unified reads symbolically.
3. **Runtime settings > Languages**: add Arabic (Libya) and English (UK). Default: Arabic. `DB_HMI.Language` (0 Arabic, 1 English) is there if you want the PLC to hold the language.

## 2. Look
| Item | Value |
|---|---|
| Screen background | `#0F172A` |
| Card / tile | `#1E293B`, border `#334155`, radius 8 |
| Text | primary `#F8FAFC`, secondary `#94A3B8` |
| Font | Noto Sans Arabic or the closest Unified font; 14 px body, 18 px tile titles, 28 px key values |
| Touch targets | 48 px high minimum |
| Direction | right-to-left layout for Arabic (mirrored when the language switches) |

Zone state colours (same as the app):

| State | Name | Arabic | Colour |
|---|---|---|---|
| 0 | off | متوقف | `#6B7280` |
| 1 | starting pump | تشغيل المضخة | `#06B6D4` |
| 2 | opening valve | فتح الصمام | `#06B6D4` |
| 3 | checking flow | التحقق من التدفق | `#06B6D4` |
| 4 | running | يعمل | `#22C55E` |
| 5 | stopping | إغلاق | `#EAB308` |
| 6 | completed | مكتمل | `#6B7280` |
| 7 | faulted | عطل | `#EF4444` |
| 8 | interrupted | متقطع | `#F97316` |

`PanelMode` 1 (switch ON) or 2 (switch OFF) adds a hand badge on the tile; 0 is auto (no badge).

## 3. Text lists
- `ZoneState`: the table above, Arabic and English.
- `PanelMode` (zones): 0 auto / تلقائي, 1 on / تشغيل يدوي, 2 off / إيقاف يدوي.
- `PumpMode`: 0 auto / تلقائي, 1 hand / يدوي, 2 off / إيقاف.
- `SystemMode`: 0 off / متوقف, 1 auto / تلقائي, 2 manual / يدوي, 3 maintenance / صيانة.
- `RunSource`: 0 app / التطبيق, 1 panel / اللوحة, 2 fallback / الجدول الاحتياطي, 3 resume / استئناف, 4 hmi / الشاشة.
- Zone names (PLC index to name):

| Index | Id | Arabic name |
|---|---|---|
| 1 | `zone_rumman_1` | رمان 1 |
| 2 | `zone_rumman_2` | رمان 2 |
| 3 | `zone_rumman_3` | رمان 3 |
| 4 | `zone_rumman_4` | رمان 4 |
| 5 | `zone_rumman_5` | رمان 5 |
| 6 | `zone_rumman_6` | رمان 6 |
| 7 | `zone_rumman_ummahat` | رمان امهات |
| 8 | `zone_rumman_jadeed` | رمان جديد |
| 9 | `zone_zaytoun` | زيتون |
| 10 | `zone_zaytoun_2` | زيتون 2 |
| 11 | `zone_enab` | عنب |
| 12 | `zone_fruit_mix` | خوخ + مشمش + عوينة |

## 4. Tags
Add each from the PLC tags with **Add to HMI tags**.

| Tag | Type | Use |
|---|---|---|
| `DB_Farm.Mode` | Int | system mode text |
| `DB_Farm.EStop`, `PowerOk`, `LinkOk`, `FallbackActive` | Bool | top bar, status column |
| `DB_Farm.TankLevelPct` | Real | tank bar |
| `DB_Farm.MainPressureBar`, `MainFlowM3h` | Real | status column |
| `DB_Farm.WellLevelM`, `FilterDpBar`, `Refilling` | Real / Bool | pumps screen |
| `DB_Zones.Zone[n].State` | Int | tile colour and text (n = 1..12) |
| `DB_Zones.Zone[n].RuntimeSec`, `TargetSec` | DInt | tile timer (remaining = target - runtime; target 0 = no limit) |
| `DB_Zones.Zone[n].FlowM3h`, `PressureBar` | Real | tile, zone screen |
| `DB_Zones.Zone[n].PanelMode` | Int | hand badge |
| `DB_Zones.Zone[n].RunSource` | Int | source text |
| `DB_Zones.Zone[n].FaultCode` | Int | fault line (alarm number) |
| `DB_Pumps.Booster`, `DB_Pumps.Well` | UDT_Pump | RunFb, Fault, FailedStart, Locked, PanelMode, PowerKw, CurrentA, RuntimeHours |
| `DB_Alarms.Word0`, `Word1`, `Word2` | Word | discrete alarms (section 7) |
| `DB_Alarms.AnyActive` | Bool | alarm indicator |

Tip: build the zone tile as one faceplate with a parameter `n` and place it 12 times, so a layout change is one edit.

## 5. Buttons: how the screen commands the PLC
The HMI never writes the command channel itself. It sets values in `DB_HMI`; the PLC turns them into a command with the **same checks as the app** (interlocks, E-stop, panel switch) and answers.

| Tag | Set by the HMI | Meaning |
|---|---|---|
| `DB_HMI.SelectedZone` | pressing a zone tile (write its n) | the zone Start and Stop act on |
| `DB_HMI.StartDurationMin` | the duration entry | minutes for a start (the PLC caps it at the zone's maximum) |
| `DB_HMI.BtnStart` | Start button, **SetBit** | start the selected zone |
| `DB_HMI.BtnStop` | Stop button | stop the selected zone |
| `DB_HMI.BtnStopAll` | Stop all button | stop every zone the app owns |
| `DB_HMI.BtnReset` | Reset alarms button | reset the PLC's latched alarms |
| `DB_HMI.ResultOk`, `ResultText`, `ResultSeq` | read only | the PLC's answer. `ResultSeq` changes with each answer. Show `ResultText` for 4 seconds (empty when accepted, else a short reason such as `pump_unavailable`) |

The PLC clears each `Btn*` bit itself, so use **SetBit** on press and nothing on release.

Tested in PLCSIM: Start made zone 1 start with run source 4 (hmi); Stop all stopped it.

Roles (Unified user management): Start, Stop and Stop all for the `Operator` group; **Reset alarms and Settings for `Admin` only**.

## 6. Screens
Bottom bar, always visible (right to left in Arabic): Overview, Zones, Pumps and water, Alarms, Schedule, Settings. Top bar: farm name, alarm count (red when `DB_Alarms.AnyActive`), PLC link state (`DB_Farm.LinkOk`; amber "fallback" while `FallbackActive`), clock, AR | EN switch.

1. **Overview (layout A).** A 4 x 3 grid of the 12 zone tiles (order of section 3) and a status column beside it: tank level, booster pump, well pump, pressure and flow, mains. A tile shows name, state text, remaining time while running, flow and the hand badge; border and fill use the state colour. Pressing a tile sets `SelectedZone` and opens the zone screen.
2. **Zone.** The tile enlarged: state, source, timer, flow, pressure, panel mode, fault text; a duration entry (number pad, 1 to the zone's maximum); Start and Stop buttons; the answer line (`ResultText`).
3. **Pumps and water.** Both pumps (run, fault, failed start, locked, panel mode, kW, A, hours), well level, filter pressure drop, tank level, refilling.
4. **Alarms.** The Unified alarm control with the alarms of section 7, in Arabic and English, and a Reset alarms button (admin).
5. **Schedule.** Read-only: the fallback runs (`DB_Fallback.Run[1..48]`: zone, start minute of day, duration, weekday, `Done`) and `DB_Fallback.LoadedAt`.
6. **Settings.** Admin only: system mode (`DB_Farm.Mode`) and language. Zone limits stay in `DB_Config` until commissioning.

## 7. Alarms (Unified discrete alarms)
One discrete alarm per row, bound to the bit of `DB_Alarms.Word0/1/2` (bit n-1 for alarm n). Class by severity: S3 = Alarm (acknowledge), S2 and S1 = Warning, S0 = Info.

| Code | Tag bit | Arabic text | English text | Severity |
|---|---|---|---|---|
| ALM-001 | Word0 bit 0 | تحذير انخفاض مستوى الخزان | Tank Low Level Warning | S1 |
| ALM-002 | Word0 bit 1 | مستوى الخزان حرج | Tank Critically Low Level | S3 |
| ALM-004 | Word0 bit 3 | عطل / فصل مضخة البئر | Well Pump Fault / Trip | S3 |
| ALM-005 | Word0 bit 4 | عطل / فصل مضخة التعزيز | Booster Pump Fault / Trip | S3 |
| ALM-006 | Word0 bit 5 | فشل بدء تشغيل مضخة التعزيز | Booster Pump Failed to Start | S2 |
| ALM-007 | Word0 bit 6 | فشل بدء تشغيل مضخة البئر | Well Pump Failed to Start | S2 |
| ALM-008 | Word0 bit 7 | تحذير ضغط منخفض في الخط الرئيسي | Mainline Low Pressure Warning | S1 |
| ALM-010 | Word0 bit 9 | تحذير ضغط مرتفع في الخط الرئيسي | Mainline High Pressure Warning | S1 |
| ALM-012 | Word0 bit 11 | لم يتم اكتشاف تدفق | No Flow Detected | S2 |
| ALM-013 | Word0 bit 12 | تدفق غير طبيعي / اشتباه في تسرب | Abnormal High Flow / Leak Suspected | S2 |
| ALM-020 | Word1 bit 3 | فشل إغلاق الصمام | Valve Failed to Close | S3 |
| ALM-021 | Word1 bit 4 | تغيير غير متوقع في حالة الصمام | Unexpected Valve State Change | S2 |
| ALM-027 | Word1 bit 10 | خطر التشغيل الجاف | Dry-Run Risk | S3 |
| ALM-029 | Word1 bit 12 | فقدان الاتصال — PLC إلى الخادم | Communication Lost — PLC to Backend | S2 |
| ALM-033 | Word2 bit 0 | انقطاع الطاقة / فشل طاقة التحكم | Power Loss / Control Power Failure | S2 |
| ALM-039 | Word2 bit 6 | مطلوب صيانة — الفلاتر / الصمامات | Maintenance Due — Filters / Valves | S1 |
| ALM-041 | Word2 bit 8 | تم تفعيل إيقاف الطوارئ | Emergency Stop Activated | S3 |
| ALM-042 | Word2 bit 9 | الوضع اليدوي نشط | Manual Mode Active | S0 |
| ALM-043 | Word2 bit 10 | وضع الصيانة نشط | Maintenance Mode Active | S0 |

The app also derives alarms from live data; the HMI shows only what the PLC itself raises.

## 8. Test in the Unified runtime simulator
1. Compile the panel and start the simulation. The PLC must be running in PLCSIM at 192.168.0.1 (`run.bat demo plcsim` plays the farm around it).
2. Overview shows live zone colours. Press the zone 1 tile, enter 2 minutes, press Start: zone 1 goes through starting and opening to running (green), source "الشاشة". Press Stop. Then Stop all.
3. Switch AR | EN: every text changes and the layout mirrors.
4. Trip the booster from the app's Simulator page: ALM-005 appears on the Alarms screen with its Arabic text. Press Reset alarms as admin once the pump is repaired.
5. Send me screenshots and I'll check them against layout A.

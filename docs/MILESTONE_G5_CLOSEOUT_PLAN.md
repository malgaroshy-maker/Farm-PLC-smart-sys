# Farm-PLC Milestone G5 closeout plan

**Date:** 2026-11-25

**Audit baseline:** `milestone-g` at `cbcd69c` and `master` at `81472c9` have identical tracked contents.

The initial audit ordered the PLC and HMI work as per-zone flow protection, real-time clock compatibility, Arabic localization, alarm flashing, and HMI permissions. The initial PLCSIM run passed 12 of 15 over Modbus. The acceptance record below gives the latest results. Field commissioning and live Siemens OPC UA verification remain open. [PLC program guide](../plc/README.md)

## Acceptance record for 2026-11-26

- **Flow protection, simulated PLC, app and HMI.** All 12 zone IDs read back the approved 2–6 m³/h bench band. Healthy olive flow was 4.00 m³/h. A brief 10.00 m³/h pulse did not trip. Sustained high flow raised ALM‑013 in the app and stopped the valve and booster. The zone restarted after repair. No-flow and failed-to-close regressions passed. A fresh PLCSIM leak raised ALM‑013 in the WebRH alarm table as Major.
- **Clock compatibility.** PLCSIM forced 1×, refused both accelerated scenarios with HTTP 409 before preparation, and passed all 13 eligible scenarios. A separate olive-zone schedule completed at 1× for one minute with 0.071 m³ of simulated flow integrated as volume. Both accelerated scenarios passed in the software simulator and virtual PLC.
- **Localization.** Paused by the owner. The installed TIA V19 project language catalog had no Arabic locale. The approved wording is retained in [the draft](../hmi/translations.ar-en.json).
- **Alarm flashing passed in WebRH.** The owner started `WCCILScsService`, which opened TCP 20008 and resolved the `HMI_RT_1` transfer failure. One approved local simulation transfer completed. Fresh PLC events ALM‑005 and ALM‑013 each alternated between two readable color phases. Single acknowledgement changed each active row to `RaisedAcknowledged` with steady colors. Both cleared PLC bits read back false and both acknowledged rows left the active view. A separate clear-before-acknowledgement check kept ALM‑005 steady in `RaisedCleared`.
- **HMI permissions.** Deferred by the owner. The approved design is read-only Settings for operators with administrator-only mode changes and alarm reset. The native-rights helper builds with the V19 SDK. In the earlier bench check, Openness found zero active named HMI administrators and zero available function rights. The current bench runtime opened without a sign-in and accepted an alarm reset. Applying the bindings and testing the roles are deferred.
- **Database and credentials.** A fresh SQLite database and an upgrade with populated and null counters both passed `alembic check`. The credential regression test verified that newly generated values are written to the isolated `.env` file and absent from launcher output. The historical entry was redacted from the working copy. A read-only check found no match in the workspace's local seed configuration or existing SQLite account hashes. Historical Git copies still contain the entry, and use outside this workspace remains unverified.
- **Protocol coverage.** The PLCSIM instance answered on Modbus TCP 502. A TCP connection to the standard OPC UA port 4840 on the same bench instance timed out. The bench result covers Modbus and the HMI's S7 link. Siemens OPC UA remains unverified against a live controller.

## 1. Per-zone flow limits and mainline leak protection

**Audit finding.** The PLC's default band of 1–30 m³/h let the simulated 10 m³/h leak stay below the trip limit. The app's seeded 5–18 m³/h band for the olive zone also conflicted with the plant's healthy 4 m³/h. The earlier leak scenario inserted fictitious cycles and telemetry to trigger ALM‑046, with water totals marked as measured. [PLC configuration](../plc/src/01_Types.udt) · [PLCSIM plant](../apps/simulator/src/plcsim_plant.py) · [Scenario runner](../apps/api/app/services/scenarios.py)

- Reuse the app's existing zone flow fields for owner-approved limits. Transfer them to the PLC explicitly and read them back against the zone ID and units. Base bench limits on recorded healthy runs from the simulated plant and field limits on farm measurements. Keep single-zone operation for this pass because the PLC has one mainline meter.
- Update the leak scenario to verify a fresh PLC ALM‑013, the faulted zone, safe valve and pump shutdown, and the alarm in the app and HMI. Remove the invented-history prerequisite. Check ALM‑046 separately when a recorded baseline is available. Review any existing synthetic rows before proposing a cleanup.
- **Accept when** healthy flow and a brief spike do not trip the PLC, sustained high flow does, and the operator can recover after clearing the leak. Rerun the no-flow and failed-to-close cases to catch regressions.

## 2. Clock scenarios and real-time PLC compatibility

**Audit finding.** The PLCSIM launcher set the gateway adapter and inherited the API's controller mode from the environment. The API could accelerate its scheduler while the PLC timers continued at 1×. The scenario catalog listed both accelerated cases without a compatibility check. [Launcher](../scripts/start.mjs) · [Farm clock](../apps/api/app/core/clock.py) · [Scenario runner](../apps/api/app/services/scenarios.py)

- Set real-time mode for the API in `demo plcsim`. Reject `scheduled_day` and `scheduled_blocked_start` before scenario preparation starts. Keep both available on the software simulator and virtual PLC. Review how unavailable scenarios and clock controls should appear with the owner before making any UI changes.
- **Accept when** 13 eligible PLCSIM cases pass and the two accelerated cases are explicitly incompatible. Run a short 1× schedule check to verify dispatch and completion on the PLC. Verify that accelerated scheduling still works in the simulator and virtual PLC.

## 3. Arabic and English in WinCC Unified

**Finding.** The generated alarm and text-list workbooks contain English columns only. Many screen labels are authored in Arabic, and the local Openness helper's generic text setter copies the same text into every language slot. [HMI build guide](HMI_BUILD_GUIDE.md) · [Screen builder](../tools/tia/build_hmi.py) · [Text generator](../tools/tia/gen_hmi_alarms_texts.py)

- Verify the Arabic project locale and rendering in the installed V19 runtime. Enable Arabic and English as project and runtime languages. Re-export the bilingual TIA templates, regenerate the alarm and text-list workbooks, and make screen text updates language-specific.
- Review wording, language switch, alignment, and any layout changes with the owner. Verify the table headers, state lists, alarm messages and guidance, and command refusals in both languages.
- **Accept when** both languages render correctly across all six screens in Unified simulation, including after switching languages. [Siemens WinCC Unified V19 manual](https://support.industry.siemens.com/cs/attachments/109828368/WinCC_VisualizingProcessesUnified_enUS_en-US.pdf)

## 4. Raised alarm flashing

**Finding.** Commit `5b47668` disabled flashing after the inverted phase proved too glaring. [Alarm class styling](../tools/tia/style_hmi_alarm_classes.py)

- The owner approved flashing for unacknowledged major and critical alarms in the existing palette. Verify ALM‑013 (major) and ALM‑005 (critical) while the fault is present. Acknowledge each in the alarm table, then clear the simulated fault and reset the PLC latch. Check that the text stays readable through both phases and the row stops flashing after acknowledgement or clear.
- **Accept when** a PLC-triggered alarm in WebRH follows the approved behavior when raised, acknowledged, and cleared, and the text stays readable throughout.

## 5. HMI user permissions

**Finding.** The Settings mode buttons and alarm reset button write PLC request tags. The builder does not configure operation rights for them. [HMI builder](../tools/tia/build_hmi.py) · [HMI role design](HMI_BUILD_GUIDE.md)

- Enforce the documented role split with native Unified operation rights. Operators can use duration, Start, Stop, and Stop all. The owner approved keeping Settings visible and disabling the system mode and alarm reset controls for operators. Admins can use those protected controls.
- Use separate named operator and administrator sessions. Check that an unauthenticated session and the operator cannot reset alarms or change mode. In the operator session, verify the duration and irrigation commands. In the administrator session, verify alarm reset and a mode change, then restore the original mode.
- In the idle PLCSIM bench, record `DB_Cmd.Hmi.Seq`, `DB_HMI.ResultSeq`, and `DB_Farm.Mode` before and after each attempt. The PLC clears request bits and resets `DB_HMI.ReqMode` within a scan, so compare the command sequence and applied mode as well as the visible button state. Use a different mode for the test and restore the original mode afterward.
- **Accept when** an unauthorized session cannot send a protected PLC request, an operator can still use the irrigation controls, and an administrator can use all approved actions. Check both the UI and the PLC request tags. [Siemens WinCC Unified V19 manual](https://support.industry.siemens.com/cs/attachments/109828368/WinCC_VisualizingProcessesUnified_enUS_en-US.pdf)

## Live verification and owner approvals

- Compile in TIA Portal V19. Ask the owner before each PLC or HMI download. Confirm the PLCSIM instance `PLC` at `192.168.0.1` and the `almservice`, `s7oiehsx64`, and PnDiscovery services. Restart `PlcsimBridge` after each PLC download, then run `run.bat demo plcsim`.
- Disconnect TiaCommander before using the Unified helper. Start the HMI with **Online → Simulation → Start** and verify it in [WebRH](https://mahamed97/WebRH). The owner approves TIA's **Allow access** prompts and enters credentials. Keep credentials out of tool output and logs.
- Record acceptance results by controller and protocol. The recorded live path uses Modbus. The offline OPC UA suite uses an in-process server. Record a live Siemens OPC UA result separately.
- Get the owner's approval for each UI choice before applying it. Use recorded farm data for field decisions and label simulated results. If imagery is requested, generate it through Codex using `codex exec -m gpt-6.1-terra`. Commit, push, or merge only on the owner's instruction.

## Separate audit follow-ups

- **Verification baseline.** 441 offline tests passed, along with Python lint and format checks, web lint and build, and the SCL static checker. This audit left the live TIA, PLCSIM, and Unified state untouched.
- **Database schema drift.** The audit flagged four nullability mismatches. The forward migration backfills nulls and aligns the columns with the models. Fresh and upgraded test databases passed. [Migration](../apps/api/alembic/versions/e4f5a6b7c8d9_require_counter_values.py)
- **Credential handling.** The launcher now saves generated credentials to `.env` without displaying them. The plaintext audit entry was redacted from the working copy and did not match the checked local configuration or accounts. Its status outside this workspace remains unverified. [Launcher](../scripts/start.mjs)

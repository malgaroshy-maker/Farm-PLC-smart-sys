# 🧠 AI Features — Algaroshy Farm Smart Irrigation System

**Document Status:** Reconciled with Milestone E (2026-11-19).  
For the complete technical specification, prompt architecture, redaction rules, and provider fallback chain, see [docs/AI.md](AI.md).

---

## 1. Milestone E Shipped Features (Active)

Per owner decisions (2026-11-19), four core features have been shipped with full rule-based offline fallbacks and read-only human-in-the-loop controls:

| Feature | Scope & Mechanism | UI Presentation | Rule-Based Fallback |
|---------|-------------------|-----------------|---------------------|
| **1. AI Alarm Assistant (Bilingual AR/EN)** | Pydantic AI agent (APInex `free/gemini-3.8-flash` → direct Google Gemini → rule-based). Reads alarm matrix, live telemetry, and zone status via read-only tools. Outputs structured `AlarmExplanation`. | "Explain / اشرح" button on every alarm row in Alarm Center & Zone Drawer; persistent floating assistant drawer on all pages. | Pre-compiled catalog explanations, likely causes, and live sensor readings from `alarm_catalog.py`. |
| **2. Weather-Aware Irrigation Advisor** | Open-Meteo API at exact farm coordinates (`32.516250, 14.070361`, Africa/Tripoli). Evaluates upcoming 24h programs against rainfall ($\ge 50\%$ or $\ge 2\text{ mm}$ → skip) and heat ($\ge 38^\circ\text{C}$ or $\text{ET}_0 \ge 7\text{ mm}$ → extend $+20\%$). | One-tap approve suggestion cards with 5-second undo toast on Dashboard and Schedules page. | Deterministic rule engine; with no forecast, safely suggests nothing. |
| **3. Statistical Anomaly Detection** | Pure statistical algorithm (no LLM). Median + MAD / robust z-scores on zone flow and pressure against completed cycle baselines ($N \ge 3$). Flags leaks (ALM-046) and clogged emitters (ALM-047). | Baseline band visualization in Zone Drawer; S2 alarms in Alarm Center with bilingual recovery guidance. | Built entirely on deterministic statistical algorithms. |
| **4. Daily Morning Briefing** | Synthesized at 06:00 farm time (`clock.farm_now()`). Summarizes yesterday's water consumption, cycle outcomes, tripped alarms, anomalies, and today's forecast. | Collapsible top hero card on Dashboard and mobile status screen. | Templated daily summary using live database aggregations. |

---

## 2. Deferred Features (Future Hardware / Production Track)

The following items from the early exploratory wishlist are **deferred** until physical PLC hardware, field cameras, microphones, or multi-year datasets are deployed:

| Feature | Reason for Deferral | Target Phase |
|---------|---------------------|--------------|
| **Predictive Equipment Maintenance** | Requires 30–60+ days of continuous physical pump vibration, electrical current draw, and valve travel telemetry. | Production Track |
| **Water Usage Combinatorial Optimizer** | Blocked until dual-zone operation (`MAX_CONCURRENT_ZONES > 1`) is field commissioned on the real pipe network. | Post-Commissioning |
| **Crop Health Computer Vision** | Requires physical camera mounts, field cabling, and real tree foliage imagery. | Future Phase |
| **Arabic Voice Control** | Field microphone hardware and noisy environment STT tuning required; touch/PWA UI prioritized for mobile operators. | Future Phase |
| **Multi-Year Seasonal Learning Model** | Requires multiple seasonal harvest cycles and crop yield records to train meaningful agronomic weights. | Future Phase |

# 🧠 AI Features — Algaroshy Farm Smart Irrigation System

> Smart AI integrations powered by Google Gemini API with local-first fallback.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    AI Service Layer                       │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │  Gemini API   │  │ Weather API  │  │  Local ML      │  │
│  │  (Cloud)      │  │ (Cloud)      │  │  (Edge/Fallback│  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬────────┘  │
│         │                  │                  │           │
│  ┌──────▼──────────────────▼──────────────────▼────────┐ │
│  │              AI Engine (apps/api/ai/)                 │ │
│  │                                                       │ │
│  │  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │ │
│  │  │ Alarm       │  │ Scheduling   │  │ Anomaly    │  │ │
│  │  │ Assistant   │  │ Optimizer    │  │ Detector   │  │ │
│  │  └─────────────┘  └──────────────┘  └────────────┘  │ │
│  │  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │ │
│  │  │ Weather     │  │ Predictive   │  │ Daily      │  │ │
│  │  │ Advisor     │  │ Maintenance  │  │ Insights   │  │ │
│  │  └─────────────┘  └──────────────┘  └────────────┘  │ │
│  │  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │ │
│  │  │ Water Usage │  │ Crop Health  │  │ Voice      │  │ │
│  │  │ Optimizer   │  │ Vision       │  │ Control    │  │ │
│  │  └─────────────┘  └──────────────┘  └────────────┘  │ │
│  │  ┌─────────────┐                                     │ │
│  │  │ Seasonal    │                                     │ │
│  │  │ Learning    │                                     │ │
│  │  └─────────────┘                                     │ │
│  └──────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## Feature 1: AI Alarm Assistant (Bilingual) 🤖

### Purpose
Operators can ask questions about alarms in **Arabic or English** and get contextualized diagnosis and step-by-step fix guidance.

### How It Works
1. Operator triggers alarm query (text or voice)
2. System gathers context: active alarms, recent sensor values, event log, zone states
3. Gemini API receives structured prompt with alarm definitions (RAG) + live context
4. Response returned in operator's preferred language (AR/EN)

### Example Interactions
```
Operator: "ليش المنطقة 3 ضغطها واطي؟"
AI: "المنطقة 3 (رمان 3) تعاني من انخفاض الضغط (1.2 بار، الحد الأدنى 1.5 بار).
     الأسباب المحتملة:
     1. مضخة التعزيز لا تعمل بكفاءة كاملة (التدفق 5.2 م³/س أقل من المتوقع)
     2. صمام المنطقة 4 مفتوح في نفس الوقت — حاول إيقاف منطقة 4 أولاً
     الخطوة المقترحة: أوقف المنطقة 4 ثم راقب الضغط لمدة دقيقتين"

Operator: "Why is pump 1 faulting repeatedly?"
AI: "Well Pump has faulted 3 times in the last 48 hours (ALM-004).
     Pattern: All faults occurred during Zone 9 (Olives) irrigation — the largest zone.
     Likely cause: Thermal overload from extended runtime on high-demand zone.
     Recommendation: Reduce Zone 9 runtime from 90min to 60min, or add a 15min
     cooldown between Zone 9 and other zones."
```

### API Endpoint
- `POST /api/v1/ai/alarm-assistant` — text query
- `POST /api/v1/ai/alarm-assistant/voice` — audio input (future)

### Tech Stack
- **Gemini 2.5 Flash** for fast responses
- **RAG context**: alarm definitions, sensor readings, event log (last 24h)
- **Fallback**: Pre-built response templates when offline

---

## Feature 2: Smart Irrigation Scheduling 🌱

### Purpose
AI learns optimal watering times, durations, and frequencies per zone based on multi-signal analysis.

### Input Signals
| Signal | Source | Update Frequency |
|--------|--------|-----------------|
| Soil moisture (per zone) | Zone sensors | Every 5 min |
| Weather forecast | Weather API | Every 3 hours |
| Crop type + growth stage | Zone config | Static/seasonal |
| Historical water consumption | Telemetry DB | Aggregated daily |
| Time of day / season | System clock | Real-time |
| Tank level | Tank sensor | Every 1 min |
| Temperature + humidity | Weather station | Every 15 min |

### AI Decision Logic
```
IF moisture < crop_threshold AND no_rain_forecast_24h:
    → Schedule irrigation (AI-calculated duration)
    → Prefer early morning (4-7 AM) or late evening (6-9 PM)
    → Avoid peak heat hours

IF rain_probability > 70% in next 6h:
    → Skip scheduled irrigation
    → Notify operator: "تم تخطي الري — احتمال مطر 75% خلال 4 ساعات"

IF heatwave_detected (T > 42°C for 3+ days):
    → Increase irrigation duration by 20-30%
    → Add midday mist cycle for sensitive crops
```

### API Endpoints
- `GET /api/v1/ai/schedule/suggestions` — AI-proposed schedule changes
- `POST /api/v1/ai/schedule/accept` — operator approves AI suggestion
- `GET /api/v1/ai/schedule/history` — past AI decisions + outcomes

### Tech Stack
- **Gemini API** for decision reasoning
- **Weather API** (OpenWeatherMap or WeatherAPI.com)
- Rule engine for safety constraints (never exceed max_runtime)

---

## Feature 3: Predictive Maintenance 🔧

### Purpose
Detect equipment degradation trends and predict failures before they happen.

### Monitored Metrics
| Equipment | Metric | Warning Sign |
|-----------|--------|-------------|
| Well Pump | Runtime trend, start count, current draw pattern | Increasing start failures, runtime efficiency drop |
| Booster Pump | Pressure output vs input, vibration proxy | Declining pressure ratio at same flow |
| Valves | Open/close response time | Increasing response time = mechanical wear |
| Flow Meters | Reading consistency vs pump state | Drift detection, frozen readings |
| Moisture Sensors | Correlation with irrigation cycles | No response to watering = sensor fault |

### Prediction Model
```
Collect: 30-day rolling window of equipment telemetry
Analyze: Trend lines, standard deviation shifts, anomaly frequency
Output: Risk score (0-100) per device + estimated days to failure
Alert: When risk > 70 → generate maintenance advisory (ALM-038/039)
```

### API Endpoints
- `GET /api/v1/ai/maintenance/health` — equipment health scores
- `GET /api/v1/ai/maintenance/predictions` — upcoming predicted failures
- `GET /api/v1/ai/maintenance/history` — past predictions vs actual outcomes

---

## Feature 4: Anomaly Detection ⚠️

### Purpose
Real-time detection of abnormal patterns that the static alarm thresholds can't catch.

### Detection Types
| Anomaly | Detection Method | Example |
|---------|-----------------|---------|
| Slow leak | Flow > 0 when all zones off | 0.3 m³/h at 2 AM, no zones active |
| Pipe burst | Sudden flow spike + pressure drop | Flow jumps from 8 to 25 m³/h |
| Sensor stuck | Value unchanged for too long | Moisture reads 45% for 72 hours straight |
| Phantom consumption | Water loss between meter and zones | Total zone flow < mainline flow by >15% |
| Unusual pattern | Historical deviation | Zone 6 normally uses 4m³, today used 12m³ |

### Tech Stack
- **Statistical models**: Z-score, IQR on sliding windows
- **Gemini API**: For complex pattern explanation in natural language
- **Local fallback**: Simple threshold + time-based rules

### API Endpoints
- `GET /api/v1/ai/anomalies/active` — current detected anomalies
- `GET /api/v1/ai/anomalies/history` — past anomalies + resolutions
- `POST /api/v1/ai/anomalies/dismiss` — operator marks as false positive (AI learns)

---

## Feature 5: Weather-Aware Advisor 🌤️

### Purpose
Integrate live weather data to proactively adjust irrigation and warn operators.

### Weather Integration
```
Provider: OpenWeatherMap API (free tier) or WeatherAPI.com
Location: Algaroshy Farm coordinates (Libya)
Frequency: Fetch every 3 hours, 7-day forecast
Data: Temperature, humidity, wind, precipitation probability, UV index
```

### Decision Matrix
| Condition | Action | Notification |
|-----------|--------|-------------|
| Rain > 5mm expected in 6h | Skip irrigation | "⏭️ ري المنطقة 2 مؤجل — مطر متوقع" |
| Temperature > 40°C | Extend duration +20% | "🌡️ موجة حر — تم زيادة مدة الري" |
| Wind > 30 km/h | Delay sprinkler zones | "💨 رياح قوية — الري مؤجل" |
| Frost risk (T < 2°C) | Emergency protect roots | "🥶 خطر صقيع — تشغيل حماية الجذور" |
| Humidity > 90% + no wind | Reduce irrigation | "💧 رطوبة عالية — تقليل الري" |

### API Endpoints
- `GET /api/v1/ai/weather/current` — current conditions
- `GET /api/v1/ai/weather/forecast` — 7-day forecast
- `GET /api/v1/ai/weather/advisories` — active weather-based recommendations

---

## Feature 6: Water Usage Optimizer 💧

### Purpose
Calculate optimal zone run combinations to minimize energy, pump cycling, and water waste.

### Optimization Goals
1. Minimize pump start/stop cycles (each cycle wears equipment)
2. Maximize hydraulic efficiency (run compatible zones together)
3. Balance water distribution across all zones
4. Respect zone combination rules (some zones can't run together)

### API Endpoints
- `GET /api/v1/ai/water/optimization` — current optimization suggestions
- `GET /api/v1/ai/water/usage-report` — AI-enhanced usage analysis

---

## Feature 7: Daily AI Insights Report 📊

### Purpose
Automated morning briefing for the farm owner with smart analysis.

### Report Contents
```
🌅 التقرير اليومي — مزرعة الجروشي
التاريخ: 2026-04-18

📊 ملخص الأمس:
• إجمالي المياه المستخدمة: 23.4 م³ (↓12% عن المعدل)
• المناطق المروية: 8 من 12
• وقت تشغيل المضخات: 4.2 ساعة

⚠️ تنبيهات:
• المنطقة 9 (زيتون) — رطوبة التربة أقل من المتوقع بعد الري
  → مقترح: زيادة مدة الري من 90 إلى 110 دقيقة

🔧 صيانة:
• مضخة البئر — 1,847 ساعة تشغيل (متبقي 153 ساعة للصيانة)

🌤️ توقعات اليوم:
• حار جاف (38°C)، لا أمطار متوقعة
  → الري المسائي مُوصى به

💡 اقتراح الذكاء الاصطناعي:
• تجميع المناطق 1+2+3 في دورة واحدة يوفر 15% من وقت تشغيل المضخة
```

### Delivery
- Available in web dashboard and mobile app
- Push notification at configured time (default 6:00 AM)
- Email digest (optional)

### API Endpoint
- `GET /api/v1/ai/insights/daily` — today's report
- `GET /api/v1/ai/insights/weekly` — weekly summary
- `GET /api/v1/ai/insights/history` — past reports

---

## Feature 8: Crop Health Vision 📷 (Future Phase)

### Purpose
Camera-based crop health monitoring using Gemini Vision API.

### Capabilities
- Detect crop stress (wilting, yellowing, browning)
- Identify pest/disease early
- Verify irrigation coverage (dry spots)
- Growth stage tracking

### API Endpoint
- `POST /api/v1/ai/vision/analyze` — upload image for analysis
- `GET /api/v1/ai/vision/reports` — historical analysis reports

---

## Feature 9: Arabic Voice Control 🎙️ (Future Phase)

### Purpose
Hands-free field operation using Arabic voice commands.

### Commands
```
"شغّل المنطقة 5 لمدة 30 دقيقة"   → Start zone 5 for 30 min
"أوقف كل شي"                      → Emergency stop all
"شنو حالة المنطقة 3؟"              → Query zone 3 status
"اعرض التقرير اليومي"              → Read daily report
```

### Tech Stack
- Google Speech-to-Text (Arabic dialect support)
- Gemini API for intent parsing
- Text-to-Speech for response

### API Endpoint
- `POST /api/v1/ai/voice/command` — audio input → action
- `GET /api/v1/ai/voice/history` — past voice commands

---

## Feature 10: Seasonal Learning Model 📈 (Future Phase)

### Purpose
Multi-year learning model that improves irrigation decisions over time.

### Learning Signals
- Crop yield correlation with irrigation patterns
- Seasonal soil moisture baselines per zone
- Weather pattern recognition (dry years vs wet years)
- Equipment degradation rate modeling

### API Endpoint
- `GET /api/v1/ai/learning/models` — active learning models
- `GET /api/v1/ai/learning/recommendations` — season-based recommendations

---

## Implementation Priority

| Phase | Features | Dependencies |
|-------|----------|-------------|
| **Phase 1 (with Backend)** | AI Alarm Assistant, Weather Advisor | Gemini API, Weather API |
| **Phase 2 (with Simulator)** | Anomaly Detection, Smart Scheduling | Telemetry pipeline |
| **Phase 3 (with Web)** | Daily Insights, Water Optimizer | UI components |
| **Phase 5 (with Reports)** | Predictive Maintenance | 30+ days of data |
| **Future** | Crop Vision, Voice Control, Seasonal Learning | Camera hardware, mic |

---

## Offline / Local Fallback Strategy

All AI features must degrade gracefully when internet is unavailable:

| Feature | Online Mode | Offline Fallback |
|---------|------------|-----------------|
| Alarm Assistant | Gemini API contextual response | Pre-built templates from ALARM_MATRIX |
| Scheduling | AI optimization | Static schedule continues unchanged |
| Anomaly Detection | Cloud ML + Gemini explanation | Local statistical rules (Z-score) |
| Weather Advisor | Live forecast data | Last known forecast + conservative mode |
| Daily Insights | Gemini-generated report | Stats-only report without AI commentary |
| Predictive Maintenance | Cloud ML trend analysis | Local threshold alerts only |

---

## Data Privacy & Safety

1. **No PII** sent to Gemini API — only sensor values, alarm codes, zone IDs
2. **PLC remains safety authority** — AI suggests, operators/PLC decides
3. **AI cannot directly control equipment** — all AI outputs go through the command validation pipeline
4. **Audit trail** — every AI suggestion logged with `actor_type: "ai"` in event log
5. **Operator override** — human can always override AI suggestions

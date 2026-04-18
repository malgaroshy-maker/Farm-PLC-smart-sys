# Changelog

All notable changes to the Algaroshy Farm Smart Irrigation System will be documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/).

---

## [Unreleased]

### Added
- 🧠 `docs/AI_FEATURES.md` — 10 AI feature specifications
- AI type definitions in `@algaroshy/contracts` (ai-types.ts)
- 15+ AI enums: AIFeature, AnomalyType, WeatherCondition, VoiceIntent, etc.
- 25+ AI interfaces: AlarmAssistant, WeatherAdvisor, AnomalyDetection, etc.
- AI env configuration: Gemini API, Weather API, feature toggles
- Phase 7 (AI Integration) added to PROJECT_STATUS.md
- Backend deps: google-genai, numpy, apscheduler, jinja2

## [0.1.0] — 2026-04-18

### Added — Phase 0 Complete ✅
- Project documentation pack (16 docs + 2 SVG layouts) in `docs/`
- Root `README.md` with project overview, tech stack, and setup guide
- `.gitignore` for Python + Node.js + React Native monorepo
- `.env.example` environment configuration template
- `CHANGELOG.md` version history tracking
- `CONTRIBUTING.md` contribution guidelines and development workflow
- `PROJECT_STATUS.md` progress tracker for all build phases
- pnpm + Turborepo monorepo (7 workspace packages)
- `@algaroshy/contracts` — shared enums, types, alarm registry, 12-zone seed data
- `apps/api` — FastAPI backend scaffold
- `apps/web` — Vite 8 + React 19 + TypeScript + Tailwind v4.2.2
- `apps/simulator` — Python simulation engine scaffold
- `apps/mobile` — Expo placeholder
- Git initialized, first commit, pushed to GitHub

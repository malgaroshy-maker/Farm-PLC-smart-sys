# UI_WIREFRAMES.md

## 1. UX Principles

- Arabic-first bilingual
- map-first dashboard
- large touch-friendly controls
- critical alarms always visible
- stale data clearly distinguished from live data
- commands require confirmation for risky actions

## 2. Web Screens

### 2.1 Login
- username/password
- language toggle
- remember device optional

### 2.2 Main Dashboard
Sections:
- farm status header
- active alarms banner
- live farm map
- source and pump cards
- current active zones
- tank level card
- pressure/flow cards
- moisture summary strip
- recent events

### 2.3 Live Farm Map
Map must show:
- zone polygons
- current zone colors
- animated pipelines for active flow
- tank and well icons
- pump house/control room icon
- device badges
- tooltip/detail drawer on click

Zone drawer:
- current state
- source mode
- pressure
- flow
- moisture
- last cycle
- active alarms
- controls if allowed

### 2.4 Alarms Center
- severity tabs
- active list
- history list
- ack/reset actions
- operator guidance panel
- filters by zone/device/date

### 2.5 Schedules
- calendar/table mode
- per-zone schedule editor
- overlap/conflict warnings
- season profile controls
- enable/disable quick actions

### 2.6 Reports
- daily irrigation report
- water usage charts
- pump runtime charts
- alarm history
- export controls

### 2.7 Admin
- users and roles
- thresholds
- zone combinations
- device config
- source policies
- notification settings

## 3. Android Screens

### 3.1 Home
- condensed farm status
- critical alarms card
- mini map preview
- current running zones
- emergency stop/stop-all button for authorized users

### 3.2 Live Map
- pan/zoom farm map
- tap zone for detail bottom sheet
- quick start/stop buttons
- freshness badge

### 3.3 Alarm Center
- active alarms first
- swipe ack
- reset button where permitted
- bilingual guidance
- notification history

### 3.4 Zone Detail
- state chip
- pressure / flow / moisture cards
- source
- schedule summary
- recent cycles
- actions

### 3.5 Reports
- simplified charts for mobile
- export or share later

## 4. Suggested Component List

### Shared components
- status chip
- severity badge
- telemetry card
- zone card
- alarm row
- confirmation dialog
- data stale banner
- map legend

### Web-specific
- resizable map and side panel
- table views
- trend chart panels

### Mobile-specific
- bottom sheets
- large quick-action buttons
- condensed cards

## 5. Color System

- gray = idle/off
- blue/cyan = water actively flowing
- green = healthy running
- yellow = warning
- orange = major issue
- red = critical fault
- purple optional = maintenance/manual

## 6. Key Interaction Rules

- stop-all should require confirmation
- dangerous/manual override actions should require role check and confirmation
- any control on stale data should warn user
- map remains visible even when panels open

# TEST_PLAN.md

## 1. Test Levels

### Unit Tests
- domain rules
- threshold evaluators
- command validators
- schedule validators

### Integration Tests
- API + DB
- simulator + backend
- backend + WebSocket
- alarm engine + notifications

### End-to-End Tests
- login
- map loads
- start zone
- zone enters running state
- telemetry updates
- alarm appears
- report includes cycle

## 2. Core Acceptance Scenarios

1. Start a valid zone in manual mode
2. Reject a disallowed zone combination
3. Trigger no-flow after start
4. Trigger tank critical low and verify protective stop
5. Trigger stale telemetry
6. Acknowledge and reset alarm
7. Execute schedule automatically
8. Export daily irrigation report
9. Verify audit log for user control action
10. Recover after restart to safe state

## 3. Commissioning Checks

- all I/O mapped correctly
- pump run/fault feedbacks correct polarity
- valve open/close logic correct
- sensor scaling correct
- pressure/flow thresholds tuned
- notification channels verified
- role permissions verified

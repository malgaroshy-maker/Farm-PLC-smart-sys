# SIMULATION_PLAN.md

## 1. Goal

Allow development of the entire stack before real hardware is connected.

## 2. Simulator Responsibilities

- maintain simulated zone states
- simulate pumps, valves, flow, pressure, moisture, tank level
- accept commands through same contracts as production backend
- emit telemetry and alarms
- support scenario injection

## 3. Simulation Model

### Inputs
- zone commands
- system mode changes
- threshold config
- schedule triggers
- fault injections

### Outputs
- live state
- telemetry streams
- command status
- alarms
- event history

## 4. Simple Behavioral Rules

- opening a valid zone with running source should increase flow
- tank-fed zones consume tank level over time
- moisture rises slowly while irrigating
- abnormal conditions can be injected:
  - valve stuck
  - pump fault
  - no flow
  - low pressure
  - leak / excess flow
  - stale comms

## 5. Required Scenarios

1. normal tank-fed irrigation cycle
2. direct-well zone cycle
3. tank low warning
4. tank critical low during run
5. booster failed start
6. well failed start
7. valve failed open
8. no flow after valve open
9. pressure collapse when forcing disallowed second zone
10. communication loss while PLC/simulator continues
11. stale data on client
12. repeated fault leading to maintenance advisory

## 6. Success Criteria

- apps can be built against simulator only
- alarm center can be fully tested
- reports can be generated from simulated history
- command rules can be validated before hardware

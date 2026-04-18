# PLC_CONTROL_LOGIC.md

## 1. Control Philosophy

The PLC is the local authority for safe irrigation behavior.  
Remote apps request actions. The PLC decides whether those actions may execute.

## 2. System Modes

### Off
No automatic irrigation. Manual commands blocked except maintenance-authorized actions.

### Auto
Schedules and sensor-assisted logic may start irrigation automatically.

### Manual
Authorized users may request zone runs manually, but interlocks still apply.

### Maintenance
Used for service and testing. Selected alarms may be suppressed, but protection logic for dangerous conditions remains active.

## 3. Sequence Overview

### 3.1 Zone Start Sequence
1. receive zone request
2. verify system mode allows start
3. verify zone enabled
4. verify no critical active alarm blocking start
5. verify source availability
6. verify hydraulic capacity for requested combination
7. command source pump path as needed
8. verify pump started within timeout
9. command valve open
10. wait for valve feedback or derived success window
11. validate pressure and flow become healthy
12. mark zone state `running`

### 3.2 Zone Stop Sequence
1. receive stop request or end-of-duration
2. command valve close
3. verify flow collapses appropriately
4. stop pump if no more zones need same source path
5. mark zone completed or stopped
6. log cycle result

## 4. Source Selection Rules

Each zone has:
- preferred source
- whether direct well is allowed
- fallback policy
- emergency low-tank policy

Example:
- close/lower zones may use direct well if configured
- most zones use tank + booster by default

## 5. Interlocks

A zone start must be blocked if:
- emergency stop active
- booster fault active when booster path required
- well pump fault active when well path required
- tank critically low and no emergency exception applies
- dry-run risk active
- requested zone combination not allowed
- required thresholds missing
- active severe overpressure/underpressure condition exists
- valve/pump/device is disabled or under maintenance lock

## 6. Runtime Rules

- each zone has max runtime
- runtime overrun produces warning or stop based on config
- retries allowed only for selected transient failures
- repeated retries escalate to alarm

## 7. Dual-Zone Logic

### Default
disabled until commissioning proves safe.

### When enabled
second zone start requires:
- combination allowed in config
- expected combined flow within range
- pressure remains above minimum
- no capacity alarm active
- source supports the combination

If pressure drops below critical after second zone starts:
- stop second zone first
- re-evaluate
- raise alarm

## 8. Dry-Run Protection

If dry-run risk becomes active:
- stop affected pump immediately
- stop dependent zones
- latch critical alarm
- require acknowledgement and manual reset depending on final policy

## 9. Pressure/Flow Validation

### Start validation
After a zone starts, within a configured window:
- pressure must enter healthy band
- flow must exceed minimum expected
Otherwise:
- retry if allowed
- else abort zone and alarm

### Run validation
During operation:
- pressure must remain between min and max
- flow must remain within expected band
Out-of-band conditions:
- warning first if brief
- stop or isolate if sustained or severe

## 10. Moisture Logic

Phase 1:
- moisture is advisory + reportable
- optional use for irrigation permission or optimization

Later:
- adaptive schedule shortening/lengthening
- skip cycle suggestions

## 11. Restart Behavior

After PLC restart:
- enter safe initialization state
- load retained schedule/config state
- detect any valves/pumps in uncertain state
- require reconciliation before resuming automatic sequences
- active irrigation should not resume blindly without clear rules

## 12. Recommended State Machines

### System state machine
- idle
- auto_ready
- manual_ready
- maintenance_ready
- fault_blocked

### Zone state machine
- off
- queued
- starting_pump
- opening_valve
- validating_flow
- running
- stopping
- completed
- warning
- faulted

### Pump state machine
- stopped
- starting
- running
- failed_start
- faulted
- cooldown optional

## 13. PLC Pseudocode Sketch

```text
IF estop THEN
  stop_all_outputs();
  latch_alarm(ALM-041);
END_IF;

FOR each zone_request:
  IF can_start(zone) THEN
    execute_start_sequence(zone);
  ELSE
    reject_command(reason);
  END_IF;
END_FOR;

FOR each active_zone:
  validate_pressure_flow(zone);
  validate_runtime(zone);
  IF critical_fault THEN
    stop_zone_or_system();
  END_IF;
END_FOR;
```

## 14. Commissioning Parameters to Tune

- pressure_min_bar by zone/group
- pressure_max_bar by zone/group
- flow_min_m3h by zone/group
- flow_max_m3h by zone/group
- start validation timeout
- valve travel timeout
- retry count
- tank warning and critical levels
- stale telemetry thresholds

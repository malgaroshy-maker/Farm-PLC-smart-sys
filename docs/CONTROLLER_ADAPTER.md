# Controller adapter (Milestone G3)

The farm controller is connected through a **gateway** (`apps/simulator/src/client.py`). The gateway talks to the API:
- it loads the farm layout (zones, valves, pumps, sensors) from the database;
- it pushes live state to `/state/sync`, once a second;
- it pulls pending commands and reports their results.

The farm side is an **adapter** that implements `ControllerAdapter` (`apps/simulator/src/adapter.py`):

| Adapter | File | Used for |
|---|---|---|
| `simulator` (default) | `src/adapters/simulator_adapter.py` | The physics simulator: today's demo. |
| `opcua` | `src/adapters/opcua_adapter.py` | A Siemens S7-1200/1500 over OPC UA. **Skeleton:** the node ids come from the TIA Portal project in Milestone G5. |

Select an adapter with environment variables:

```
CONTROLLER_ADAPTER=simulator          # default
CONTROLLER_ADAPTER=opcua              # needs:
OPCUA_TAGMAP=apps/simulator/opcua_tagmap.example.json
```

## Safety rule
The PLC owns the interlocks. Adapters only forward commands; they never bypass or imitate the PLC's safety logic on the real hardware path. The API's own interlocks stay in place as a first check.

## OPC UA command handshake
1. The gateway writes `type`, `target` and `duration_min`, then increments `seq`.
2. The PLC checks its interlocks, then acts or refuses. It writes `ack_status` (1 = accepted, 2 = rejected) and `ack_reason`, then sets `ack_seq = seq`.
3. If no acknowledgement arrives within 5 s, the command is reported as `failed: plc_no_ack`.

Command types: `start_zone = 1`, `stop_zone = 2`, `stop_all = 3`, `reset_alarm = 4`.

A zone without tags in the tag map is reported as `failed: no_tags_for:<zone>`. The gateway never pretends a command succeeded.

## Tests
`apps/simulator/tests/test_opcua_adapter.py` starts a real in-process OPC UA server built from a tag map. That server answers the handshake the way the PLC will: it accepts a start, rejects an interlocked zone, and in a separate test stays silent so the no-ack path is covered. Validation against **PLCSIM Advanced** comes in G5, before any hardware.

## Adding a zone
Settings → Zones & equipment → Add a zone creates the zone, its valve and its moisture sensor in the database.
- **Controller:** the simulator picks the new zone up on its next start. For a PLC, add the zone's tags to the tag map.
- **Map:** the zone appears on the map once its outline is traced (`tools/map-geometry`).

# 📻 Normalized MMDVM DMR Sessions

[Documentation index](README.md) · [MMDVM telemetry bus](TELEMETRY.md) · [Plugin framework](PLUGINS.md) · [Architecture](ARCHITECTURE.md)

Alpha18 adds a bounded normalized DMR call/session layer on top of the passive MMDVM telemetry bus.

The purpose is simple: **plugins should consume one coherent YWD session object instead of having to understand the quirks of individual raw MMDVM-Host events.**

This remains an observation-only capability. It does not change RF mode, own the modem serial port, transmit, or grant plugins IP networking.

## Why correlation is needed

The pinned MMDVM-Host emits rich identity on DMR `start` / `late_entry` events, including source ID, source info, destination, group/private state, slot, and RF/network source.

Terminal events such as `end`, `lost`, and `timeout` are intentionally much smaller. They may contain only the slot and final metrics such as duration, BER, packet loss, or RSSI summary.

YWD therefore correlates those events by DMR time slot while the bridge is running:

```text
DMR START
  src/dst/group/slot/source
        │
        ▼
YWD ACTIVE SESSION
  stable identity + direction
        │
        ├── RSSI / BER samples continue independently
        │
        ▼
DMR END
  slot + final metrics
        │
        ▼
YWD COMPLETED SESSION
  original identity + final metrics
```

Raw `dmr.active` and `dmr.last` telemetry remain available for compatibility and diagnostics. The normalized layer is additive.

## Runtime shape

The trusted bridge snapshot adds:

```json
{
  "sessions": {
    "schema": 1,
    "active": [],
    "last": null,
    "recent": []
  }
}
```

The layer is deliberately bounded:

- at most one active session per DMR slot
- one `last` completed/terminal session
- the newest 12 terminal sessions in `recent`
- no database
- no unbounded history file
- no additional polling process

Correlation runs only when the existing MQTT bridge receives a DMR event.

## Normalized session schema

Representative completed RF session:

```json
{
  "session_id": "dmr-2-1786995743000",
  "protocol": "DMR",
  "state": "completed",
  "result": "end",
  "correlation": "matched",
  "call_type": "voice",
  "late_entry": false,
  "slot": 2,
  "source": "rf",
  "direction": "rf_to_network",
  "src_id": 3196104,
  "src_info": "KJ6YWD Jim",
  "dst_id": 9990,
  "group": false,
  "destination_type": "private",
  "frames": null,
  "started_at": "2026-08-17T19:42:15.8Z",
  "ended_at": "2026-08-17T19:42:23.4Z",
  "last_action": "end",
  "event_count": 2,
  "metrics": {
    "duration_s": 7.6,
    "ber_pct": 3.0,
    "packet_loss_pct": null,
    "rssi_dbm": {
      "min": -66,
      "max": -47,
      "avg": -57
    }
  }
}
```

### Identity fields

| Field | Meaning |
|---|---|
| `session_id` | Ephemeral bridge-runtime identifier. Do not treat it as a permanent database key. |
| `protocol` | `DMR` in schema 1. |
| `slot` | DMR time slot. |
| `src_id` | Source DMR ID when supplied by MMDVM-Host. |
| `src_info` | Resolved source information when supplied by MMDVM-Host. |
| `dst_id` | Destination DMR ID / talkgroup. |
| `group` | Boolean group/private indication when known. |
| `destination_type` | `group`, `private`, or `unknown`. |
| `call_type` | `voice`, `data`, or `unknown`. Data is identified from MMDVM's frame-count metadata. |
| `late_entry` | True when YWD first observed the session through MMDVM `late_entry`. |

### Direction

YWD preserves MMDVM's original source and adds a normalized direction:

| `source` | `direction` |
|---|---|
| `rf` | `rf_to_network` |
| `network` | `network_to_rf` |
| unavailable | `unknown` |

The direction describes where the DMR stream entered MMDVM-Host. It does not imply that both sides have equivalent measurements. In particular, RSSI remains an RF-receive measurement and is not synthesized for a network-originated call.

### State/result

Active sessions use:

```text
state = active
result = null
correlation = open
```

Terminal results currently include:

- `end` → `state=completed`
- `lost`
- `timeout`
- `rejected`
- `invalid`
- `superseded` when a new start arrives on a slot before the prior session received a terminal event

`result` preserves the terminal reason even when `state` is normalized to `completed` for a normal end.

### Correlation quality

`correlation` is intentionally explicit:

| Value | Meaning |
|---|---|
| `open` | Active start/late-entry session waiting for a terminal event. |
| `matched` | Terminal event matched an active session on the same slot. |
| `orphan` | A terminal event arrived without a corresponding active session. Identity is left unknown unless the terminal event itself supplied it. |
| `superseded` | A new start replaced an older still-active session on the same slot. |

YWD does **not** invent missing callsigns, IDs, direction, or metrics to make an orphan look complete.

A bridge restart resets the in-memory/runtime session correlation state. If MMDVM-Host then emits only the sparse end of a call that began before the bridge restarted, that end is expected to appear as an `orphan` session rather than being guessed.

## Final metrics

The normalized `metrics` object uses stable YWD names:

| Field | Source |
|---|---|
| `duration_s` | MMDVM terminal duration |
| `ber_pct` | MMDVM terminal BER |
| `packet_loss_pct` | network-originated terminal packet-loss percentage when supplied |
| `rssi_dbm.min` | RF session minimum RSSI |
| `rssi_dbm.max` | RF session maximum RSSI |
| `rssi_dbm.avg` | RF session average RSSI |

MMDVM's upstream RSSI key `ave` is normalized to YWD `avg` for consumers.

The separate live RSSI and BER telemetry samples remain available. Session metrics represent the terminal/call summary and should not be confused with the most recent live sample.

## Public telemetry API

The trusted `mmdvm_telemetry.public_snapshot()` keeps the existing Alpha17 fields and adds:

```text
active_session
last_session
sessions.active[]
sessions.last
sessions.recent[]
```

The old fields remain:

```text
active_call
last_event
rssi
ber
bridge
mode
```

This lets existing consumers continue working while new consumers move to normalized sessions.

## MMDVM Live Telemetry plugin 0.2.0

The reference telemetry plugin is the first consumer of the normalized contract.

Its WebUI displays:

- the normalized active session
- normalized RF/network direction
- the last completed/terminal session
- result
- duration
- BER
- packet loss when applicable
- average RF RSSI when applicable

Its sandboxed service journal also reads the normalized session snapshot rather than reconstructing DMR identity from raw end events.

The plugin still has:

- no RF ownership
- no serial-device access
- no normal IP sockets
- no arbitrary systemd control
- only the declared `read:mmdvm-telemetry` observation capability plus its existing lifecycle/journal capability

## Contract for future MMDVM plugins

New first-party MMDVM plugins should prefer the normalized session API whenever they need call identity/state.

They should not:

- re-correlate raw `start` and `end` messages independently
- scrape MMDVM-Host journal text for identity already present in the session API
- infer RSSI for network-originated calls
- assume an orphan terminal event has the identity of a previous unrelated call
- use the session layer as permission to control RF

RF configuration/control remains a separate future capability with explicit core ownership/arbitration.

## Alpha18 physical test

1. Update from the frozen Alpha17.1 checkpoint.
2. Confirm core DMR, BrandMeister, OLED, broker, bridge, and telemetry plugin remain healthy.
3. Key an HT into the hotspot and let the call end.
4. Confirm the Plugin Manager `Last session` row retains source/destination/direction after the raw MMDVM end event.
5. Confirm RF duration, BER, and RSSI average appear on the same normalized session.
6. Receive a network-originated call and confirm direction is `NET → RF`, packet-loss/BER final metrics are retained, and no RF RSSI is invented for that network call.
7. Reboot with the plugin enabled and verify the plugin returns active. Session history is runtime-only and may reset across bridge/Pi restart.
8. Confirm `systemctl --failed --no-pager` remains clean.

Useful raw snapshot check:

```bash
sudo python3 -m json.tool /run/ywd-hotspot-telemetry/telemetry.json
```

Look for the `sessions` object alongside the existing raw `dmr`, `rssi`, and `ber` objects.

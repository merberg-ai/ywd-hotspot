# 📻 Normalized MMDVM DMR Sessions

[Documentation index](README.md) · [MMDVM telemetry](TELEMETRY.md) · [Passive DMR Voice](DMR-VOICE.md) · [Plugin framework](PLUGINS.md) · [Architecture](ARCHITECTURE.md)

YWD-Hotspot maintains a bounded normalized DMR call/session layer on top of the trusted passive MMDVM telemetry path.

The purpose is simple: **trusted dashboard/plugin consumers should receive one coherent YWD session object instead of independently reconstructing identity from individual raw MMDVM-Host events.**

This remains observation-only. It does not change RF mode, own the modem serial port, transmit, or grant plugins network/device authority.

## Why correlation is needed

MMDVM-Host start/late-entry events can include rich identity such as source ID, source info, destination, group/private state, slot and RF/network source. Terminal events such as `end`, `lost` and `timeout` can be much smaller and may contain mostly final metrics.

YWD correlates those events by DMR time slot while the bridge is running:

```text
DMR START / LATE ENTRY
  identity + slot + source
        │
        ▼
YWD ACTIVE SESSION
        │
        ├── BER/RSSI telemetry may arrive independently
        │
        ▼
DMR END / LOST / TIMEOUT
        │
        ▼
YWD TERMINAL SESSION
  retained identity + supplied final metrics
```

Raw telemetry remains available for diagnostics; normalized sessions are the preferred higher-level contract.

## Runtime shape

The trusted telemetry snapshot contains a bounded `sessions` object:

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

Current bounds:

- at most one active session per DMR slot;
- one `last` terminal session;
- a small recent terminal-session ring;
- no SQL/database;
- no unbounded history;
- no additional polling process solely for session correlation.

A bridge restart resets in-memory/runtime correlation. An end event for a call that began before the restart can therefore appear as an `orphan`; YWD does not guess missing identity.

## Representative completed RF session

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
  "started_at": "2026-08-17T19:42:15.8Z",
  "ended_at": "2026-08-17T19:42:23.4Z",
  "last_action": "end",
  "event_count": 2,
  "metrics": {
    "duration_s": 7.6,
    "ber_pct": 0.6,
    "packet_loss_pct": null,
    "rssi_dbm": null
  }
}
```

`rssi_dbm` is intentionally allowed to be `null`. The RC1 reference duplex HAT produced valid BER/session/voice data but did not provide usable RSSI, so normalized sessions must not invent a signal value merely to make the object look complete.

## Identity fields

| Field | Meaning |
|---|---|
| `session_id` | Ephemeral bridge-runtime identifier; not a permanent database key. |
| `protocol` | `DMR` in schema 1. |
| `slot` | DMR time slot. |
| `src_id` | Source DMR ID when supplied upstream. |
| `src_info` | Resolved source information when supplied upstream. |
| `dst_id` | Destination DMR ID/talkgroup. |
| `group` | Group/private indication when known. |
| `destination_type` | `group`, `private`, or `unknown`. |
| `call_type` | `voice`, `data`, or `unknown`. |
| `late_entry` | True when YWD first observed the session through MMDVM late entry. |

## Direction

YWD preserves MMDVM's source and adds a normalized direction:

| `source` | `direction` |
|---|---|
| `rf` | `rf_to_network` |
| `network` | `network_to_rf` |
| unavailable | `unknown` |

Direction describes where the DMR stream entered MMDVM-Host. It does **not** imply equivalent measurements in both directions. RSSI is meaningful only for actual local RF reception and only when the modem firmware supplies it.

## State / result / correlation

Active sessions normally use:

```text
state = active
result = null
correlation = open
```

Terminal results can include:

- `end` → normal completed session;
- `lost`;
- `timeout`;
- `rejected`;
- `invalid`;
- `superseded` when a new start replaces an older still-open slot session.

Correlation quality is explicit:

| Value | Meaning |
|---|---|
| `open` | Active session waiting for a terminal event. |
| `matched` | Terminal event matched the active session on that slot. |
| `orphan` | Terminal event arrived without a matching active session. |
| `superseded` | A new start replaced an older still-open session. |

YWD does not invent callsigns, IDs, direction or metrics for an orphan terminal event.

## Metrics

Normalized metric names include:

| Field | Meaning/source |
|---|---|
| `duration_s` | terminal call duration when supplied |
| `ber_pct` | BER when supplied |
| `packet_loss_pct` | network-originated packet loss when supplied |
| `rssi_dbm` | RF RSSI summary/value only when a usable upstream value exists |

Older/raw MMDVM RSSI structures may contain min/max/average values; trusted normalization should preserve real measurements but must leave RSSI absent/null when unsupported. BER and RSSI are separate measurements and are never converted into one another.

## Public/trusted consumers

The dashboard/session helpers expose current/last/recent normalized state to trusted core consumers. New first-party MMDVM-aware features should prefer this contract when they need call identity/state rather than scraping journal text or re-correlating raw MQTT events themselves.

The retired `mmdvm-live-telemetry` proof plugin is **not** the owner of this contract. Session state is trusted core infrastructure and remains useful for the dashboard, diagnostics, RX Monitor support and future capability-gated plugins.

## Plugin contract

A plugin consuming session/telemetry information still receives only the explicitly granted observation capability. It does not gain:

- RF ownership;
- `/dev/serial0` access;
- arbitrary sockets/network access;
- systemd/root control;
- permission to infer or synthesize missing RF measurements.

New consumers should not:

- independently reconstruct start/end identity when normalized session state already exists;
- infer RSSI for network-originated calls;
- fabricate RSSI when modem firmware reports zero/unavailable;
- assume an orphan belongs to the previous unrelated call;
- treat observation state as permission to transmit.

## Diagnostics

```bash
sudo python3 -m json.tool /run/ywd-hotspot-telemetry/telemetry.json
```

Look for `sessions` alongside the lower-level DMR/BER/RSSI/bridge objects. On hardware without RSSI support, healthy session objects with BER and `rssi_dbm: null` are expected.

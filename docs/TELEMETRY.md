# 📡 MMDVM Telemetry

[Docs index](README.md) · [Architecture](ARCHITECTURE.md) · [Display](DISPLAY.md) · [MMDVM Sessions](MMDVM-SESSIONS.md)

YWD-Hotspot keeps a passive structured MMDVM telemetry path as **trusted core infrastructure**. The old `mmdvm-live-telemetry` proof plugin is retired; the broker/telemetry/session infrastructure remains because dashboard instrumentation, normalized session state, diagnostics, RX Monitor support, and future capability-gated consumers use it independently of that plugin.

This path never owns the modem or RF configuration.

## Data path

```text
MMDVM-Host
   │ structured MQTT JSON
   ▼
127.0.0.1:18883
YWD loopback Mosquitto
   │
   ▼
ywd-mmdvm-telemetry.service
trusted YWD bridge
   │ sanitized bounded snapshot/session input
   ▼
/run/ywd-hotspot-telemetry/telemetry.json
   │
   ├─ dashboard instrumentation
   ├─ normalized DMR sessions
   ├─ diagnostics
   └─ explicit future capability consumers
```

YWD Extended also emits per-frame passive DMR voice envelopes on a separate `ywd-mmdvm/voice` topic consumed by `ywd-mmdvm-voice.service`.

No telemetry consumer receives modem serial ownership or RF TX authority merely because it can read this state.

## MMDVM-Host configuration

YWD-Hotspot generates a local MQTT target:

```ini
[MQTT]
Host=127.0.0.1
Port=18883
Auth=0
Keepalive=60
Name=ywd-mmdvm
```

Structured low-rate JSON topic:

```text
ywd-mmdvm/json
```

YWD Extended passive voice topic:

```text
ywd-mmdvm/voice
```

Per-frame voice traffic is kept separate from the low-rate telemetry snapshot path.

## Loopback broker boundary

The YWD listener is intentionally local-only:

```text
listener 18883 127.0.0.1
allow_anonymous true
persistence false
```

There is no YWD LAN/WAN telemetry listener. `ywd-mqtt.service` owns the dedicated loopback broker instance/configuration and conflicts with the distro `mosquitto.service` so both brokers are not left competing for service ownership.

The image/runtime dependencies include `mosquitto` and `mosquitto-clients`; normal runtime reconciliation can also install/repair the required broker/client packages when needed. The broker is still a local implementation detail, not a user-facing MQTT service.

## Trusted bridge

`ywd-mmdvm-telemetry.service` runs as the restricted `ywd-hotspot` account with only the network access needed to reach loopback.

The bridge accepts known structured MMDVM message families rather than copying arbitrary MQTT payloads into browser/plugin-visible state.

Runtime snapshot:

```text
/run/ywd-hotspot-telemetry/telemetry.json
```

The file lives under tmpfs runtime state, is recreated at boot, and contains no plugin configuration or reusable credentials.

The MMDVMHost unit requests the YWD MQTT broker and telemetry bridge so the passive structured path is available whenever that runtime starts. Side-infrastructure failure remains diagnostic; it is not permission to seize RF/modem ownership.

## RSSI normalization and hardware reality

Supported MMDVM_HS ADF7021 firmware may report the positive magnitude of received dBm in its RSSI bytes. YWD generates the matching normalization map:

```text
0 0
255 -255
```

and configures MMDVM-Host to use:

```ini
[Modem]
RSSIMappingFile=/etc/ywd-hotspot/mmdvm-hs-rssi.dat
```

A reported magnitude such as `62` can therefore normalize to approximately `-62 dBm`.

**This mapping cannot create RSSI that the modem firmware never sends.** RSSI reporting is optional in MMDVM_HS firmware builds (commonly associated with the firmware-side `SEND_RSSI_DATA` option). Recompiling MMDVM-Host on the Pi does not make a HAT firmware that reports zero RSSI suddenly produce a real measurement.

During `0.2.0-rc1` physical acceptance, the reference duplex HAT produced healthy DMR voice/BER telemetry but all RF voice-frame RSSI fields were `0`. That established the expected unsupported behavior for that firmware: BER works, RSSI remains unavailable, and the WebUI hides RSSI-only instrumentation instead of inventing dBm.

YWD-Hotspot does not automatically flash MMDVM HAT firmware because board/clone/duplex/oscillator variants make that unsafe as a generic appliance action.

## DMR/session information

Trusted telemetry/session normalization can expose bounded state such as:

- current MMDVM mode;
- latest usable RSSI and BER samples with age/source semantics;
- DMR source/destination IDs;
- group/private status;
- timeslot;
- RF vs network direction;
- call/session start/end/lost/timeout state;
- completed duration/BER/loss/RSSI summaries when supplied upstream;
- bridge heartbeat/message/error counters.

RSSI is an RF receive measurement. Network-originated audio does not acquire a local RF RSSI sample, and RF RSSI remains absent when the modem firmware supplies no usable value.

See **[MMDVM-SESSIONS.md](MMDVM-SESSIONS.md)** for normalized call/session semantics.

## Dashboard relationship

The dashboard does **not** depend on an MMDVM telemetry plugin. It reads trusted core activity/telemetry/session state through the normal dashboard API.

That is why retiring the old proof plugin did not remove:

```text
ywd-mqtt.service
ywd-mmdvm-telemetry.service
```

The current LIVE DMR panel uses measurements honestly: BER can remain visible even when RSSI is unavailable, and RSSI presentation is suppressed until a usable RSSI value exists.

## Update / boot behavior

Telemetry runtime is provisioned as passive side infrastructure. Normal application updates reinstall the trusted units while preserving RF active/enabled policy and the selected MMDVM runtime.

Candidate validation treats telemetry as a coherent capability set: if telemetry markers are present in a candidate, the broker config, bridge/session/runtime helpers, package/runtime assumptions, and systemd units must be present coherently regardless of branch name.

Shared runtime state under `/run/ywd-hotspot` uses preservation where required so completion of one-shot first-boot setup cannot remove the live activity collector's runtime directory.

## Basic diagnostics

```bash
echo '===== TELEMETRY SERVICES ====='
systemctl is-active ywd-mqtt.service
systemctl is-active ywd-mmdvm-telemetry.service
systemctl is-active ywd-mmdvm-voice.service || true

echo
echo '===== LOOPBACK LISTENER ====='
sudo ss -ltnp | grep 18883 || true

echo
echo '===== TELEMETRY SNAPSHOT ====='
sudo python3 -m json.tool /run/ywd-hotspot-telemetry/telemetry.json 2>/dev/null || true

echo
echo '===== VOICE BRIDGE SNAPSHOT ====='
sudo python3 -m json.tool /run/ywd-hotspot-voice/voice.json 2>/dev/null || true

echo
echo '===== RSSI MAPPING ====='
grep -n 'RSSIMappingFile' /etc/ywd-hotspot/MMDVM-Host.ini || true
cat /etc/ywd-hotspot/mmdvm-hs-rssi.dat 2>/dev/null || true

echo
echo '===== CORE DMR ====='
systemctl is-active ywd-mmdvmhost.service
systemctl is-active ywd-dmrgateway.service
systemctl is-active ywd-dashboard.service

echo
echo '===== FAILURES ====='
systemctl --failed --no-pager
```

Expected broker scope is `127.0.0.1:18883`, not a public/LAN address.

A short `mosquitto_sub` window that receives no message merely means no matching MMDVM event occurred during that window; inspect service/listener state and perform a controlled RF test before calling the bridge broken.

## Relationship to plugins

Telemetry establishes a reusable observation boundary, but plugins still require explicit declared capabilities and never receive raw modem/network ownership merely because telemetry exists. Rich consumers should use a narrow core capability or normalized API rather than opening their own modem/MQTT connection.

Any future RF-control plugin remains a separate architectural problem requiring trusted-core ownership/arbitration, explicit operator intent, safe state capture/restore, and failure recovery.

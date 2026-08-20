# 📡 MMDVM Telemetry

[Docs index](README.md) · [Architecture](ARCHITECTURE.md) · [Display](DISPLAY.md) · [MMDVM Sessions](MMDVM-SESSIONS.md)

YWD-Hotspot keeps a passive structured MMDVM telemetry path as **trusted core infrastructure**. The old `mmdvm-live-telemetry` proof plugin has been retired; the telemetry bridge itself remains because dashboard instrumentation, normalized session state, diagnostics, and future capability-gated consumers use it independently of that plugin.

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

The structured JSON topic is:

```text
ywd-mmdvm/json
```

The passive DMR voice tap uses a separate topic so per-frame voice data does not pass through the low-rate telemetry snapshot path.

## Loopback broker boundary

The YWD listener is intentionally local-only:

```text
listener 18883 127.0.0.1
allow_anonymous true
persistence false
```

There is no YWD LAN/WAN telemetry listener. `ywd-mqtt.service` owns this dedicated loopback broker instance/configuration.

If the OS already has Mosquitto for another purpose, YWD does not use package removal as a cleanup shortcut for shared software.

## Trusted bridge

`ywd-mmdvm-telemetry.service` runs as the restricted `ywd-hotspot` account with only the network access needed to reach loopback.

The bridge accepts known structured MMDVM message families rather than copying arbitrary MQTT payloads into browser/plugin-visible state.

Runtime snapshot:

```text
/run/ywd-hotspot-telemetry/telemetry.json
```

The file lives under tmpfs runtime state, is recreated at boot, and contains no plugin configuration or reusable credentials.

## RSSI normalization

Supported MMDVM_HS ADF7021 firmware may report the positive magnitude of received dBm in its RSSI bytes. YWD generates the matching normalization map:

```text
0 0
255 -255
```

and configures MMDVM-Host to use it through:

```ini
[Modem]
RSSIMappingFile=/etc/ywd-hotspot/mmdvm-hs-rssi.dat
```

This converts values such as `62` to approximately `-62 dBm`. It does not invent RSSI when firmware does not provide RSSI data and is not a replacement for a board-specific calibrated RF measurement system.

## DMR/session information

Trusted telemetry/session normalization can expose bounded state such as:

- current MMDVM mode;
- latest RSSI and BER samples with age/source semantics;
- DMR source/destination IDs;
- group/private status;
- timeslot;
- RF vs network direction;
- call/session start/end/lost/timeout state;
- completed duration/BER/loss/RSSI summaries when supplied upstream;
- bridge heartbeat/message/error counters.

RSSI is an RF receive measurement. Network-originated audio does not magically acquire a new local RF RSSI sample, so consumers must respect sample age and direction.

See **[MMDVM-SESSIONS.md](MMDVM-SESSIONS.md)** for normalized call/session semantics.

## Dashboard relationship

The dashboard does **not** depend on an MMDVM telemetry plugin. It reads trusted core status/telemetry/session state directly.

This is why removing the old `mmdvm-live-telemetry` plugin did not remove or disable:

```text
ywd-mqtt.service
ywd-mmdvm-telemetry.service
```

The old plugin-specific presentation/polling code is a separate cleanup candidate after the current pre-main hardening build is physically validated.

## Update / boot behavior

Telemetry runtime is provisioned as passive side infrastructure. Failure to activate it should be reported diagnostically but must not be treated as permission to break otherwise healthy DMR operation.

Normal application updates preserve RF enabled/active policy while reinstalling trusted runtime units. Candidate validation now treats telemetry as a capability set: if telemetry markers are present in a candidate, the broker config, bridge/session/runtime helpers, and systemd units must be present coherently regardless of branch name.

## Basic diagnostics

```bash
echo '===== TELEMETRY SERVICES ====='
systemctl is-active ywd-mqtt.service
systemctl is-active ywd-mmdvm-telemetry.service

echo
echo '===== LOOPBACK LISTENER ====='
sudo ss -ltnp | grep 18883 || true

echo
echo '===== SNAPSHOT ====='
sudo python3 -m json.tool /run/ywd-hotspot-telemetry/telemetry.json 2>/dev/null || true

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

Expected listener scope is `127.0.0.1:18883`, not a public/LAN address.

## Relationship to plugins

Telemetry established a reusable observation boundary, but current plugins still require explicit declared capabilities and do not receive raw modem/network ownership. A future telemetry-oriented plugin can consume a narrow core capability rather than opening its own MQTT or modem connection.

Any future RF-control plugin remains a separate architectural problem requiring trusted-core ownership/arbitration, explicit operator intent, safe state capture/restore, and failure recovery.

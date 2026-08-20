# 🧱 YWD-Hotspot Architecture

[← Docs index](README.md) · [Project README](../README.md) · [Plugins](PLUGINS.md) · [Passive Voice](DMR-VOICE.md) · [Security](../SECURITY.md)

---

YWD-Hotspot keeps the actual DMR transport path deliberately small and separates presentation/admin/plugin work from RF ownership.

## RF path

```text
DMR radio
   │
   ▼
MMDVM HAT
   │
   ▼
MMDVM-Host  ───── passive copies only ─────► YWD telemetry / voice observers
   │
   ▼
DMRGateway
   │
   ▼
BrandMeister
```

**MMDVM-Host remains the sole modem/RF owner.** Dashboard, OLED, telemetry, plugin, browser audio, and update code do not independently open the modem serial device or gain RF TX authority.

## Simplex and duplex configuration

Canonical config schema 6 models radio mode explicitly:

```text
radio.mode
radio.frequency_hz
radio.rx_frequency_hz
radio.tx_frequency_hz
```

Simplex uses one RF frequency and the hotspot's simplex slot behavior. Duplex uses separate hotspot RX/TX frequencies and supports TS1 + TS2.

Generated MMDVM-Host/DMRGateway INIs are outputs, never the source of truth. Older configs migrate conservatively and do not silently switch modes.

## Core side services

Representative services:

| Service | Role |
|---|---|
| `ywd-activity.service` | bounded activity / Last Heard state |
| `ywd-dashboard.service` | stdlib HTTP dashboard/API; routes validated writes through trusted admin helpers |
| `ywd-headless-oled.service` | authoritative OLED owner on YWD-Hotspot OS |
| `ywd-oled.service` | generic/non-OS OLED unit; disabled on YWD-Hotspot OS |
| `ywd-update.service` | detached one-shot application update job |
| `ywd-dmrid-update.timer` | periodic RadioID refresh |
| `ywd-mqtt.service` | loopback-only Mosquitto used by trusted MMDVM observation paths |
| `ywd-mmdvm-telemetry.service` | passive structured telemetry snapshot bridge |
| `ywd-mmdvm-voice.service` | bounded passive DMR voice-frame bridge |
| `ywd-mmdvm-voice-build.service` | separately scheduled/low-priority preparation of the optional patched MMDVM binary |
| `ywd-plugin@.service` | shared restricted runner for installed service plugins |

Side-service failure must not become permission to change RF state.

## Passive telemetry

```text
MMDVM-Host structured MQTT
        │
        ▼
loopback YWD Mosquitto
        │
        ▼
trusted telemetry bridge
        │
        ▼
/run/ywd-hotspot-telemetry/telemetry.json
        │
        ├─ dashboard instrumentation
        ├─ normalized session state
        └─ capability-gated plugin consumers
```

The old MMDVM Live Telemetry **plugin** is retired; telemetry itself remains trusted core infrastructure.

## Passive DMR voice

The optional MMDVM voice patch mirrors accepted DMR voice frames to a separate loopback-only topic while normal MMDVM processing continues unchanged.

```text
MMDVM-Host
   │ accepted voice-frame copy
   ▼
ywd-mmdvm/voice
   │
   ▼
trusted voice bridge
   │ bounded ring / sanitized frame API
   ▼
read:dmr-voice Plugin UI capability
   │
   ▼
RX Monitor browser iframe
   └─ FEC / AMBE recovery / PCM playback on browser device
```

The Pi does not perform AMBE-to-PCM playback. Browser decoding keeps the original Pi Zero as the performance budget.

See **[DMR-VOICE.md](DMR-VOICE.md)**.

## Plugin architecture

Plugin package source, installation, activation, and runtime are separate concepts:

```text
AVAILABLE → INSTALLED → ENABLED → ACTIVE
```

Plugin kinds:

```text
declarative   trusted core interprets metadata/config; no plugin executable code
service       signed Python entrypoint through ywd-plugin@.service sandbox
ui            signed JS/CSS inside isolated dashboard iframe
```

Uploaded executable service/UI packages require a trusted Ed25519 signature. A valid signature proves publisher provenance; it does not grant arbitrary system privilege.

Current plugin rules prohibit direct modem serial ownership, independent MMDVM instances, arbitrary sudo, broad device access, arbitrary network sockets, and RF TX authority.

### Plugin UI isolation

UI plugin code is never injected into the trusted dashboard DOM. Core creates a sandboxed iframe with a restrictive CSP/Permissions Policy and exposes only declared capability methods through a trusted MessageChannel bridge.

RX Monitor's `read:dmr-voice` access is one such explicit capability.

### Transactional plugin package updates

Uploading a same-ID `.ywdplugin` can be classified as update/reinstall/downgrade/replacement. Review is non-mutating. A confirmed replacement re-verifies the archive, preserves configuration/data and prior installed/enabled intent where valid, performs an atomic package swap, and rolls back the prior package/state on failure.

Plugin kind and signing provenance cannot silently change under an ordinary update.

## Privilege boundary

The dashboard runs as the restricted `ywd-hotspot` user.

Privileged browser operations are funneled through:

```text
/usr/local/libexec/ywd-hotspot-admin
```

and the restricted policy:

```text
/etc/sudoers.d/ywd-hotspot
```

The dispatcher accepts named operations rather than arbitrary shell text, branch names, URLs, or filesystem paths supplied by browser code.

## Canonical configuration

Source of truth:

```text
/etc/ywd-hotspot/config.json
```

Generated outputs:

```text
/etc/ywd-hotspot/MMDVM-Host.ini
/etc/ywd-hotspot/DMRGateway.ini
```

Configuration flow:

```text
browser / CLI input
        │
        ▼
validate + normalize
        │
        ▼
transactional canonical JSON update
        │
        ▼
regenerate temporary INIs
        │
        ▼
atomic apply / scoped service action
```

Normal configuration history is retained separately for rollback.

## Credential separation

YWD-Hotspot treats these as separate security domains:

1. BrandMeister Hotspot Security password
2. BrandMeister API v2 key
3. local WebUI control password
4. plugin publisher public trust keys
5. plugin publisher **private signing key** — development machine only; never hotspot state

Reusable secrets must not appear in browser-readable config or sanitized support bundles.

## Runtime/state layout

```text
/etc/ywd-hotspot/
  config.json
  MMDVM-Host.ini
  DMRGateway.ini
  bm-api.key
  web-auth.json
  build-info.json
  update-channel
  plugin-state.json
  plugin-packages.json
  plugins/
  plugin-trust.d/

/var/lib/ywd-hotspot/
  DMRIds.dat
  lastheard.json
  calibration.json
  geocode-cache.json
  talkgroup-directory.json
  update-status.json
  config-history.json
  audit.json
  plugin-packages/
  plugins/
  private/

/run/ywd-hotspot/
  activity.json

/run/ywd-hotspot-telemetry/
  telemetry.json

/run/ywd-hotspot-voice/
  voice.json

/var/backups/ywd-hotspot/
```

## GitHub source vs deployed runtime

```text
/opt/ywd-hotspot/repo    root-owned managed Git checkout
/opt/ywd-hotspot/app     deployed application copy; no .git
```

Update flow:

```text
GitHub fetch
   ↓
resolve target commit
   ↓
stage candidate outside live app
   ↓
capability + syntax validation
   ↓
protected backup / plugin quiesce
   ↓
transactional UPDATE.sh
   ↓
restore prior RF + valid plugin intent
   ↓
advance managed checkout after success
```

Candidate validation is based on runtime markers in the candidate itself, not only its branch name. A promoted plugin-capable `dev`/`main` therefore receives the same plugin/voice coherence checks as `dev-plugins`.

## WebUI layers

The browser remains plain same-origin HTML/CSS/JS:

```text
style.css                    base theme
app-core.js                  established dashboard behavior
talkgroups.js                TS-aware Talkgroup Manager
ui-polish.css/js             common modal / interaction polish
update.css/js                software update controls
update-progress.js           stage-driven progress modal
instrumentation.css/js       optional live RF gauges/traces
plugin-manager*.js/css       trusted package/lifecycle UI
plugin-ui-host.js            trusted iframe/capability host
plugin-ui-runtime.js         isolated plugin-side bridge runtime
app.js                       loader/integration layer
```

No Node.js runtime or SPA framework is required on the hotspot.

## OLED ownership invariant

YWD-Hotspot OS must have exactly one process owning the physical SSD1306:

```text
YWD-Hotspot OS   → ywd-headless-oled.service
Generic install  → ywd-oled.service
```

OLED failure is passive presentation failure and must not interrupt DMR.

## Pi Zero performance budget

Prefer Python stdlib, bounded cached state, small long-running services, plain browser JS/CSS/SVG, and browser-side expensive rendering/decoding.

Avoid turning a Pi Zero into infrastructure cosplay: no required Docker, Redis, SQL server, Node runtime, or heavyweight frontend framework.

## RF safety invariant

Install, update, config apply/revert, plugin lifecycle, dashboard/OLED restart, passive telemetry, passive voice monitoring, and browser audio are **never permission to unexpectedly start or retune the transmitter**.

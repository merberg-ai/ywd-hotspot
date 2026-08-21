# 🧱 YWD-Hotspot Architecture

[← Docs index](README.md) · [Plugins](PLUGINS.md) · [Passive Voice](DMR-VOICE.md) · [Security](../SECURITY.md)

YWD-Hotspot keeps the DMR transport path small and separates presentation/admin/plugin work from RF ownership.

## RF path

```text
DMR radio
   │
   ▼
MMDVM HAT
   │
   ▼
MMDVM-Host  ───── passive copies only ─────► trusted YWD observers
   │
   ▼
DMRGateway
   │
   ▼
BrandMeister
```

**MMDVM-Host remains the sole modem/RF owner.** Dashboard, OLED, telemetry, plugins, browser audio and updater code do not independently own `/dev/serial0` or RF TX.

## MMDVM runtime layer

`0.2.0-rc1` makes the radio host runtime explicit:

```text
ywd-extended
  pinned upstream MMDVM-Host
  + hash-verified YWD extension patch
  + passive-dmr-voice/plugin-rx-monitor capabilities

upstream
  exact same pinned upstream MMDVM-Host
  no YWD extensions
```

Persistent runtime/provenance:

```text
/etc/ywd-hotspot/mmdvm-runtime.json
/etc/ywd-hotspot/mmdvm-build.json
```

Stock and Extended use separate compile-cache identities. Normal app updates preserve this layer and do not silently rebuild/switch it.

## Simplex / duplex

Canonical schema models:

```text
radio.mode
radio.frequency_hz
radio.rx_frequency_hz
radio.tx_frequency_hz
```

Simplex uses one RF frequency. Duplex uses separate hotspot RX/TX and TS1/TS2. Generated INIs remain outputs of canonical JSON, never source of truth.

## Core services

| Service | Role |
|---|---|
| `ywd-activity.service` | bounded activity / Last Heard state |
| `ywd-dashboard.service` | trusted dashboard/API as restricted user |
| `ywd-headless-oled.service` | authoritative OLED owner in YWD-Hotspot OS |
| `ywd-update.service` | detached application update job |
| `ywd-dmrid-update.timer` | RadioID refresh |
| `ywd-mqtt.service` | loopback broker for trusted observers |
| `ywd-mmdvm-telemetry.service` | passive structured telemetry bridge |
| `ywd-mmdvm-voice.service` | bounded passive voice bridge when capability exists |
| `ywd-plugin@.service` | shared restricted service-plugin runner |

Side-service failure is not permission to alter RF state.

## Passive voice path

Available with YWD Extended:

```text
MMDVM-Host
   │ accepted voice-frame copy
   ▼
ywd-mmdvm/voice (loopback)
   ▼
trusted voice bridge
   ▼
read:dmr-voice capability
   ▼
RX Monitor iframe
   └─ browser FEC / AMBE recovery / PCM playback
```

The Pi does not perform AMBE speech synthesis.

## Plugin architecture

```text
AVAILABLE → INSTALLED → ENABLED → ACTIVE
```

Kinds:

```text
declarative   trusted core interprets metadata/config
service       signed Python through hardened shared systemd sandbox
ui            signed JS/CSS in isolated iframe
```

Plugins can declare trusted dependency/hardware/runtime tokens. MMDVM-specific requirements are resolved from `mmdvm-runtime.json`; incompatible plugins are blocked at install/enable/start. Requirement satisfaction never grants modem ownership.

Current MMDVM tokens include:

```text
mmdvm-ywd-extended
mmdvm-extension-api-2
mmdvm-cap-passive-dmr-voice
```

## Privilege boundary

The dashboard runs as `ywd-hotspot`. Privileged actions pass through the narrow admin dispatcher and restricted sudoers policy; browser/plugin input never becomes arbitrary root shell text.

## Canonical config

```text
/etc/ywd-hotspot/config.json
      ↓ validate/normalize
/etc/ywd-hotspot/MMDVM-Host.ini
/etc/ywd-hotspot/DMRGateway.ini
      ↓ scoped apply
services
```

Secrets and plugin state are stored separately from browser-readable public configuration.

## Runtime layout

Important `/etc/ywd-hotspot` state includes:

```text
config.json
MMDVM-Host.ini
DMRGateway.ini
bm-api.key
web-auth.json
build-info.json
update-channel
mmdvm-runtime.json
mmdvm-build.json
plugin-state.json
plugin-packages.json
plugins/
plugin-trust.d/
```

Transient telemetry/voice/activity state remains under `/run`; user/plugin data and protected state remain under `/var/lib/ywd-hotspot`; rollback backups remain under `/var/backups/ywd-hotspot`.

## Git-managed application layer

```text
/opt/ywd-hotspot/repo    managed source
/opt/ywd-hotspot/app     deployed runtime
```

Update flow:

```text
fetch/resolve target
  ↓
stage outside live app
  ↓
capability + syntax validation
  ↓
backup / plugin quiesce
  ↓
transactional application replacement
  ↓
restore prior valid plugin + RF policy
  ↓
advance managed source
```

MMDVM runtime identity is intentionally separate from application Git identity.

## Public factory image

The release builder adds a second boundary: public `.img.xz` artifacts must contain no operator personalization and no builder SSH authorized key. They boot into setup AP + OLED-code onboarding with RF off. The exact accepted image is the exact image published.

## OLED / Pi Zero invariants

YWD-Hotspot OS uses `ywd-headless-oled.service` as the single physical OLED owner. The original Pi Zero W remains the performance budget: prefer stdlib services, bounded state and browser-side expensive UI/audio work over heavyweight infrastructure.

## RF safety invariant

Install, update, restore, plugin lifecycle, MMDVM runtime metadata migration, dashboard/OLED restart, telemetry and passive voice observation are **never permission to unexpectedly start or retune RF**.

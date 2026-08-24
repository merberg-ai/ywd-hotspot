# 🧱 YWD-Hotspot Architecture

[← Docs index](README.md) · [SSH / SFTP](SSH.md) · [Plugins](PLUGINS.md) · [Passive Voice](DMR-VOICE.md) · [External Vocoder](VOCODER.md) · [Security](../SECURITY.md)

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

**MMDVM-Host remains the sole modem/RF owner.** Dashboard, OLED, telemetry, plugins, RX audio, SSH and updater code do not independently own `/dev/serial0` or RF TX.

## MMDVM runtime layer

The radio host runtime is explicit:

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
| `ywd-dashboard.service` | trusted dashboard/API as restricted service user |
| `ywd-headless-oled.service` | authoritative OLED owner in YWD-Hotspot OS |
| `ywd-update.service` | detached application update job |
| `ywd-dmrid-update.timer` | RadioID refresh |
| `ywd-mqtt.service` | dedicated loopback broker for trusted MMDVM observers |
| `ywd-mmdvm-telemetry.service` | passive structured telemetry/session bridge |
| `ywd-mmdvm-voice.service` | demand-gated passive voice bridge when capability exists |
| `ywd-plugin@.service` | shared restricted service-plugin runner |
| `ssh.service` | optional OS maintenance access; factory OFF and dashboard-managed |

The separately installed vocoder uses its own socket/service units:

```text
ywd-vocoder-mbelib.socket
ywd-vocoder-mbelib.service
```

Those units are not part of the RF ownership path. Side-service failure is not permission to alter RF state.

## Passive telemetry / voice paths

Low-rate structured telemetry:

```text
MMDVM-Host
  -> ywd-mmdvm/json on 127.0.0.1:18883
  -> trusted telemetry/session bridge
  -> /run/ywd-hotspot-telemetry/telemetry.json
  -> dashboard / diagnostics / trusted consumers
```

YWD Extended Phase 3J passive voice:

```text
MMDVM-Host
  -> ywd-mmdvm/voice on loopback
  -> trusted voice bridge
       ├─ /run/ywd-hotspot-voice/voice.json
       │    bounded diagnostics/capture ring only
       │
       └─ nonblocking AF_UNIX datagram live path
            /run/ywd-hotspot-voice/live-audio.sock
                  ↓
          trusted dashboard audio streamer
          DMR recovery / FEC
          10 AMBE frames / 200 ms
                  ↓
          /run/ywd-vocoder.sock
          YWD Vocoder Protocol v1
                  ↓
          separately installed mbelib backend
                  ↓
          trusted NDJSON PCM stream
                  ↓
          sandboxed RX Monitor iframe
          Web Audio reservoir/playout only
```

The JSON voice ring is no longer the live speech transport. It remains a bounded diagnostics/capture path. The direct live sender is nonblocking so MMDVM-Host and the normal RF path are never backpressured by audio playback.

Current selected Phase 3J tuning on `dev-plugins`:

```text
live burst tail          12 DMR bursts (~720 ms)
vocoder request timeout  400 ms
diagnostic ring          32 frames / 1 Hz snapshots
browser reservoir target 400 ms
browser emergency depth  700 ms
browser correction       gentle +/-1%
```

The external vocoder is separately installed and socket-activated. YWD-Hotspot core enforces the conservative service scheduling policy:

```text
Nice=0
CPUWeight=200
```

No negative nice or realtime scheduling is used. See **[VOCODER.md](VOCODER.md)**.

RSSI is optional modem-firmware data. The telemetry/voice paths preserve real RSSI when supplied and leave it unavailable when the HAT firmware reports no usable value; BER is never converted into guessed dBm.

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
mmdvm-cap-demand-gated-dmr-voice
```

RX Monitor additionally declares the trusted vocoder capability, but the plugin does not download/install the external backend itself. Core authorizes the bridge and the operator separately installs the local Protocol v1 decoder.

## Web privilege boundary

The dashboard runs as restricted `ywd-hotspot`. Privileged actions pass through the narrow admin dispatcher and restricted sudoers policy; browser/plugin input never becomes arbitrary root shell text.

Examples of privileged core-owned actions include RF service changes, configuration apply, updates, backup/restore, DMR-ID maintenance and the bounded SSH access/key operations. Those actions are explicit APIs, not a generic command runner.

## External vocoder boundary

YWD Vocoder Protocol v1 is a narrow local AF_UNIX request/response boundary. Current RX Monitor core recovers AMBE49 frames before crossing it; the backend returns fixed-format 8 kHz mono signed 16-bit PCM.

Core ships the protocol/client and the scheduling policy for the known external service, but does not bundle mbelib source/binaries or a browser AMBE decoder. The backend remains separately distributed and may be absent when RX audio is not needed.

## SSH boundary

The public appliance includes OpenSSH but removes factory server host keys and disables `ssh.service` before publication.

After first boot, authenticated dashboard controls may:

- create an Ed25519 client login key for an existing normal local user (normally `ywd` on YWD-Hotspot OS);
- install only its public half into that user's `authorized_keys`;
- return the private/public pair once;
- enable/disable `ssh.service` and boot activation;
- generate unique server host keys on first enable;
- export server identity keys for advanced recovery.

YWD always enforces public-key-only authentication with SSH passwords and root login disabled.

On YWD-Hotspot OS, `ywd` has passwordless sudo, so an authorized SSH key for that account is an administrator credential. This is why SSH remains factory OFF and operator-controlled.

See **[SSH.md](SSH.md)**.

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

The external vocoder's socket is transient under `/run/ywd-vocoder.sock`; its build/source tree and package state are deliberately outside canonical hotspot JSON because the decoder is separately installed.

SSH state is intentionally native OS state under `/etc/ssh` and the selected user's home directory rather than part of canonical hotspot JSON.

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

MMDVM runtime identity is intentionally separate from application Git identity. The separately installed vocoder is also intentionally outside application Git deployment and should be verified independently after a bare-metal rebuild.

## Public factory image

Public `.img.xz` artifacts contain no operator personalization, no builder SSH authorized key, no reusable SSH server identity and no RF autostart. They boot into setup AP + OLED-code onboarding with RF/SSH off.

## OLED / Pi Zero invariants

YWD-Hotspot OS uses `ywd-headless-oled.service` as the single physical OLED owner. The original Pi Zero W remains the performance budget: prefer stdlib services, bounded state, direct local IPC, demand-driven optional workers, and browser-side presentation over heavyweight infrastructure.

## RF safety invariant

Install, update, restore, plugin lifecycle, SSH lifecycle, MMDVM runtime metadata migration, dashboard/OLED restart, telemetry, passive voice observation and external vocoder lifecycle are **never permission to unexpectedly start or retune RF**.
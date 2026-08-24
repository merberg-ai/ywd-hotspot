# 🧩 YWD-Hotspot Plugin Framework

[← Docs index](README.md) · [Plugin Packages](PLUGIN-PACKAGES.md) · [Plugin UI](PLUGIN-UI.md) · [DMR Voice](DMR-VOICE.md) · [External Vocoder](VOCODER.md)

YWD-Hotspot core is authoritative for package verification, lifecycle state, service sandboxing, browser isolation, updater integration, dependency/capability checks, and RF ownership. Standalone plugin source/examples live in `merberg-ai/ywd-hotspot-plugins`.

## Core safety rules

- Plugin Manager is trusted core, not a plugin.
- Upload/verification does not enable a package.
- Installation and activation are separate operator decisions.
- Executable service/UI packages require a trusted Ed25519 signature.
- No plugin receives arbitrary sudo.
- No plugin supplies its own systemd unit.
- No plugin independently owns `/dev/serial0` or starts MMDVM-Host.
- No current plugin API grants RF TX authority.
- Plugin config/data remains separate from canonical hotspot configuration.
- Application updates quiesce/restore only previously valid plugin intent.
- Package updates are explicit transactional replacements with rollback.

## Lifecycle

```text
AVAILABLE → INSTALLED → ENABLED → ACTIVE
```

Persistent state remains split between package registration, enable intent, per-plugin config and plugin-owned data.

## Plugin kinds

### Declarative

Trusted core interprets data/config; no plugin Python/JavaScript executes.

### Sandboxed service

Signed Python executes only through the shared hardened `ywd-plugin@.service` sandbox.

### Browser UI

Signed JS/CSS runs in a sandboxed iframe. Core exposes only declared MessageChannel capabilities such as `read:dmr-voice` and the trusted streamed-audio bridge used by RX Monitor.

## Requirement checks

Dependencies and hardware are declarative tokens interpreted by trusted core. Packages cannot supply arbitrary `apt`, `pip`, shell, download or hardware-probe commands.

General dependency examples:

```text
python3
systemd
journalctl
mmdvm-host
mosquitto-broker
mosquitto-client
```

Hardware examples:

```text
mmdvm-serial
oled-i2c
```

### MMDVM runtime requirements

Current YWD Extended requirement tokens include:

```text
mmdvm-ywd-extended
mmdvm-extension-api-2
mmdvm-cap-passive-dmr-voice
mmdvm-cap-demand-gated-dmr-voice
```

These are checked against `/etc/ywd-hotspot/mmdvm-runtime.json` during package installation and again when enabling/starting applicable plugins.

A passive RX plugin can declare runtime requirements for the YWD Extended passive-voice capability. On a Stock Upstream hotspot the package remains unavailable for activation with a readable missing-requirement result. A plugin **cannot** patch/rebuild/switch MMDVM-Host by itself.

YWD Extended is the default/recommended runtime, but Stock Upstream remains a supported operator choice.

## RX Monitor Phase 3J architecture

RX Monitor demonstrates the intended rich-plugin boundary:

```text
MMDVM-Host (sole modem owner)
  → trusted loopback passive voice tap
  → trusted voice bridge
       ├─ bounded JSON diagnostics ring
       └─ direct nonblocking AF_UNIX live-audio datagrams
  → trusted DMR recovery/FEC + 10-frame/200 ms batching
  → separately installed YWD Vocoder Protocol v1 backend
  → one trusted NDJSON PCM stream
  → isolated browser plugin / Web Audio playout
```

The plugin receives PCM for live speech. It contains no mbelib source/binary, AMBE Wasm decoder, direct modem serial access, direct MQTT access, broad network access, direct vocoder-socket access, or RF-TX authority.

Current selected Phase 3J tuning on `dev`:

```text
core live burst tail     12 DMR bursts (~720 ms)
core decode timeout      400 ms
browser target reservoir 400 ms
browser emergency depth  700 ms
browser correction       gentle +/-1%
external service policy  Nice=0 / CPUWeight=200
```

The external vocoder is not a plugin dependency that the package downloads or installs itself. It is an operator-installed local backend documented in **[VOCODER.md](VOCODER.md)**. Core owns the known service's conservative scheduling drop-in; the decoder remains separately distributed.

## Package lifecycle and updates

New package:

```text
UPLOAD → verify/review → INSTALL → ENABLE → ACTIVE
```

Same-ID updates preserve config/data and prior valid intent, reverify the candidate, quiesce runtime, atomically swap source, revalidate, restore valid prior state, and roll back on failure.

Kind/provenance/capability changes cannot silently bypass signature or sandbox requirements.

## Application updates

Before a plugin-capable YWD application update, core captures plugin state/service intent and makes plugin services inert. After the new candidate validates, only packages that still satisfy validation and runtime requirements are eligible for restoration.

Candidate validation is capability-based rather than branch-name-based. The current gate also requires the complete streamed RX-audio/vocoder payload and its dashboard wrapper integration before a candidate can touch live services.

The optional passive voice bridge is demand-gated by aggregate plugin capability demand. Normal application updates also preserve/restart the bridge when it was active so updated bridge code is not left behind an old Python process.

## Backup/restore

Protected `.ywdsettings` backups may preserve activation/registration intent, plugin configuration, and trusted publisher **public** keys. Uploaded executable package code is not silently embedded/fetched during restore.

Private signing keys never belong in Git, a backup, or the hotspot.

The separately installed external vocoder backend is not silently embedded in `.ywdsettings`; reinstall/verify it independently after a bare-metal rebuild when RX audio is desired.

## RF ownership remains out of scope

A valid signature or satisfied MMDVM capability is not permission to transmit. Any future plugin that needs RF-mode ownership would require a separate trusted-core arbitration design with explicit operator intent, single ownership, rollback and failure recovery.

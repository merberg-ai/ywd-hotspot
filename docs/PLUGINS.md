# 🧩 YWD-Hotspot Plugin Framework

[← Docs index](README.md) · [Plugin Packages](PLUGIN-PACKAGES.md) · [Plugin UI](PLUGIN-UI.md) · [Architecture](ARCHITECTURE.md)

YWD-Hotspot core is authoritative for plugin API contracts, package verification, lifecycle state, service sandboxing, browser isolation, updater integration, and RF ownership rules. Standalone plugin source/examples live in the companion repository:

```text
merberg-ai/ywd-hotspot-plugins
```

The framework is now part of the integrated development baseline rather than a branch-only proof feature.

## Core safety rules

- Plugin Manager is trusted YWD-Hotspot core, not a plugin.
- Plugin support can be globally disabled.
- Uploading/verifying a package does not enable it.
- Installation and activation are separate operator decisions.
- Service/UI executable code requires a trusted Ed25519 signature.
- Uploaded packages cannot self-claim YWD's `first-party` trust label.
- No plugin receives arbitrary sudo.
- No plugin supplies its own systemd unit.
- No plugin independently owns `/dev/serial0` or starts a competing MMDVM instance.
- Current plugin APIs do not grant RF TX authority.
- Plugin config/data is separate from canonical hotspot configuration.
- Application updates quiesce service plugins and restore only previously valid operator intent.
- Package updates are explicit transactions with rollback rather than blind directory overwrite.

## State model

Source, registration, activation, and effective runtime are intentionally separate:

```text
AVAILABLE
    package source is discoverable

INSTALLED
    trusted core registered it for use

ENABLED
    operator requested activation

ACTIVE
    it is effectively active now
```

Persistent state is separated too:

```text
/etc/ywd-hotspot/plugin-state.json
    master + per-plugin activation intent

/etc/ywd-hotspot/plugin-packages.json
    installation/registration intent

/etc/ywd-hotspot/plugins/<id>.json
    per-plugin configuration

/var/lib/ywd-hotspot/plugins/<id>/
    plugin-owned data/runtime path

/var/lib/ywd-hotspot/plugin-packages/<id>/
    persistent uploaded package source

/etc/ywd-hotspot/plugin-trust.d/<key-id>.pem
    trusted publisher PUBLIC keys
```

Private signing keys never belong in hotspot state.

## Plugin kinds

### Declarative

Data/config package interpreted by trusted core. No plugin Python or browser JavaScript executes.

### Sandboxed service

Signed Python entrypoint executed only through the shared hardened unit:

```text
systemd/ywd-plugin@.service
  → trusted installed-package validation
  → plugin_service_runner.py
  → validated service.py
```

The sandbox includes a restricted user/group, `NoNewPrivileges`, no Linux capabilities, private devices, strict filesystem protection, restricted address families, and only the plugin's own data path opened for writes.

A service plugin cannot install its own unit.

### Browser UI

Signed browser-side JS/CSS with no Pi-side daemon. It is served only while installed/effectively enabled and runs in a sandboxed iframe without trusted-dashboard DOM access.

The trusted host exposes only declared capability methods through a MessageChannel bridge.

Generic UI operations are intentionally narrow. Feature-specific operations require explicit capabilities such as:

```text
read:dmr-voice
```

## Package lifecycle

New plugin:

```text
UPLOAD
  ↓ verify + review
INSTALL
  ↓
ENABLE
  ↓
ACTIVE
```

Uninstall preserves package source and plugin config/data unless the operator separately chooses destructive removal actions.

## In-place plugin updates

Uploading a package with the same uploaded plugin ID does not require the old disable/uninstall/remove cycle anymore.

The review step classifies the candidate as appropriate:

```text
UPDATE
REINSTALL
DOWNGRADE
REPLACE VERSION
```

The review is non-mutating. For a confirmed replacement, trusted core:

1. re-verifies archive hashes/signature;
2. checks ID/kind/provenance/capability compatibility;
3. records installed/enabled/service state;
4. preserves plugin configuration and data;
5. quiesces runtime where applicable;
6. atomically swaps package source;
7. revalidates the new package/config;
8. restores prior valid activation/runtime intent;
9. rolls back the old package/state on failure.

An ordinary same-plugin update cannot silently turn a UI package into a service package or bypass signature requirements.

## Plugin UI and capability isolation

UI code is never injected into the trusted dashboard DOM. Core creates an iframe with a restrictive CSP and Permissions Policy. The iframe gets no arbitrary same-origin network access and no direct authenticated dashboard API access.

RX Monitor demonstrates the intended rich-plugin direction: trusted core owns passive frame observation and grants only `read:dmr-voice`; AMBE/FEC/audio work stays on the browser device.

## Passive telemetry

MMDVM structured telemetry is trusted core infrastructure:

```text
MMDVM-Host
  → loopback YWD Mosquitto
  → trusted telemetry bridge
  → local sanitized telemetry/session state
```

The old MMDVM Live Telemetry plugin has been retired. Core telemetry remains because dashboard instrumentation/session normalization use it independently of any plugin.

## Requirement checks

Dependency/hardware requirements are declarative tokens interpreted by trusted core. Packages cannot provide custom `apt`, `pip`, `curl | bash`, or hardware-probe commands.

Examples include:

```text
python3
systemd
journalctl
mmdvm-host
mosquitto-broker
mosquitto-client
```

and hardware tokens such as:

```text
mmdvm-serial
oled-i2c
```

## Application-update behavior

Before a plugin-capable YWD application update, trusted core captures plugin state and exact service boot/runtime intent, then makes service plugins inert for replacement. After the new runtime validates, only prior packages that still validate are eligible for restoration.

Candidate validation is based on the plugin/voice/telemetry capabilities present in the candidate tree, not on whether the target branch happens to be named `dev-plugins`.

## Backup / restore

Protected `.ywdsettings` backups can preserve activation intent, registration intent, plugin configuration, and trusted publisher **public** keys.

Uploaded executable package code is not silently embedded/fetched as part of restore. Missing packages must be explicitly supplied again.

See **[BACKUP-RESTORE.md](BACKUP-RESTORE.md)**.

## Publisher signing keys

Trusted public keys live under:

```text
/etc/ywd-hotspot/plugin-trust.d/<key-id>.pem
```

The companion plugin repository provides `PLUGIN-DEV.sh`, which calls the canonical core package builder. Private keys remain outside both Git repositories and outside the hotspot.

## Built-in proof fixtures

`system-info` and `service-heartbeat` were used to prove declarative/service lifecycle behavior. They remain in the source tree temporarily while pre-main cleanup moves validation away from hard-coded proof IDs. They are not architectural dependencies and are candidates for retirement after the current hardening build is physically validated.

## RF ownership remains out of scope

A valid plugin signature is not permission to control the modem. Any future RF-mode plugin work would require a separate trusted-core arbitration design with one RF owner, explicit operator intent, state capture/restore, and failure recovery.

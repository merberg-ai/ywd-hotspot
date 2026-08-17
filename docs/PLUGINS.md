# YWD-Hotspot Plugin Framework

Plugin development lives on the `dev-plugins` branch. The normal `main` / `dev` appliance remains independent from this experimental framework until plugin functionality is deliberately promoted.

## Current checkpoints

| Checkpoint | Meaning |
|---|---|
| `dev-plugins-alpha15.1-known-good` | reboot + application-update lifecycle proven |
| `dev-plugins-alpha16.1-known-good` | package lifecycle/hardware/dependency UI proven |
| `dev-plugins-alpha17.1-known-good` | passive structured MMDVM telemetry + real RSSI/BER proven |
| `dev-plugins-alpha18.1-known-good` | normalized DMR sessions + telemetry updater fix physically proven |
| `0.1.0-alpha18.2-dev` | encrypted migration backup + persistent signed package upload test build |

Alpha18.2 does **not** grant plugins independent RF ownership. The future MMDVM/RF-control design still requires trusted core arbitration rather than a plugin opening `/dev/serial0` or launching a competing MMDVM-Host instance.

## Core rules

- Plugin Manager is trusted YWD-Hotspot core, not a plugin.
- The plugin subsystem is globally disabled by default when no activation state exists.
- Master **OFF** is authoritative: active service plugins are stopped and per-plugin activation is cleared.
- Re-enabling the master switch does not silently reactivate plugins.
- Uploading a package does not install it.
- Installing a package does not enable or start it.
- Uninstalling stops/disables runtime eligibility but preserves config/data.
- Removing package source and removing plugin data are separate destructive operations.
- Plugin configuration never directly edits canonical `/etc/ywd-hotspot/config.json`.
- No plugin gets arbitrary sudo.
- No plugin supplies its own systemd unit.
- Uploaded executable service code requires a trusted Ed25519 signature.
- An uploaded package may not self-claim YWD's `first-party` trust label.
- Current APIs do not permit plugin-owned RF mode/serial ownership.
- Application update and channel-transition safety must quiesce both built-in and persistent uploaded service plugins.

## Package / runtime state model

YWD keeps package source, registration, activation and runtime separate:

```text
AVAILABLE
    package source is discoverable

INSTALLED
    trusted core has registered the package as eligible for use

ENABLED
    operator explicitly requested activation

ACTIVE
    plugin is effectively running now
```

State/config/data remain separate too:

```text
/etc/ywd-hotspot/plugin-state.json
    plugin master + per-plugin activation intent

/etc/ywd-hotspot/plugin-packages.json
    install/registration intent

/etc/ywd-hotspot/plugins/<id>.json
    per-plugin configuration

/var/lib/ywd-hotspot/plugins/<id>/
    plugin-owned writable runtime/data path

/var/lib/ywd-hotspot/plugin-packages/<id>/
    Alpha18.2 persistent uploaded .ywdplugin source

/etc/ywd-hotspot/plugin-trust.d/<key-id>.pem
    trusted Ed25519 publisher public keys
```

The application-owned built-in package catalogs remain:

```text
/opt/ywd-hotspot/app/lib/plugin_packages/
/opt/ywd-hotspot/app/lib/service_plugin_packages/
```

The persistent uploaded catalog is overlaid onto those built-in catalogs at discovery time. Application updates can therefore replace `/opt/ywd-hotspot/app` without deleting operator-uploaded package source.

## Declarative plugins

Declarative/data-only packages contain metadata and a configuration schema interpreted by trusted core. They do not execute plugin Python or inject arbitrary browser JavaScript/CSS.

Typical built-in source:

```text
lib/plugin_packages/<id>/
  plugin.json
  config.schema.json
```

The `system-info` reference plugin demonstrates the declarative provider path.

Alpha18.2 may accept an **unsigned uploaded declarative** `.ywdplugin` package after strict archive/hash/API validation. Its package card reports `UNSIGNED` so the provenance is not confused with a verified publisher.

## Sandboxed service plugins

Service packages contain an approved `service.py` entrypoint and run only through the shared template:

```text
systemd/ywd-plugin@.service
  -> plugin_package_manager.py require-installed <id>
  -> plugin_service_runner.py --check <id>
  -> plugin_service_runner.py <id>
  -> validated service.py
```

The shared sandbox remains restrictive:

- `User=ywd-hotspot`
- `Group=ywd-hotspot`
- `NoNewPrivileges=true`
- empty capability bounding/ambient sets
- `PrivateDevices=true`
- `ProtectSystem=strict`
- `ProtectHome=true`
- protected kernel tunables/modules/cgroups
- namespace/SUID restrictions
- `MemoryDenyWriteExecute=true`
- `RestrictAddressFamilies=AF_UNIX`
- no direct MMDVM device ownership
- only `/var/lib/ywd-hotspot/plugins/<id>` is opened for plugin writes

A service plugin cannot ship a systemd unit. The generic YWD template is the only runtime owner.

### Uploaded executable service policy

Alpha18.2 adds a second trust requirement for WebUI-uploaded executable code:

```text
unsigned uploaded service     -> reject
unknown signing key           -> reject
invalid signature             -> reject
verified trusted Ed25519 key  -> may become AVAILABLE
```

Passing the signature gate still does not install, enable or start the package.

See **[PLUGIN-PACKAGES.md](PLUGIN-PACKAGES.md)** for the archive/signing format and publisher-key workflow.

## `.ywdplugin` upload lifecycle

The locked Plugin Manager now supports:

```text
UPLOAD .YWDPLUGIN
```

A package is staged and validated before it is moved into the persistent catalog. The core checks include:

- compressed/uncompressed limits
- flat safe filenames only
- no symbolic links or directories
- exact SHA-256 file inventory
- package format/version
- plugin ID/API/schema
- dependency/hardware allow lists
- capability allow lists
- uploaded `experimental` trust label
- Ed25519 signature when declared
- mandatory trusted signature for service code
- collision with an already available ID

A successful upload results in an AVAILABLE, uninstalled, disabled package.

### Package actions

**INSTALL** validates requirements, registers the package and explicitly leaves it disabled.

**UNINSTALL** stops/boot-disables a service package, clears activation and registration, while preserving source/config/data.

**REMOVE PACKAGE** exists only for persistent uploaded packages. It requires the plugin to be uninstalled/inactive and physically removes only:

```text
/var/lib/ywd-hotspot/plugin-packages/<id>/
```

Built-in application packages cannot be physically removed through Plugin Manager; application updates own those files.

**REMOVE DATA** remains separate and removes only:

```text
/etc/ywd-hotspot/plugins/<id>.json
/var/lib/ywd-hotspot/plugins/<id>/
```

No package-controlled glob/path is accepted.

## Dependency and hardware checks

Manifest requirements are declarative tokens interpreted by trusted core. Plugins do not execute custom dependency probes or package-manager commands.

Current dependency allow list includes:

```text
python3
systemd
journalctl
mmdvm-host
mosquitto-broker
mosquitto-client
```

Current hardware probes include:

```text
mmdvm-serial -> /dev/serial0
oled-i2c     -> /dev/i2c-1
```

Missing requirements prevent install/enable as appropriate. The framework does not run arbitrary `apt`, `pip`, `curl | bash`, or plugin-provided dependency scripts.

## MMDVM telemetry capability

Alpha17/18 established trusted MMDVM observation infrastructure:

```text
MMDVM-Host structured MQTT JSON
  -> YWD loopback Mosquitto listener 127.0.0.1:18883
  -> trusted ywd-mmdvm-telemetry bridge
  -> sanitized /run/ywd-hotspot-telemetry/telemetry.json
  -> normalized DMR session model
  -> sandboxed mmdvm-live-telemetry plugin
```

The current reference telemetry plugin has observational capabilities only. It does not own RF, serial or Internet sockets.

Alpha18 adds normalized bounded `active`, `last` and `recent` DMR sessions so future plugins do not need to scrape journals or guess sparse start/end identity.

See **[TELEMETRY.md](TELEMETRY.md)** and **[MMDVM-SESSIONS.md](MMDVM-SESSIONS.md)**.

## Update safety

Before a plugin-aware application update, trusted core captures:

- master activation state
- per-plugin activation flags
- exact service active state
- exact service boot-enable state
- built-in service package IDs
- Alpha18.2 persistent uploaded service package IDs

Then it disables/stops plugin services before replacing the application.

After a successful update, the target catalogs are loaded—including persistent uploaded packages when the target supports them—and only previously valid/installed/enabled packages are eligible for restoration. New packages stay disabled.

On rollback, the old app is restored before the captured plugin policy is reconstructed.

When leaving `dev-plugins` for a plugin-free stable branch, plugin services are made inert and the generic plugin/telemetry runtime is removed as appropriate. Persistent uploaded package files may remain on disk as inert operator data rather than being silently destroyed.

## Backup / restore integration

Alpha18.2 `.ywdsettings` backups can preserve:

- plugin master activation intent
- per-plugin activation intent
- package-registration intent
- plugin configurations
- trusted publisher public keys

The backup does not embed uploaded executable package source.

On a fresh OS restore:

- built-in/otherwise available packages can have registration and activation intent restored
- missing uploaded packages are reported
- their configs are preserved
- no code is downloaded automatically
- re-uploading package source remains an explicit operator action

See **[BACKUP-RESTORE.md](BACKUP-RESTORE.md)**.

## Publisher signing keys

Alpha18.2 does not ship an automatically trusted third-party key and does not expose a WebUI button for casually adding executable-code trust.

A trusted publisher public key is installed by the operator/root under:

```text
/etc/ywd-hotspot/plugin-trust.d/<key-id>.pem
```

YWD's package builder can create signed archives using an Ed25519 private key held by the publisher/developer:

```bash
python3 tools/ywdplugin-build.py SOURCE OUTPUT.ywdplugin \
  --sign-key PRIVATE.pem \
  --key-id publisher-key-1 \
  --publisher "Publisher Name"
```

Never store the private key on the hotspot or in the repository.

## RF ownership remains out of scope

Neither a verified signature nor the service sandbox is permission to directly control the MMDVM modem.

The current plugin APIs keep:

```text
rf_mode = false
```

for all supported packages. A future RF-mode/MMDVM integration needs a separate trusted-core arbitration contract with one serial/RF owner, safe capture/restore of the normal DMR state, failure recovery and explicit operator control.

That design should build on the existing plugin lifecycle, signing, telemetry and normalized-session foundation rather than bypass it.

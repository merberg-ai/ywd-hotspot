# YWD-Hotspot Plugin Framework

Plugin integration currently lives on the `dev-plugins` branch. The conservative `main` and unified `dev` lines remain independent until plugin work is deliberately promoted.

External/community plugin source and examples live in the companion repository:

- `merberg-ai/ywd-modem-plugins` — open-source YWD-Hotspot plugin development

The YWD-Hotspot repository remains the canonical source for the plugin API contract, package verifier, sandbox, lifecycle manager, updater integration, and security boundary.

## Current validation status

| Checkpoint / build | Meaning |
|---|---|
| `checkpoint/dev-plugins-alpha15.1-known-good` | reboot + application-update lifecycle proven |
| `checkpoint/dev-plugins-alpha16.1-known-good` | package lifecycle, dependency and hardware UI proven |
| `checkpoint/dev-plugins-alpha17.1-known-good` | passive structured MMDVM telemetry + real RSSI/BER proven |
| `checkpoint/dev-plugins-alpha18.1-known-good` | normalized DMR sessions + telemetry updater fix physically proven |
| `checkpoint/dev-plugins-alpha18.2.4-known-good` | encrypted backup / plugin framework baseline preserved |
| `0.1.0-alpha18.2.15-dev` | real uploaded signed service package exercised end-to-end on the Pi |

The Alpha18.2.15 hardware test successfully exercised:

```text
UPLOAD
  -> VERIFIED / AVAILABLE
  -> INSTALL
  -> ENABLE / ACTIVE
  -> configuration save + service restart
  -> DISABLE
  -> UNINSTALL (configuration preserved)
  -> REMOVE DATA
  -> REMOVE PACKAGE
```

This validated the actual WebUI upload/install/runtime/removal path rather than only synthetic package tests.

## Core rules

- Plugin Manager is trusted YWD-Hotspot core, not a plugin.
- The plugin subsystem is globally disabled by default when activation state is absent.
- Master **OFF** is authoritative: active plugin services stop and per-plugin activation is cleared.
- Re-enabling the master switch never silently reactivates plugins.
- Uploading a package does not install it.
- Installing a package does not enable or start it.
- Uninstalling stops/disables runtime eligibility and preserves config/data.
- Removing package source and removing plugin data are separate destructive actions.
- Plugin configuration never directly edits canonical `/etc/ywd-hotspot/config.json`.
- No plugin gets arbitrary sudo.
- No plugin supplies its own systemd unit.
- Uploaded executable service code requires a trusted Ed25519 signature.
- Uploaded packages cannot self-claim YWD's `first-party` trust label.
- Current plugin APIs do not permit independent RF/serial ownership.
- Application updates quiesce plugin services and restore only previously valid operator state.

## State model

Package source, registration, activation, and runtime are intentionally separate:

```text
AVAILABLE
    package source is discoverable

INSTALLED
    trusted core registered the package for use

ENABLED
    operator explicitly requested activation

ACTIVE
    plugin is effectively running now
```

Persistent state is also separated:

```text
/etc/ywd-hotspot/plugin-state.json
    plugin master + per-plugin activation intent

/etc/ywd-hotspot/plugin-packages.json
    install / registration intent

/etc/ywd-hotspot/plugins/<id>.json
    per-plugin configuration

/var/lib/ywd-hotspot/plugins/<id>/
    plugin-owned writable runtime/data path

/var/lib/ywd-hotspot/plugin-packages/<id>/
    persistent uploaded .ywdplugin source

/etc/ywd-hotspot/plugin-trust.d/<key-id>.pem
    trusted Ed25519 publisher public keys
```

Built-in catalogs remain application-owned:

```text
/opt/ywd-hotspot/app/lib/plugin_packages/
/opt/ywd-hotspot/app/lib/service_plugin_packages/
```

Persistent uploaded packages are overlaid on those catalogs during discovery, allowing application updates to replace `/opt/ywd-hotspot/app` without deleting operator-uploaded package source.

## Declarative plugins

Declarative/data-only packages contain metadata and a configuration schema interpreted by trusted core. They do not execute plugin Python or inject arbitrary browser JavaScript/CSS.

An unsigned uploaded declarative package may be accepted after strict archive/hash/API validation. The Plugin Manager displays `UNSIGNED` so provenance is never confused with a verified publisher.

## Sandboxed service plugins

Service plugins contain an approved `service.py` entrypoint and run only through the shared YWD unit:

```text
systemd/ywd-plugin@.service
  -> installed-package validation
  -> plugin_service_runner.py --check <id>
  -> plugin_service_runner.py <id>
  -> validated service.py
```

The shared sandbox includes:

- `User=ywd-hotspot`
- `Group=ywd-hotspot`
- `NoNewPrivileges=true`
- no Linux capabilities
- `PrivateDevices=true`
- `ProtectSystem=strict`
- protected home/kernel/control-group state
- namespace/SUID restrictions
- `MemoryDenyWriteExecute=true`
- `RestrictAddressFamilies=AF_UNIX`
- no direct MMDVM device ownership
- only the exact plugin data directory is opened for writes

A service plugin cannot install or provide its own systemd unit.

### Uploaded executable-service policy

```text
unsigned uploaded service     -> reject
unknown signing key           -> reject
invalid signature             -> reject
verified trusted Ed25519 key  -> may become AVAILABLE
```

Passing signature verification still does not install, enable, or start a package.

See **[PLUGIN-PACKAGES.md](PLUGIN-PACKAGES.md)** for the archive/signing format.

## Package actions

**INSTALL** validates requirements and registers an AVAILABLE package. It remains disabled.

**ENABLE** explicitly activates an installed valid plugin. Service plugins may then become active through the shared sandbox unit.

**STOP RUNTIME** stops a service only for the current runtime; boot enable state is retained.

**DISABLE** stops the service, disables boot activation, and clears activation intent.

**UNINSTALL** stops/boot-disables service runtime, clears activation/registration, and preserves package source, configuration, and data.

**REMOVE DATA** removes only:

```text
/etc/ywd-hotspot/plugins/<id>.json
/var/lib/ywd-hotspot/plugins/<id>/
```

**REMOVE PACKAGE** exists only for uploaded packages. The package must first be uninstalled and inert. It removes only:

```text
/var/lib/ywd-hotspot/plugin-packages/<id>/
```

No package-controlled glob or arbitrary path is accepted.

## Dependency and hardware checks

Manifest requirements are declarative tokens interpreted by trusted core. Plugins do not execute custom package-manager or hardware-probe commands.

Current dependency tokens include:

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

Missing requirements prevent installation/activation as appropriate. YWD does not run plugin-provided `apt`, `pip`, `curl | bash`, or arbitrary dependency scripts.

## MMDVM telemetry capability

The trusted observation path is:

```text
MMDVM-Host structured MQTT JSON
  -> loopback YWD Mosquitto 127.0.0.1:18883
  -> trusted telemetry bridge
  -> /run/ywd-hotspot-telemetry/telemetry.json
  -> normalized DMR sessions
  -> sandboxed observational plugins
```

Telemetry plugins do not own RF, serial, or broad network sockets. Normalized `active`, `last`, and bounded `recent` session state avoids plugin-side journal scraping and stale identity guessing.

See **[TELEMETRY.md](TELEMETRY.md)** and **[MMDVM-SESSIONS.md](MMDVM-SESSIONS.md)**.

## Update safety

Before a plugin-aware application update, trusted core captures master state, per-plugin activation, exact service runtime/boot state, and built-in/persistent package identities. Plugin services are quiesced before application replacement.

After a successful update, only packages that still validate and were previously installed/enabled are eligible for restoration. Newly discovered packages remain disabled. Rollback restores the previous application before reconstructing plugin runtime policy.

When leaving `dev-plugins` for a plugin-free target, plugin services are made inert. Persistent uploaded package source may remain as inert operator data rather than being silently destroyed.

## Backup / restore

Protected `.ywdsettings` backups can preserve plugin activation intent, package-registration intent, plugin configuration, and trusted publisher public keys.

Uploaded executable package source is **not** embedded in `.ywdsettings`. On a fresh restore, missing packages are reported and must be explicitly re-uploaded. YWD never silently downloads executable plugin code from the Internet.

See **[BACKUP-RESTORE.md](BACKUP-RESTORE.md)**.

## Publisher signing keys

Trusted publisher public keys live under:

```text
/etc/ywd-hotspot/plugin-trust.d/<key-id>.pem
```

Build a signed package with:

```bash
python3 tools/ywdplugin-build.py SOURCE OUTPUT.ywdplugin \
  --sign-key PRIVATE.pem \
  --key-id publisher-key-1 \
  --publisher "Publisher Name"
```

Never store a signing private key on the hotspot or commit it to either repository.

## RF ownership remains out of scope

A verified signature is not permission to control the modem directly. Current supported packages keep `rf_mode = false`.

Future RF-mode work requires a trusted-core arbitration contract with one serial/RF owner, explicit operator control, safe capture/restore of normal DMR state, and failure recovery. It must build on the existing lifecycle/signing/telemetry foundation rather than bypass it.

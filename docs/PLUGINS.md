# YWD-Hotspot Plugin Framework

Plugin integration currently lives on the `dev-plugins` branch. The physically tested Alpha18.2.16 plugin-capable baseline is parked on `dev` as the stable development fallback while new framework work continues on `dev-plugins`. `main` remains conservative/promoted.

External/community plugin source and examples live in the companion repository:

- `merberg-ai/ywd-hotspot-plugins` — open-source YWD-Hotspot plugin development

The YWD-Hotspot repository remains the canonical source for the plugin API contract, package verifier, service sandbox, Plugin UI isolation, lifecycle manager, updater integration, and security boundary.

## Current validation status

| Checkpoint / build | Meaning |
|---|---|
| `checkpoint/dev-plugins-alpha15.1-known-good` | reboot + application-update lifecycle proven |
| `checkpoint/dev-plugins-alpha16.1-known-good` | package lifecycle, dependency and hardware UI proven |
| `checkpoint/dev-plugins-alpha17.1-known-good` | passive structured MMDVM telemetry + real RSSI/BER proven |
| `checkpoint/dev-plugins-alpha18.1-known-good` | normalized DMR sessions + telemetry updater fix physically proven |
| `checkpoint/dev-plugins-alpha18.2.4-known-good` | encrypted backup / plugin framework baseline preserved |
| `0.1.0-alpha18.2.15-dev` | real uploaded signed service package exercised end-to-end on the Pi |
| `checkpoint/dev-alpha18.2.16-known-good` | current stable development baseline physically tested; plugin lifecycle/UI polish working as expected |

Alpha19 introduces **Plugin UI v1** on the experimental `dev-plugins` line. It is intentionally not a known-good checkpoint until its signed UI smoke-test lifecycle is physically validated.

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
- Uploaded service code and browser UI code require a trusted Ed25519 signature.
- Plugin browser code is never injected into the trusted dashboard DOM.
- Uploaded packages cannot self-claim YWD's `first-party` trust label.
- Current plugin APIs do not permit independent RF/serial ownership.
- Application updates quiesce service plugins and restore only previously valid operator intent.

## State model

Package source, registration, activation, and effective activity are intentionally separate:

```text
AVAILABLE
    package source is discoverable

INSTALLED
    trusted core registered the package for use

ENABLED
    operator explicitly requested activation

ACTIVE
    plugin is effectively active now
```

For a service plugin, ACTIVE normally means its shared sandbox unit is running. For a UI-only plugin, ACTIVE means it is valid/installed/effectively enabled; no Pi-side process exists and its iframe is created only while the operator opens its dashboard section.

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

Built-in catalogs remain application-owned. Persistent uploaded packages are overlaid during discovery so application updates can replace `/opt/ywd-hotspot/app` without deleting operator-uploaded source.

## Declarative plugins

Declarative/data-only packages contain metadata and a configuration schema interpreted by trusted core. They execute no plugin Python or browser JavaScript.

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

## Plugin UI v1

Alpha19 adds a distinct signed `kind: "ui"` execution model for rich browser-side plugin interfaces.

A UI plugin:

- has no Pi-side daemon or service entrypoint;
- declares `provider: "browser-ui"` and `ui:section`;
- supplies flat signed `ui.js` and `ui.css` assets;
- receives a dedicated dashboard navigation section only while installed and effectively enabled;
- executes in `sandbox="allow-scripts"` without `allow-same-origin`;
- receives a restrictive frame CSP and Permissions Policy;
- cannot access the trusted dashboard DOM/session/settings or arbitrary YWD APIs;
- communicates only through a narrow trusted `MessageChannel` bridge.

Plugin UI v1 generic bridge operations are deliberately limited to:

```text
plugin.ping
plugin.getState
plugin.getConfig
```

Future feature-specific bridges such as passive DMR voice observation require explicit core capability contracts. They are not implicitly granted by `ui:section`.

See **[PLUGIN-UI.md](PLUGIN-UI.md)** for the complete isolation/lifecycle contract.

## Uploaded executable-code policy

```text
unsigned uploaded declarative       -> allowed, visibly UNSIGNED
unsigned uploaded service/UI code   -> reject
unknown signing key                 -> reject
invalid signature                   -> reject
verified trusted Ed25519 key        -> may become AVAILABLE
```

Passing signature verification still does not install, enable, or activate a package.

See **[PLUGIN-PACKAGES.md](PLUGIN-PACKAGES.md)** for archive/signing details.

## Package actions

**INSTALL** validates requirements and registers an AVAILABLE package. It remains disabled.

**ENABLE** explicitly activates an installed valid plugin. Service plugins may start through the shared sandbox unit; UI-only plugins become eligible for their dashboard section without creating a Pi process.

**STOP RUNTIME** applies to service plugins and stops only the current service runtime; boot enable state is retained.

**DISABLE** stops a service where applicable and clears activation intent. UI sections are removed immediately when their plugin is no longer effectively enabled.

**UNINSTALL** stops/boot-disables service runtime where applicable, clears activation/registration, and preserves package source, configuration, and data.

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

Before a plugin-aware application update, trusted core captures master state, per-plugin activation, exact service runtime/boot state, and package identities. Service plugins are quiesced before application replacement.

After a successful update, only packages that still validate and were previously enabled are eligible for restoration. UI activation intent participates in the same validation but has no Pi-side process to stop or restore. Newly discovered packages remain disabled.

When leaving plugin-capable development for a plugin-free target, service plugins are made inert and plugin activation is cleared. Persistent uploaded package source may remain as inert operator data rather than being silently destroyed.

## Backup / restore

Protected `.ywdsettings` backups can preserve plugin activation intent, package-registration intent, plugin configuration, and trusted publisher public keys.

Uploaded executable package source is **not** embedded in `.ywdsettings`. On a fresh restore, missing packages are reported and must be explicitly re-uploaded. YWD never silently downloads executable plugin code from the Internet.

See **[BACKUP-RESTORE.md](BACKUP-RESTORE.md)**.

## Publisher signing keys

Trusted publisher public keys live under:

```text
/etc/ywd-hotspot/plugin-trust.d/<key-id>.pem
```

Build a signed service/UI package with:

```bash
python3 tools/ywdplugin-build.py SOURCE OUTPUT.ywdplugin \
  --sign-key PRIVATE.pem \
  --key-id publisher-key-1 \
  --publisher "Publisher Name"
```

The companion plugin repository provides `PLUGIN-DEV.sh` as an interactive wrapper around the same canonical builder. Never store a signing private key on the hotspot or commit it to either repository.

## RF ownership remains out of scope

A verified signature is not permission to control the modem directly. Current supported packages keep `rf_mode = false`.

Future RF-mode work requires a trusted-core arbitration contract with one serial/RF owner, explicit operator control, safe capture/restore of normal DMR state, and failure recovery. It must build on the existing lifecycle/signing/telemetry foundation rather than bypass it.

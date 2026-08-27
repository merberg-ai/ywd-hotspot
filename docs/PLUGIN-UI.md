# YWD-Hotspot Plugin UI v1

[← Docs index](README.md) · [Plugins](PLUGINS.md) · [Plugin Packages](PLUGIN-PACKAGES.md) · [Passive DMR Voice](DMR-VOICE.md)

Plugin UI v1 lets an installed/enabled signed plugin add a dedicated YWD-Hotspot dashboard section without injecting plugin JavaScript into the trusted dashboard DOM.

## Security model

A UI plugin is a distinct package kind:

```text
kind = ui
provider = browser-ui
rf_mode = false
```

Uploaded executable UI plugins require a trusted Ed25519 signature. They do not execute arbitrary code on the Raspberry Pi, do not receive a dedicated systemd service, do not receive device access, and do not receive arbitrary network/sudo access.

The trusted dashboard creates a separate iframe only while the plugin section is open:

```text
trusted YWD dashboard
        │
        └─ sandboxed iframe (allow-scripts only)
                │
                ├─ core Plugin UI runtime
                ├─ signed plugin ui.js
                └─ signed plugin ui.css
```

The frame omits `allow-same-origin`, forms, popups, top navigation, microphone/camera, USB, serial and geolocation permissions. Its response CSP blocks direct network/media/object/frame/form access. The plugin therefore cannot directly read the dashboard DOM, dashboard control session, Settings/System controls, other plugin pages, or arbitrary YWD API responses.

A trusted `MessageChannel` owned by the parent dashboard is the Plugin UI bridge.

## Lifecycle

A UI navigation section exists only while package/core state allows it:

```text
package AVAILABLE
package INSTALLED
master Plugin Support ON
plugin ENABLED
manifest valid
requirements satisfied
```

UI-only plugins have no Pi-side background process. Opening a section creates the sandboxed iframe; leaving destroys it and closes the bridge. Disabling/uninstalling the plugin or turning master Plugin Support OFF removes the section and destroys an open frame.

## Manifest

Plugin API/package format v1 uses flat signed source. Example:

```json
{
  "api": 1,
  "id": "example-ui",
  "name": "Example UI",
  "version": "0.1.0",
  "description": "Example browser-only plugin.",
  "trust": "experimental",
  "kind": "ui",
  "provider": "browser-ui",
  "capabilities": ["ui:section"],
  "rf_mode": false,
  "config_schema": "config.schema.json",
  "dependencies": [],
  "hardware": [],
  "ui": {
    "api": 1,
    "label": "EXAMPLE",
    "script": "ui.js",
    "style": "ui.css"
  }
}
```

Rules include:

- `ui:section` required for a dashboard section;
- safe bounded navigation label;
- simple flat `.js` / optional `.css` filenames;
- package size/file limits remain enforced;
- executable UI packages require trusted Ed25519 signatures;
- plugin HTML is not supplied by the package; trusted core creates the shell.

## Generic browser bridge

The core runtime exposes `window.ywdPlugin` inside the sandbox.

Generic v1 operations remain deliberately small, for example:

```text
plugin.ping
plugin.getState
plugin.getConfig
```

`plugin.getState` returns sanitized identity/lifecycle/capability state for that plugin only. `plugin.getConfig` returns public/redacted configuration; secret fields do not become raw browser values.

There is no generic arbitrary fetch, filesystem, shell, service-control, serial, device or arbitrary-YWD-API bridge.

## Read-only DMR activity and directory capabilities

RC3-era Plugin UI v1 also defines two generic read-only contracts for identity/activity plugins:

```text
read:dmr-activity
read:dmr-directory
```

`read:dmr-activity` exposes a bounded sanitized snapshot derived from the trusted activity collector. It includes current/recent DMR session fields such as source identity, destination, RF/network path, slot, duration and bounded RF/network quality metrics. Raw MMDVM journal text is deliberately excluded.

`read:dmr-directory` exposes bounded lookup/search against the hotspot's local RadioID-derived DMR ID database. The initial database schema resolves DMR ID to callsign only. Browser plugins do not receive the database file, filesystem path, an export endpoint, or arbitrary external-network access.

Both capabilities are checked against the installed signed manifest and current plugin enable state on every request. Disabling or uninstalling a plugin revokes access immediately. Expensive signed-manifest validation may be cached until the installed manifest changes so frequent read-only activity polling remains practical on a Pi Zero.

The browser runtime convenience methods are:

```text
plugin.readDmrActivity({limit})
plugin.lookupDmrIds([id, ...])
plugin.searchDmrDirectory(query, {limit})
```

These contracts are intentionally generic. Contact Intelligence can use them today; later traffic/scanner plugins can reuse them without gaining unrelated dashboard or RF privileges.

## Passive DMR voice capability

Current YWD Extended builds support an explicit passive DMR voice observation contract used by RX Monitor.

A compatible signed UI plugin declares the matching package/runtime requirements/capability, including the YWD Extended MMDVM runtime where required. The data path remains core-owned:

```text
MMDVM-Host (sole modem/RF owner)
  -> YWD Extended accepted voice-frame copy
  -> loopback ywd-mmdvm/voice
  -> trusted bounded voice bridge
  -> read:dmr-voice capability
  -> sandboxed browser iframe
  -> browser FEC / AMBE recovery / PCM playback
```

The plugin does **not** connect to MQTT directly and does not open `/dev/serial0`. Core validates the plugin capability and controls what frames/state cross the MessageChannel.

RX Monitor is therefore a useful example of a rich UI plugin that moves expensive decoding/audio work to the browser while keeping the Pi Zero and RF path small.

See **[DMR-VOICE.md](DMR-VOICE.md)** and **[PLUGINS.md](PLUGINS.md)**.

## Performance contract

A UI-only plugin has no background Pi service. With no plugin section open, browser plugin execution is absent and Pi cost is limited to normal core discovery/state handling and any shared trusted telemetry/voice infrastructure already required by the feature.

The iframe and plugin JavaScript execute on the browser device. This is intentional for the original Pi Zero W performance budget.

## Safety contract for future capabilities

New capabilities must be explicit trusted-core contracts. A plugin must declare them and core must validate every request. Plugin code must never work around the bridge by opening the modem, raw sockets, arbitrary dashboard endpoints, or privileged interfaces.

A valid signature/capability is not RF authority. Any future RF-control feature would require a separate core arbitration design with explicit operator intent and single-owner rollback/failure behavior.

## Useful validation flow

For a signed UI package:

```text
UPLOAD -> verify/review
  -> INSTALL
  -> ENABLE
  -> nav section appears
  -> open section / bridge online
  -> declared bridge operations work
  -> leave section / iframe destroyed
  -> DISABLE / section disappears
  -> master OFF / all plugin UI disappears
  -> ordinary DMR operation remains unchanged
```

For RX Monitor specifically, also verify the selected MMDVM runtime satisfies its YWD Extended/passive-voice requirements before expecting the voice capability to become available.

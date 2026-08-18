# YWD-Hotspot Plugin UI v1

Plugin UI v1 lets an installed and enabled signed plugin add a dedicated section to the YWD-Hotspot dashboard without injecting plugin JavaScript into the trusted dashboard DOM.

## Security model

A UI plugin is a distinct package kind:

```text
kind = ui
provider = browser-ui
rf_mode = false
```

Uploaded UI plugins require a trusted Ed25519 signature. They do not execute code on the Raspberry Pi, do not receive a systemd service, do not receive device access, and do not receive arbitrary network or sudo access.

The trusted dashboard creates a separate iframe only while the plugin section is open:

```text
trusted YWD dashboard
        |
        +-- sandboxed iframe (allow-scripts only)
                |
                +-- core Plugin UI runtime
                +-- signed plugin ui.js
                +-- signed plugin ui.css
```

The frame deliberately omits `allow-same-origin`, forms, popups, top navigation, downloads, microphone/camera, USB, serial and geolocation permissions. Its response CSP blocks direct `connect-src`, media, objects, nested frames and forms. The plugin therefore cannot read the dashboard DOM, dashboard control session, Settings controls, other plugin pages, or arbitrary YWD API responses.

A trusted `MessageChannel` owned by the parent dashboard is the only Plugin UI v1 bridge.

## Lifecycle

A UI navigation section exists only when all of these are true:

```text
package AVAILABLE
package INSTALLED
master Plugin Support ON
plugin ENABLED
manifest valid
```

For a UI-only plugin, that state is reported as ACTIVE. UI plugins have no Pi-side runtime process.

Opening the section creates the sandboxed frame. Leaving the section destroys the frame and closes its bridge channel. Disabling/uninstalling the plugin or turning master Plugin Support OFF removes the section and destroys an open frame.

## Manifest

Plugin API remains version 1 and `.ywdplugin` package format remains version 1. UI source is flat like the existing package format.

Example:

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

Rules for UI v1:

- `ui:section` is required.
- navigation label is 1-24 safe display characters.
- script/style are simple flat filenames.
- script must be `.js` and at most 256 KiB.
- style must be `.css` and at most 128 KiB.
- package-wide v1 limits still apply.
- UI plugins require a trusted Ed25519 signature when uploaded.
- plugin HTML is not supplied by the package; trusted core creates the document shell.

## Browser bridge

The core runtime exposes `window.ywdPlugin` inside the sandbox.

Plugin UI v1 generic operations are intentionally tiny:

```text
plugin.ping
plugin.getState
plugin.getConfig
```

`plugin.getState` returns sanitized identity/lifecycle/capability information for that plugin only. `plugin.getConfig` returns the same public/redacted configuration already exposed by Plugin Manager; secret fields never become raw values.

There is no generic fetch, filesystem, shell, service-control, serial, device or arbitrary YWD API bridge.

Future capabilities such as passive DMR voice observation must be added as explicit trusted-core bridge contracts. A plugin must declare the matching capability and core must validate every request. Plugin code must never work around the bridge with direct modem, raw socket or privileged access.

## Performance contract

A UI-only plugin has no background Pi service. With no browser section open, the Plugin UI execution cost is limited to normal plugin-state discovery during existing Plugin Manager/dashboard reads.

The iframe and plugin JavaScript execute on the browser device. This is intentional for the original Raspberry Pi Zero W performance budget.

## Phase-1 validation

The companion repository contains `plugins/ui-smoke-test`. It should be used before DMR Monitor work begins.

Expected test:

```text
UPLOAD signed package
 -> VERIFIED / AVAILABLE
 -> INSTALL
 -> ENABLE
 -> UI TEST nav section appears
 -> open UI TEST
 -> BRIDGE ONLINE
 -> plugin.getState/config/ping work
 -> leave section; frame is destroyed
 -> DISABLE; UI TEST disappears
 -> master OFF; UI sections disappear
 -> ordinary DMR hotspot operation remains unchanged
```

# RC3 Final UI Polish

This note tracks the final WebUI-only polish window opened after the A5 runtime/RF checkpoint and before final published-RC2 -> exact-RC3 updater and factory-image acceptance.

Core RF, MMDVM, DMRGateway, MQTT, plugin, vocoder, updater, and configuration semantics remain frozen unless a UI test exposes a real blocker.

## Settings lock behavior

When the dashboard control session is locked, the **Settings** page remains visible so the current configuration can still be inspected, but its editable controls are disabled.

The page shows:

```text
SETTINGS LOCKED · Unlock the dashboard to edit configuration.
```

The lock covers Settings inputs, selects, text areas, Save / Save & Apply, secret-change actions, location lookup, modem-default actions, configuration-history actions, and other buttons rendered inside the Settings page.

Selecting **UNLOCK** in the dashboard header and successfully authenticating restores the Settings controls. Controls that were already disabled for another UI reason retain that state; for example, inactive simplex/duplex frequency controls are not incorrectly enabled by unlocking.

Locking the dashboard again returns Settings to read-only mode.

This is a frontend usability/safety layer only. Existing server-side authenticated control checks remain authoritative.

## Consistent boolean switches

Boolean settings rendered with the dashboard's standard `.field.check` structure use the same cyber-style pill switch everywhere, including dynamically injected OLED runtime and Live DMR instrumentation settings.

Feature-specific stylesheets may still style ordinary text, number, and select inputs, but they must not replace the switch background, pill radius, checked-state glow, or mobile switch geometry. The shared switch visual properties are deliberately pinned so later generic input rules cannot turn checkbox switches back into plain rectangular boxes.

The underlying controls remain native checkboxes for data binding, keyboard behavior, accessibility, checked state, and disabled state.

### Physical acceptance for switch consistency

1. Check **Network Enabled** in the BrandMeister Settings card as the visual reference.
2. Check OLED Runtime Display booleans such as **Show Destination**, **Show Slot**, **Show Elapsed**, **Show BER**, **Show RSSI**, **Show Packet Loss**, and **Cycle Idle Pages**.
3. Check Live DMR Instrumentation booleans, including both collapsed and expanded meter/trace settings.
4. Confirm unchecked controls show the same pill-switch shape and visible left-side thumb rather than an empty rectangle.
5. Toggle representative controls on and confirm the thumb moves right with the cyan active treatment.
6. Verify the same behavior on a narrow/mobile browser and a desktop-width browser.
7. Lock the dashboard and confirm disabled switches remain visibly recognizable as switches while becoming non-interactive.

## System SSH client-key user

The appliance remote-login account is fixed to **`ywd`**. The System -> SSH Access card therefore no longer presents a username input for client-key creation.

**CREATE & EXPORT CLIENT KEY** always enrolls a fresh Ed25519 client key for the managed `ywd` account. The visible SSH status summary continues to show **Login user: ywd**.

The dashboard's privileged dispatch path also enforces this policy. A crafted request that attempts to enroll a client key for another username is rejected rather than relying only on the hidden/default WebUI value.

This does not change the established SSH security policy: factory SSH remains disabled, enabling SSH exposes public-key-only authentication on port 22, password authentication remains disabled, root SSH login remains disabled, and creating a client key does not itself enable SSH.

### Physical acceptance for fixed SSH user

1. Unlock dashboard controls and open **System -> SSH Access**.
2. Confirm the status summary shows **Login user: ywd**.
3. Confirm there is no editable SSH/SFTP username box.
4. Confirm **CREATE & EXPORT CLIENT KEY** remains visible and uses the full available row width on mobile and desktop layouts.
5. Create/export a client key and confirm the downloaded archive identifies the Linux user as `ywd`.
6. Confirm the new public key increases or preserves the expected authorized-key count for `ywd`.
7. Confirm creating the key does not change whether SSH is enabled or disabled.

## Diagnostics modernization

The original diagnostics implementation predated duplex RF support, the plugin/vocoder layers, SSH management, the DMR ID database status UI, managed Git update channels, MMDVM runtime-generation markers, passive telemetry/voice bridges, and several appliance/image services. RC3 diagnostics now collect those newer support surfaces while retaining explicit credential redaction.

### Copy Support Summary

**COPY SUPPORT SUMMARY** now refreshes and combines current dashboard, health, plugin, DMR ID, SSH, and updater state. A failure in one optional subsystem does not prevent the rest of the summary from being produced.

The copied summary includes, where available:

- installed version, branch, exact commit, source state, saved update channel, and updater status;
- core and discovered YWD service health/restart counts;
- simplex or duplex RF frequencies, color code, offsets, levels, modem serial settings, inversion, jitter, and hang timing;
- BrandMeister configured master/port plus runtime connection state and static/dynamic talkgroups;
- configuration pending state, RF-autostart/journal policy, OLED/display and WebUI settings;
- temperature, load, memory, disk, Raspberry Pi throttle history, Wi-Fi IP/signal/gateway/error/drop counters;
- DMR ID database record count/age/due state and timer state;
- plugin subsystem health plus installed/enabled/active plugin identification;
- SSH enabled/boot/policy state, fixed login user, authorized-key count, and server host-key count;
- calibration baseline/best result, previous-boot state, journal/kernel warning summary, and recent DMR traffic/quality rows.

It does **not** copy BrandMeister passwords/API keys, the WebUI control credential, Wi-Fi PSKs, or SSH key material.

Clipboard handling is deliberately compatible with the appliance's normal plain-LAN HTTP use. The dashboard first uses the modern Clipboard API when available. If browser security policy blocks that path, it falls back to a temporary hidden textarea and the legacy browser copy command. If both automatic methods are denied, the generated support summary remains visible and is automatically selected for manual copying rather than being discarded or reported as a diagnostics-generation failure.

### Diagnostic bundle v2

**CREATE DIAGNOSTIC BUNDLE** now uses a current-appliance collector instead of the original hard-coded Alpha-era service list. The archive discovers installed `ywd-*` units so newer first-party services and plugin instances are automatically represented.

The v2 archive contains a top-level `README.txt`, `support-summary.txt`, and `bundle-manifest.json` with SHA-256 hashes for collected files. Major support areas include:

- sanitized public configuration and redacted generated MMDVM-Host/DMRGateway INI files;
- build info, saved update channel/status, managed Git branch/upstream/dirty state, runtime-generation/capability markers, manifest/pins metadata, calibration/history/audit/setup/plugin state metadata;
- exact installed MMDVMHost/DMRGateway/Mosquitto/sshd binary paths, sizes, metadata, and SHA-256 hashes;
- dynamically discovered YWD services/timers/sockets, unit properties, restart/result state, failed units, and bounded per-service journals;
- current/previous kernel logs, warning-level current-boot logs, previous-boot tail, boot list, and journal disk usage;
- OS/kernel/architecture/CPU/memory/disk/mount information plus Raspberry Pi model, USB, serial/I2C device presence, temperature, and throttling;
- interface/link statistics, IPv4/IPv6 routes, listening sockets, Wi-Fi link state, rfkill state, resolver contents, and DNS resolution for the configured BrandMeister master and GitHub;
- current plugin snapshot across declarative/service/UI plugin kinds, package/state metadata, and safe filesystem inventories for plugin config/data without copying arbitrary plugin data contents;
- DMR ID database/timer/service status;
- SSH runtime policy plus fingerprints/comments only — never SSH public/private key files;
- external vocoder protocol/runtime status;
- sanitized recent dashboard activity and public MMDVM telemetry/voice bridge state, with AMBE/frame payloads deliberately excluded;
- metadata inventories for YWD configuration/state/runtime files and protected pre-update backups without copying private backup contents.

Known secret-bearing JSON keys and common free-form credential patterns are scrubbed. Command-line forms such as `--password value`, password/token/PSK assignments, bearer tokens, URL-embedded credentials, and private-key PEM/OpenSSH blocks are redacted. Wi-Fi connection profiles are never collected. Third-party/plugin logs are arbitrary text, so the archive README still instructs users to review a bundle before posting it publicly.

The diagnostics directory retains a bounded set of recent generated archives rather than accumulating bundles forever.

### Physical acceptance for diagnostics

1. Unlock dashboard controls and open **Diagnostics**.
2. Select **COPY SUPPORT SUMMARY** and confirm the preview/copy contains the exact current build/channel, correct simplex/duplex RF values, service state, BrandMeister state, DMR ID status, plugin state, SSH state, system/network health, and recent activity where available.
3. Test **COPY SUPPORT SUMMARY** from the normal plain-LAN `http://` dashboard on the mobile browser. Confirm it either reports a normal copy, reports the LAN compatibility copy path, or visibly selects the generated summary for manual copying if that browser blocks both automatic methods. In all cases the generated summary must remain intact in the preview.
4. Confirm the summary contains only `configured=true/false` style secret metadata and does not expose password/API-key/key material.
5. Select **CREATE DIAGNOSTIC BUNDLE** and allow the Pi time to collect the broader support archive.
6. Confirm the resulting archive identifies itself as diagnostic schema 2 and contains `README.txt`, `support-summary.txt`, `bundle-manifest.json`, and the expected `config/`, `state/`, `runtime/`, `runtime-state/`, `system/`, `hardware/`, `network/`, `journals/`, `plugins/`, `dmrid/`, `security/`, `vocoder/`, `update/`, and `inventory/` support areas as applicable on that appliance.
7. Confirm the manifest/build metadata reports the saved `dev` channel and exact installed development commit during this UI-polish window.
8. Review the redacted generated INIs and representative logs/state documents; confirm no BrandMeister password/API key, WebUI credential, Wi-Fi PSK, SSH key body, or AMBE voice-frame payload is present.
9. Confirm newly added/dynamically installed `ywd-*` services appear automatically in discovered service state and per-service journals when present.
10. Confirm creating/copying diagnostics does not change RF state, plugin state, SSH enabled state, configuration, or updater channel.
11. Confirm `ywd-mmdvmhost.service`, `ywd-dmrgateway.service`, and `ywd-dashboard.service` remain active and `systemctl --failed` remains clean after collection.

## Physical acceptance for Settings lock

On the configured RC3 development hotspot:

1. Load the dashboard while controls are locked.
2. Open **Settings**.
3. Confirm the lock notice is visible.
4. Confirm configuration values remain readable.
5. Confirm text fields, switches, selects, lookup actions, secret-change buttons, configuration-history actions, **SAVE**, and **SAVE & APPLY** cannot be operated.
6. Unlock the dashboard with the existing WebUI control password.
7. Confirm the lock notice disappears and normal editable Settings controls are restored.
8. Confirm simplex/duplex mode-specific disabled fields still behave correctly.
9. Make a harmless form edit, then revert or save as appropriate, to confirm normal Settings interaction still works when unlocked.
10. Lock the dashboard again and confirm Settings immediately returns to read-only mode.
11. Confirm `ywd-mmdvmhost.service`, `ywd-dmrgateway.service`, and `ywd-dashboard.service` remain active and `systemctl --failed` reports zero failed units.

Do not advance the RC3 release branch or final image candidate solely because this UI batch passes; continue the final UI-polish window until explicitly frozen for release acceptance.

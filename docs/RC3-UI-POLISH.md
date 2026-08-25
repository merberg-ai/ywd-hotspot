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

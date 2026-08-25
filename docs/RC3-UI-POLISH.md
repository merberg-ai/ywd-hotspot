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

## Physical acceptance for this tweak

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

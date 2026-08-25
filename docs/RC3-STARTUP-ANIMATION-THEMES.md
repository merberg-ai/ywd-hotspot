# RC3 selectable startup animation themes

YWD-Hotspot now supports multiple lightweight startup/loading animations. The startup readiness gate, 12-second fail-safe, fade behavior, and dashboard data requirements remain unchanged; only the visual presentation is selectable.

## Default

The default is **RF Sweep**. Existing schema-6 configurations that do not yet contain a loading-animation preference automatically use RF Sweep. No configuration schema bump is required for this presentation-only setting.

The saved preference is stored as `web.loading_animation`. The browser also remembers the last server-confirmed value so the selected visual can appear before the next `/api/config` response completes. The appliance configuration remains authoritative once loaded.

## Available themes

The Settings -> WEBUI card provides **LOADING ANIMATION** with these choices:

- **RF Sweep** (`rf_sweep`) — oscilloscope-style RF trace and horizontal scan; default.
- **Radar Scan** (`radar_scan`) — circular RF scan with transient signal blips.
- **Packet Burst** (`packet_burst`) — packet movement through RADIO -> MMDVM -> GATEWAY -> NET.
- **Digital Waterfall** (`digital_waterfall`) — compact scrolling spectrum/waterfall presentation.
- **RF Orbit** (`rf_orbit`) — RF/DMR/network/UI nodes orbit a YWD core.
- **Boot Telemetry** (`boot_telemetry`) — retro subsystem readiness lines.
- **Signal Lock** (`signal_lock`) — noisy signal bars and lock-state presentation.
- **VFO Tuning** (`vfo_tuning`) — explicitly simulated boot VFO that settles on the configured RF frequency when configuration is available. It does not retune or probe the modem.
- **DMR Frame Pulse** (`dmr_frame`) — alternating TS1/TS2 digital frame bursts.

A **PREVIEW** button displays the currently selected animation for a few seconds without saving configuration, restarting services, opening the UART, transmitting RF, or changing the actual radio frequency.

## Safety / performance

All themes are first-party HTML/CSS with small JavaScript state updates. They do not use canvas, WebGL, external graphics, or active modem probing. Animation state is decorative and cannot delay the dashboard's existing readiness/fail-safe logic.

Every theme honors the browser's `prefers-reduced-motion` setting. Reduced-motion mode presents a static representation rather than continuous movement.

The VFO theme is labeled as a simulated boot display. Before configuration is available it may show changing decorative frequencies; once configuration is loaded it settles on the configured simplex frequency or duplex hotspot TX frequency. It never commands MMDVMHost or the physical HAT.

## Settings locking

The loading-animation selector and Preview button follow the existing Settings lock policy. When dashboard controls are locked they remain visible but non-interactive. Unlocking the dashboard restores normal selection/preview behavior.

## Physical acceptance

1. Update the configured development hotspot and confirm the dashboard still exits the startup overlay normally.
2. Confirm a configuration with no explicit `web.loading_animation` uses **RF Sweep**.
3. Unlock Settings -> WEBUI and confirm the selector lists all nine themes.
4. Preview each theme and confirm the preview closes automatically and does not alter RF/service/config state.
5. Save a non-default theme, reload the dashboard, and confirm that theme is used on the next startup overlay.
6. Save **RF Sweep** again and confirm it becomes the startup visual.
7. Confirm Settings lock disables both the selector and Preview control.
8. Test at least one mobile-width and one desktop-width browser.
9. If possible, enable browser reduced-motion preference and confirm the loader remains readable without continuous animation.
10. Confirm `ywd-mmdvmhost.service`, `ywd-dmrgateway.service`, and `ywd-dashboard.service` remain active and `systemctl --failed` remains clean.

## Release status

This is an additional development UI feature after `checkpoint-dev-rc3-ui-polish-proven-pre-final-acceptance`. It does **not** change the pending release gates. The final published RC2 -> exact final RC3 updater acceptance and exact factory-image acceptance are still required before RC3 promotion.

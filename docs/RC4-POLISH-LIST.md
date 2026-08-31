# RC4 Polish List

This list tracks presentation/usability polish after the hardware-proven RC4 scanner baseline. Items here should stay low-risk and avoid reopening proven RF, DMRGateway, scanner-runtime, plugin-runtime, or network-routing behavior unless a real defect is discovered.

Baseline for this polish pass:

- hardware-proven TGIF scanner/watchlist runtime;
- TGIF Control Center action feedback visually accepted on the Raspberry Pi Zero;
- Status-page TGIF scanner sweep/hold presentation visually accepted on the Raspberry Pi Zero;
- terminal/TGIF presentation checkpoint accepted at `27fd5ed46abdd56fa2f126482376ddcf9824b633`;
- scanner-aware updater hardware gate accepted on the mature Pi Zero on 2026-08-31.

## 1. Navigation bar overflow / ugly horizontal scrollbar

**Status:** IMPLEMENTED - browser acceptance pending

The main tab row now contains enough RC4 sections that the desktop layout can overflow by a small amount, exposing the browser's native horizontal scrollbar directly under the navigation buttons. A mobile test also exposed a race where the late-created BrandMeister Talkgroups tab could remain labeled `TALKGROUPS` instead of `BM TALKGROUPS`.

### Implemented polish

- reduce desktop tab font to 12px;
- tighten horizontal button padding and inter-tab gap;
- keep labels on one line;
- hide native horizontal scrollbar chrome in Firefox/WebKit/Blink while preserving horizontal scrolling;
- use 10px nav text and compact padding on narrow/mobile displays;
- keep every tab horizontally reachable by touch/trackpad/wheel fallback;
- make the `BM TALKGROUPS` rename persistent with a MutationObserver so a late dynamic Talkgroups tab cannot miss a short startup polling window;
- bump the TGIF polish browser cache identity to `rc4-tgif-polish2` so mobile browsers do not retain the earlier presentation layer.

### Acceptance

At the normal desktop browser width used for RC4 testing:

- all tabs should fit without a visible horizontal scrollbar;
- labels such as **BM TALKGROUPS**, **RX MONITOR**, and **DIAGNOSTICS** must remain readable;
- active/hover styling must remain unchanged;
- at narrow/mobile widths, every tab must remain reachable by horizontal swipe/scroll even though the scrollbar itself is visually hidden;
- the BrandMeister tab must remain **BM TALKGROUPS** even on slower Pi Zero/mobile startup paths.

## 2. Compact terminal YWD-HOTSPOT wordmark

**Status:** ACCEPTED

The installer/updater and login presentation use the compact `$`-character YWD-HOTSPOT wordmark accepted on the Raspberry Pi Zero/PuTTY hardware gate.

Presentation owners:

- shared installer/updater banner in `bin/ywd-ui.sh`;
- `/etc/issue` and `/etc/issue.net` through `lib/branding/issue`;
- `/etc/motd` through `lib/branding/motd`;
- dynamic SSH/local login panel in `lib/console/ywd-system-info.py`.

The static and dynamic terminal surfaces identify the appliance as **Raspberry Pi DMR Hotspot Appliance** and **BrandMeister + TGIF**.

Accepted checkpoint: `27fd5ed46abdd56fa2f126482376ddcf9824b633`.

## 3. TGIF parity in GitHub/source install wizard

**Status:** IMPLEMENTED - fresh source/image acceptance pending

The interactive source installer configuration path asks whether TGIF Network should be enabled. When enabled it asks for:

- TGIF master/host;
- TGIF UDP port;
- TGIF Hotspot Security password using hidden `getpass` input.

Existing TGIF credentials are preserved when TGIF is disabled during a recovery/reconfiguration pass. The canonical config model remains the validator/source of truth.

Source regression coverage passes; the final physical fresh-install/first-run exercise remains part of the RC4 image/fresh-install gate rather than mutating the mature accepted hotspot.

## 4. TGIF details in SSH/login appliance panel

**Status:** ACCEPTED

The dynamic login panel shows, without exposing credentials:

- BrandMeister state and master endpoint;
- TGIF `ACTIVE`, `ENABLED`, or `DISABLED` state;
- TGIF master endpoint when enabled;
- TGIF scanner runtime state/current TG when scanning;
- the plain-HTTP RC4 first-boot setup URL if setup is still required.

The login hook reads only local config/runtime/systemd state; it does not make an external or dashboard HTTP request during SSH login.

Accepted checkpoint: `27fd5ed46abdd56fa2f126482376ddcf9824b633`.

## 5. TGIF scanner-aware updater / dashboard / terminal

**Status:** ACCEPTED

Treat the hardware-proven TGIF watchlist scanner as explicit runtime state during software updates instead of an invisible sidecar.

### Runtime policy

- candidate fetch/validation does **not** disturb the scanner;
- an inactive scanner remains inactive;
- an actively scanning scanner is captured and stopped immediately before live application replacement;
- after a successful compatible update, scanning is restored automatically;
- an explicit manual HOLD restores the same watched TG and manual HOLD state;
- traffic/post-call HOLD is not resurrected from stale traffic after an update and resumes as normal scanning;
- rollback restores the same pre-update scanner intent;
- a target that does not support TGIF scanning, has TGIF disabled, or has no usable watchlist leaves the scanner stopped with a warning rather than failing an otherwise successful core update;
- scanner update preservation never keys RF and does not alter DMRGateway routing.

### Presentation

The terminal GitHub updater reports whether scanning is active and that it will be paused/restored. The WebUI software-update card and confirmation dialog show scanner state/current TG and explain the preservation behavior. Update progress has explicit scanner-paused/scanner-restored phases, and completion reports whether the scanner actually resumed. The Change Channel UI uses the same policy.

### Validation

The mature Pi Zero successfully updated with the scanner running and returned to the expected scanner state with no appliance issues. `tools/tgif-update-safety-smoke.py` covers capture/quiesce/restore, manual-HOLD preservation, unsupported-target fail-soft behavior, updater ownership, dashboard status projection, and terminal presentation without external TGIF traffic or live service changes.

Checkpoint: `docs/checkpoints/rc4-tgif-scanner-update-awareness-hardware-pass.md`.

## Queue

Add subsequent RC4 polish items here before implementation so this pass stays controlled and easy to checkpoint.

# RC4 Polish List

This list tracks presentation/usability polish after the hardware-proven RC4 scanner baseline. Items here should stay low-risk and avoid reopening proven RF, DMRGateway, scanner-runtime, plugin-runtime, or network-routing behavior unless a real defect is discovered.

Baseline for this polish pass:

- hardware-proven TGIF scanner/watchlist runtime;
- TGIF Control Center action feedback visually accepted on the Raspberry Pi Zero;
- Status-page TGIF scanner sweep/hold presentation visually accepted on the Raspberry Pi Zero;
- terminal/TGIF presentation checkpoint accepted at `27fd5ed46abdd56fa2f126482376ddcf9824b633`;
- `dev` and `dev-plugins` were aligned at that checkpoint before scanner-aware updater work began.

## 1. Navigation bar overflow / ugly horizontal scrollbar

**Status:** TODO

The main tab row now contains enough RC4 sections that the desktop layout can overflow by a small amount, exposing the browser's native horizontal scrollbar directly under the navigation buttons.

Current cause in `web/style.css`:

```css
.tabs{display:flex;gap:7px;overflow:auto;padding:12px 0 10px}
.tabs button,.btn{padding:9px 11px;white-space:nowrap}
```

The desktop tab buttons also inherit the normal monospace font size; only the existing `max-width:760px` media rule explicitly reduces tab font size.

### Planned polish

- slightly reduce desktop tab font size;
- slightly tighten horizontal button padding and inter-tab gap;
- keep labels on one line;
- remove the visible native scrollbar chrome;
- preserve horizontal wheel/touch/trackpad scrolling as a fallback on narrow displays instead of clipping inaccessible tabs;
- keep mobile tap targets usable and avoid shrinking text excessively.

### Acceptance

At the normal desktop browser width used for RC4 testing:

- all tabs should fit without a visible horizontal scrollbar;
- labels such as **BM TALKGROUPS**, **RX MONITOR**, and **DIAGNOSTICS** must remain readable;
- active/hover styling must remain unchanged;
- at narrow/mobile widths, every tab must remain reachable by horizontal swipe/scroll even though the scrollbar itself is visually hidden.

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

**Status:** IMPLEMENTED - hardware update acceptance pending

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

`tools/tgif-update-safety-smoke.py` simulates capture/quiesce/restore, manual-HOLD preservation, unsupported-target fail-soft behavior, updater ownership, dashboard status projection, and terminal presentation without external TGIF traffic or live service changes.

Hardware acceptance must deliberately perform an update **with the scanner running**. A stronger gate is to place the scanner in manual HOLD on a watched TG before updating and require it to return active on the same TG in manual HOLD afterward.

## Queue

Add subsequent RC4 polish items here before implementation so this pass stays controlled and easy to checkpoint.

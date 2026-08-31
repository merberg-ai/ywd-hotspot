# RC4 Polish List

This list tracks presentation/usability polish after the hardware-proven RC4 scanner baseline. Items here should stay low-risk and avoid reopening proven RF, DMRGateway, scanner-runtime, plugin-runtime, or network-routing behavior unless a real defect is discovered.

Baseline for this polish pass:

- `dev` at `a0414d37ec65c27ac49b8c49f3a72cd6044c4513`;
- TGIF Control Center action feedback visually accepted on the Raspberry Pi Zero;
- Status-page TGIF scanner sweep/hold presentation visually accepted on the Raspberry Pi Zero;
- scanner/runtime/routing behavior remains hardware-proven and unchanged by the presentation overlay.

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

**Status:** IMPLEMENTED - awaiting appliance acceptance

Replace the older radio/letter banner and plain box headings with one compact ASCII wordmark inspired by the YWD-Plug Windows console style. The wordmark must fit an ordinary 80-column SSH/local terminal.

Presentation owners:

- shared installer/updater banner in `bin/ywd-ui.sh`;
- `/etc/issue` and `/etc/issue.net` through `lib/branding/issue`;
- `/etc/motd` through `lib/branding/motd`;
- dynamic SSH/local login panel in `lib/console/ywd-system-info.py`.

The static and dynamic terminal surfaces should identify the appliance as **Raspberry Pi DMR Hotspot Appliance** and **BrandMeister + TGIF**.

## 3. TGIF parity in GitHub/source install wizard

**Status:** IMPLEMENTED - awaiting source/appliance acceptance

The interactive source installer configuration path now asks whether TGIF Network should be enabled. When enabled it asks for:

- TGIF master/host;
- TGIF UDP port;
- TGIF Hotspot Security password using hidden `getpass` input.

Existing TGIF credentials are preserved when TGIF is disabled during a recovery/reconfiguration pass. The canonical config model remains the validator/source of truth.

## 4. TGIF details in SSH/login appliance panel

**Status:** IMPLEMENTED - awaiting appliance acceptance

The dynamic login panel should show, without exposing credentials:

- BrandMeister state and master endpoint;
- TGIF `ACTIVE`, `ENABLED`, or `DISABLED` state;
- TGIF master endpoint when enabled;
- TGIF scanner runtime state/current TG when scanning;
- the plain-HTTP first-boot setup URL if setup is still required.

The login hook reads only local config/runtime/systemd state; it does not make an external or dashboard HTTP request during SSH login.

## Queue

Add subsequent RC4 polish items here before implementation so this pass stays controlled and easy to checkpoint.

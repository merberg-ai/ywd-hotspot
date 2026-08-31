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

## Queue

Add subsequent RC4 polish items here before implementation so this pass stays controlled and easy to checkpoint.

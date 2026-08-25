# RC3 UI CSP-safe styling

During the final RC3 UI-polish pass, the new **System -> MODEM / MMDVM** panel and **Software Update -> CHANGE CHANNEL** modal were initially styled from JavaScript-created `<style>` elements.

YWD-Hotspot deliberately serves a restrictive Content-Security-Policy with `style-src 'self'`. Inline/dynamically injected style elements are therefore not a supported dashboard styling path. Browsers correctly rejected those injected rules, leaving the new components with browser-default typography/button appearance even though their functionality worked.

The accepted UI pattern is now:

- modem/MMDVM panel rules live in `web/system-ui.css`;
- software-channel modal rules live in `web/update.css`;
- both are normal first-party assets already permitted by the dashboard CSP;
- new dynamically rendered dashboard components must reuse existing first-party classes or place new rules in an externally served first-party stylesheet rather than relying on injected `<style>` blocks.

## Physical acceptance

On both a narrow/mobile browser and a desktop-width browser:

1. Open **System -> MODEM / MMDVM** and confirm normal dashboard-sized text, compact key/value rows, styled capability pills, themed expandable details, and normal maintenance buttons.
2. Open **Software Update -> CHANGE CHANNEL** while controls are unlocked.
3. Confirm `main`, `dev`, and `dev-plugins` render as dark YWD-themed channel cards rather than native white browser buttons.
4. Confirm the selected channel has the cyan active treatment and the target details/warning area remain readable without oversized typography.
5. Confirm the modal scrolls vertically on a small screen and the Cancel/Switch controls remain reachable.
6. Confirm no modem, updater, RF, configuration, or branch-switch semantics changed as part of this styling-only correction.

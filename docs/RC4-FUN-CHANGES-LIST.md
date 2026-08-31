# RC4 Fun Changes List

Status: list-building only. Do not implement these items until the list is explicitly approved for implementation.

## 1. Clean up SSH client-key export UI

- Remove the normal-WebUI `Export Server Identity` action. Keep the underlying server host-key/recovery implementation unless there is a separate reason to remove it.
- Keep the useful client-side SSH key export flow for operators who want to log in with a key.
- Rename the action to a clearer operator-facing label. Preferred wording: `CREATE & EXPORT SSH CLIENT KEY` if the action creates a fresh key; otherwise use `EXPORT SSH CLIENT KEY`.
- Fix the mobile button layout so the action does not overflow its card or clip text.
- Make the remaining SSH key-export action responsive/full-width where appropriate and consistent with other Settings/System controls.
- Add immediate busy feedback on the Pi Zero: spinner/animation plus a temporary working label such as `CREATING KEY…` / `EXPORTING…`, with duplicate-click protection until the request completes.
- Preserve existing access-control/lock requirements and do not expose private-key material through status APIs or logs.

## 2. RC4 documentation sweep

Perform a repository-wide documentation pass so the public/operator documentation matches the actual RC4 implementation instead of the older RC3 behavior.

At minimum review and update:

- top-level `README.md`;
- installation/source-install documentation;
- factory-image / first-boot documentation;
- update/channel/rollback documentation;
- settings backup/import/restore documentation;
- SSH/key-authentication documentation;
- TGIF/network documentation;
- plugin/runtime documentation where RC4 behavior changed;
- troubleshooting/help pages and any docs linked directly from the WebUI;
- screenshots/examples/text that still describe retired RC3 behavior.

RC4 features/changes that must be represented accurately include:

- simultaneous BrandMeister + TGIF support;
- dedicated conditional TGIF Control Center tab;
- TGIF talkgroup directory/search with RF `5xxxxxx` mapping and built-in numeric fallback/Parrot handling;
- appliance-persistent TGIF favorites and watchlist;
- TGIF watchlist scanner: max 10 TGs, priority/order, dwell, manual HOLD/RESUME/NEXT/STOP, post-call hold, traffic-aware hold, TUNE and DISCONNECT controls;
- scanner state/activity projection on the main Status page;
- scanner-aware updater/channel-switch behavior, including temporary quiesce and restore of active/manual-HOLD state;
- TGIF-aware terminal/login/update presentation;
- TGIF in source/GitHub install configuration and first-boot setup;
- first-boot setup portal uses normal HTTP in RC4 instead of the RC3 self-signed HTTPS flow;
- restore/import confirmation includes redacted TGIF intent without exposing credentials;
- encrypted `.ywdsettings` preservation of BrandMeister/TGIF credentials and canonical config behavior already accepted for RC4;
- SSH password-or-key configuration, managed `AllowUsers`, root/interactive-login restrictions, and client-key export workflow;
- Digital Waterfall as the fresh-install/default loading animation while preserving explicit existing theme choices;
- mobile/navigation polish including `BM TALKGROUPS` labeling and hidden native horizontal scrollbar while retaining swipe/scroll access;
- persistent RSSI mapping and truthful OLED/I2C handling/health where those are operator-relevant;
- current updater preservation guarantees for config, plugins, SSH identity/keys, RF runtime/boot policy, network state, OLED ownership, and TGIF scanner state.

Documentation rules for this pass:

- distinguish published RC3 behavior from RC4 candidate behavior when history matters;
- do not claim the RC4 first-boot HTTP image path has been physically accepted until the actual RC4 image gate is complete;
- clearly distinguish YWD's TGIF Watchlist Scanner from BrandMeister static talkgroups and from TGIF's own network-side features;
- never document or print network passwords/private keys/secrets;
- keep instructions older-ham-friendly and practical, with concrete UI labels, examples, and troubleshooting steps;
- update docs in the same implementation slice whenever a user-visible RC4 behavior changes after this sweep.

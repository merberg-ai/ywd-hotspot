# RC4 Terminal / TGIF Polish Hardware Checkpoint

Date: 2026-08-30

This checkpoint records the accepted terminal-facing RC4 polish baseline after live Raspberry Pi Zero / PuTTY validation.

Accepted implementation baseline before this checkpoint commit:

- `dev` implementation SHA: `f1035a43509290b65bce2ac11e913bbcd77f455b`
- compact dollar-block `YWD-HOTSPOT` terminal wordmark accepted as good-for-now;
- shared terminal identity is used by installer/update presentation, `/etc/issue`, `/etc/issue.net`, `/etc/motd`, and the dynamic SSH login panel;
- SSH/login appliance panel reports BrandMeister and TGIF state/master information and TGIF scanner state;
- source/GitHub configuration wizard includes optional TGIF enable/master/port/security-password prompts;
- RC4 first-run setup URL shown by the console uses HTTP rather than the retired self-signed HTTPS path;
- previously hardware-proven BM/TGIF routing, TGIF scanner, plugins, SSH, OLED and RF behavior remain outside this presentation slice.

Visual acceptance note: the first thin-outline wordmark was rejected. The replacement dense `$`-character wordmark was visually reviewed in a fresh PuTTY login and accepted as sufficiently close to the desired YWD terminal style for this RC4 phase.

Remaining polish is tracked separately in `docs/RC4-POLISH-LIST.md`; this checkpoint does not imply RC4 release freeze or version bump.

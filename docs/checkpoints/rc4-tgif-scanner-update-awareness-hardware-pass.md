# RC4 TGIF Scanner-Aware Update Hardware Pass

Hardware acceptance recorded 2026-08-31 on the mature Raspberry Pi Zero YWD-Hotspot appliance.

Accepted behavior:

- TGIF scanner remained active before the application update.
- The updater captured scanner runtime intent, quiesced the scanner only for live replacement, and restored it after the update.
- Manual HOLD/current-talkgroup intent was preserved through the update test.
- BrandMeister and TGIF remained operational after the update.
- MMDVMHost and DMRGateway remained healthy.
- No failed systemd units were observed.
- Dashboard/terminal updater awareness behaved as expected.

This checkpoint closes the first scanner-aware updater hardware gate. Future scanner/update changes should be treated as regressions against this baseline.

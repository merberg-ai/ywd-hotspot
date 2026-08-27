# YWD-Hotspot 0.2.0-rc3 Release Notes

**Status:** published, physically accepted factory-image release candidate.

RC3 integrates the physically proven DMR RX Monitor / Phase 3J path and the runtime hardening discovered while validating it on the reference Raspberry Pi Zero W + duplex MMDVM hotspot.

## Published identity

```text
Tag
  v0.2.0-rc3

Accepted source commit
  3823140b9fd4d6e73fe9066af4b2280628f62f5e

Published image
  ywd-hotspot-0.2.0-rc3.img.xz

Image SHA256
  5c3151b2a39f5a800b703d8925c53cddcf7bf49d8fcb59eda6bed30afc4413cc

Release
  https://github.com/merberg-ai/ywd-hotspot/releases/tag/v0.2.0-rc3
```

The published image is the exact compressed artifact that passed the final fresh-flash acceptance. Its public filename was normalized after the build and the renamed file was re-hashed before publication; no rebuild or recompression occurred after acceptance.

## Major RC3 changes

- DMR RX Monitor live audio over a persistent trusted AF_UNIX stream rather than repeated per-chunk HTTP decode requests;
- trusted AMBE49/FEC recovery and 10-frame / 200 ms vocoder batching in core;
- persistent external YWD Vocoder Protocol v1 client, with the mbelib decoder remaining separately installed and not bundled with YWD-Hotspot or the plugin;
- sandboxed browser plugin receives PCM only;
- selected Raspberry Pi Zero vocoder scheduling policy: `Nice=0`, `CPUWeight=200`;
- demand-gated MMDVM voice tap so extension work is active only while an installed+enabled plugin requires the relevant trusted capability;
- exact current-vs-legacy YWD Extended runtime classification so normal application updates do not silently recompile MMDVM-Host;
- explicit legacy-runtime refresh path for the current demand-gated capability set;
- safer plugin feature-runtime reconciliation with unconditional best-effort DMRGateway restoration and a longer Pi Zero mutation timeout;
- DMRGateway private MQTT telemetry corrected to `127.0.0.1:18883`, matching MMDVM-Host and the YWD loopback broker;
- encrypted settings restore fixed to inventory uploaded UI plugins correctly and reconcile the trusted feature runtime after restore/rollback;
- additional regression smokes for runtime compatibility, plugin feature lifecycle, streamed audio, telemetry endpoint consistency, settings restore, startup themes and release-critical UI wiring;
- branded readiness-gated startup overlay and RF-style animation;
- blocking stage-aware Save / Save & Apply transaction modal;
- responsive cyber-style toggle switches for boolean settings;
- source-installer terminal prompting corrected for normal SSH/console use;
- source installs explicitly establish the dashboard control password when needed;
- first-boot `.ywdsettings` restore now shows upload, verify and apply progress;
- About exposes the guarded `main` / `dev` / `dev-plugins` software-channel workflow;
- System exposes the read-only MODEM / MMDVM HAT/runtime inventory card with runtime provenance and capabilities.

## Final UI integration correction

A late live audit found that the software-channel and MODEM / MMDVM modules existed in source but were not reliably wired into the release dashboard path. RC3 now serves and bootstraps those modules explicitly.

Their styling is shipped as same-origin external CSS to comply with the dashboard `style-src 'self'` CSP. Candidate validation fails closed if the release bootstrap, required routes, privileged dispatch, or CSP-safe styling are missing.

See [`RC3-FINAL-UI-WIRING-FIX.md`](RC3-FINAL-UI-WIRING-FIX.md) for the narrow correction and acceptance checklist.

## Physical acceptance

Acceptance across the RC3 candidate sequence and final factory image covered:

- current YWD Extended runtime classification and provenance;
- extension API 2 and current patch identity;
- duplex Parrot on TS1 and TS2;
- RF -> BrandMeister and network -> RF traffic;
- RX Monitor enable/disable lifecycle;
- external vocoder Start Audio / Stop Audio lifecycle;
- vocoder returning dormant when browser audio stops;
- live audio socket cleanup after Stop Audio;
- application update preserving installed/enabled RX Monitor state;
- reboot preserving plugin demand state, voice gate, MQTT telemetry and BrandMeister connectivity;
- encrypted `.ywdsettings` backup/restore restoring uploaded RX Monitor package registration, enabled state, trusted feature runtime and an ordinary configuration delta;
- MMDVM-Host and DMRGateway private MQTT connections on `127.0.0.1:18883`;
- fresh GitHub/source installation on a Raspberry Pi 5 test host;
- first-boot settings backup upload/verify/apply feedback;
- published RC2 -> exact RC3 application updater path without silently recompiling radio binaries;
- explicit legacy YWD Extended recognition and current-runtime refresh path;
- factory-clean setup AP, Wi-Fi handoff and OLED-code onboarding;
- RF initially OFF and SSH initially OFF;
- System MODEM / MMDVM card present and refreshable;
- About CHANGE CHANNEL present with lock-state behavior and approved branch inventory;
- reboot persistence;
- zero failed systemd units at acceptance points.

The final publication acceptance record is archived at [`history/RC3-FACTORY-IMAGE-PUBLICATION-PASS.md`](history/RC3-FACTORY-IMAGE-PUBLICATION-PASS.md).

## MMDVM runtime compatibility

RC3 keeps the upstream pins unchanged:

```text
MMDVM-Host
  dea6e9b2c35857fe6f904c5092bebadb86cbf079

DMRGateway
  2a3306de313cf4c094c2031c9ced5a6858bbbfcc

YWD extension API
  2
```

Current YWD Extended patch:

```text
77c712fae4a02c59ded8bfa777e796041cc081ba445817b2f0c07c3456a40994
```

Current RC3 capability identity:

```text
slot_affinity_queued_work
dmr_pdu_route_metadata
dmr_rx_audio_events
```

The RC1/RC2 YWD Extended patch is recognized as a legacy-compatible runtime rather than silently rebuilt. Operators who need the current RC3 capability set use the explicit runtime refresh command documented in [`UPGRADING.md`](UPGRADING.md).

## External vocoder boundary

RC3 does not bundle mbelib, libmbe, AMBE Wasm, or an automatic decoder installer. The optional external decoder backend is installed separately by the operator and communicates through YWD Vocoder Protocol v1.

Normal DMR/RF operation remains independent of the optional external vocoder.

## Release-history rule

`v0.2.0-rc3`, `release/0.2.0-rc3`, and the final pre-image checkpoint preserve the exact accepted source. Post-release documentation may advance `main` and `dev` beyond the tag, but it does not redefine the tested RC3 artifact.

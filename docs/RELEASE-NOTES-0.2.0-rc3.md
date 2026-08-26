# YWD-Hotspot 0.2.0-rc3 Release Notes

**Status:** final RC3 pre-image candidate. Published RC2 -> RC3 updater acceptance is complete; the remaining release gate is the exact factory-image build and fresh-flash acceptance before public promotion.

RC3 integrates the physically proven DMR RX Monitor / Phase 3J path and the runtime hardening discovered while validating it on the reference Raspberry Pi Zero W + duplex MMDVM hotspot.

## Major RC3 changes

- DMR RX Monitor live audio over a persistent trusted AF_UNIX stream rather than repeated per-chunk HTTP decode requests;
- trusted AMBE49/FEC recovery and 10-frame / 200 ms vocoder batching in core;
- persistent external YWD Vocoder Protocol v1 client, with the mbelib decoder remaining separately installed and not bundled with YWD-Hotspot or the plugin;
- sandboxed browser plugin receives PCM only;
- selected Raspberry Pi Zero vocoder scheduling policy: `Nice=0`, `CPUWeight=200`;
- demand-gated MMDVM voice tap: `YWD_DMR_VOICE_TAP=1` is present only while an installed+enabled plugin demands `read:dmr-voice`;
- exact current-vs-legacy YWD Extended runtime classification so normal app updates do not silently recompile MMDVM-Host;
- explicit legacy-runtime refresh path for the current demand-gated voice capability;
- safer plugin feature-runtime reconciliation with unconditional best-effort DMRGateway restoration and a longer Pi Zero mutation timeout;
- DMRGateway private MQTT telemetry corrected to `127.0.0.1:18883`, matching MMDVM-Host and the YWD loopback broker;
- encrypted settings restore fixed to inventory uploaded UI plugins correctly and reconcile the trusted feature runtime after restore/rollback;
- additional regression smokes for runtime compatibility, plugin feature lifecycle, streamed audio, telemetry endpoint consistency, and settings-restore plugin/runtime behavior;
- pre-image WebUI polish with a readiness-gated branded startup overlay and RF-style animation, blocking stage-aware Save / Save & Apply transaction modal, and responsive cyber-style toggle switches for boolean settings on mobile and desktop;
- source-installer terminal prompting corrected so configuration remains visible/interactive over normal SSH/console use;
- source installs now explicitly establish the dashboard control password when one is not already configured;
- first-boot `.ywdsettings` restore now shows real upload progress plus visible verify/apply processing state;
- About exposes the guarded `main` / `dev` / `dev-plugins` software-channel workflow;
- System exposes the read-only MODEM / MMDVM HAT/runtime inventory card with current runtime provenance and capabilities.

## Final pre-image integration correction

A live audit on the already-updated Pi Zero found that the software-channel and MODEM / MMDVM modules existed in the source tree but were not reliably wired into the dashboard. The MMDVM API itself was healthy while `/modem-ui.js` returned 404.

RC3 now serves and bootstraps both late-release UI modules explicitly rather than carrying them implicitly inside the unrelated backup/restore JavaScript response. Their styling is shipped as same-origin external CSS to comply with the dashboard `style-src 'self'` CSP. Candidate validation now fails closed if the modules, routes, privileged dispatch, or CSP-safe styling are missing. The other intentional non-obvious bundles (startup themes, transactional plugin package overlay, and sandboxed plugin UI runtime) were audited at the same time.

See `docs/RC3-FINAL-UI-WIRING-FIX.md` for the narrow correction and acceptance checklist.

## Physical acceptance before final artifact test

Validated across the RC3 candidate sequence:

- current YWD Extended MMDVM runtime is exactly in sync;
- extension API 2 and current demand-gated patch identity;
- Parrot 9990 on duplex TS1 and TS2;
- RF -> BrandMeister and network -> RF traffic;
- RX Monitor enable/disable lifecycle;
- external vocoder Start Audio / Stop Audio lifecycle;
- vocoder returns dormant with browser audio stopped;
- live audio socket is removed after Stop Audio;
- application update preserves installed/enabled RX Monitor state;
- reboot preserves plugin demand state, voice gate, MQTT telemetry and BrandMeister connectivity;
- encrypted `.ywdsettings` backup/restore restores uploaded RX Monitor package registration, enabled state, trusted feature runtime and an ordinary configuration delta;
- MMDVM-Host and DMRGateway both maintain private MQTT connections on `127.0.0.1:18883`;
- zero failed systemd units at acceptance points;
- branded startup/loading overlay works and looks correct on the appliance;
- blocking Save / Save & Apply transaction feedback works correctly;
- responsive toggle-switch treatment was accepted for mobile/desktop presentation;
- fresh GitHub/source installation completed successfully on a Raspberry Pi 5 test host;
- first-boot settings backup upload/verify/apply feedback was physically exercised successfully;
- published RC2 -> exact RC3 application updater path passed without silently recompiling the radio binaries, including legacy YWD Extended recognition;
- current YWD Extended explicit refresh path was separately proven with the current extension identity and capabilities.

The final dashboard-wiring correction must be physically checked on the Pi Zero before its exact commit becomes the new immutable pre-image checkpoint.

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

The RC1/RC2 YWD Extended patch is recognized as a legacy-compatible runtime rather than silently rebuilt. Operators who need the RC3 demand-gated voice capability use the explicit runtime refresh command documented in `docs/UPGRADING.md`.

## External vocoder boundary

RC3 does not bundle mbelib, libmbe, AMBE Wasm, or an automatic decoder installer. The optional external decoder backend is installed separately by the operator and communicates through YWD Vocoder Protocol v1.

Normal DMR/RF operation remains independent of the optional external vocoder.

## Remaining release acceptance

Before RC3 is promoted to `main` and tagged:

1. physically accept the final dashboard-wiring candidate on the Pi Zero and freeze that exact source SHA;
2. build the public factory image from the exact frozen SHA using the fail-closed release wrapper;
3. verify artifact metadata, SHA-256 and xz integrity;
4. fresh-flash that exact compressed artifact and validate setup AP, Wi-Fi handoff, OLED code, first-run setup/import, RF/SSH initial policy, WebUI, current YWD Extended identity, BrandMeister/Parrot, plugin/vocoder behavior, reboot persistence, and zero failed units;
5. promote/tag/publish only the exact tested source and exact tested image assets.

No rebuild or recompression should occur after exact-artifact acceptance.

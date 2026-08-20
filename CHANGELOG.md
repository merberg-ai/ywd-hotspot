# 🗒️ Changelog

[Project README](README.md) · [Docs](docs/README.md) · [Development](docs/GITHUB-SETUP.md)

YWD-Hotspot is approaching its first 0.1.0 release. Release candidates remain subject to physical acceptance before promotion to `main`.

---

## 0.1.0-rc1 — First Release Candidate

**Status:** release candidate prepared on `dev-release-0.1.0`; full acceptance testing is still required before promotion to `main`.

Release hardening since the last Alpha development baseline includes:

- staged candidate validation expanded to require the complete System/DMR-ID maintenance payload before deployment;
- Git provenance hardened so temporary refs/branches cannot masquerade as the persistent update channel;
- RadioID database manager added to the System page with due-check, forced update, record count, age, timer/service status, and explicit unhealthy handling for empty databases;
- privileged shutdown and DMR-ID actions routed through the narrow split admin dispatcher;
- updater fixed to install the split admin bridge coherently **before** dashboard restart, eliminating the transient `unsupported admin action` race during updates;
- OLED status and CLI restart behavior now resolve the authoritative `ywd-headless-oled.service` on YWD-Hotspot OS while retaining generic-install fallback to `ywd-oled.service`;
- Talkgroup Manager confirmation ownership simplified so duplex-aware TG actions receive one correct themed confirmation without timing-based de-duplication;
- dashboard runtime identity now follows the canonical installed `VERSION` file, keeping API, journal, About, CLI, branch/ref, commit, and update-channel reporting consistent;
- README/install/development/repository/image-builder documentation refreshed for RC1;
- new `docs/BUILDING.md` added with simple source validation, fresh GitHub install/build, optional patched MMDVM voice-tap build, and full appliance-image build instructions;
- README/build/DMR voice docs now explicitly document the YWD MMDVM-Host patch used for the optional RX Monitor/passive DMR voice path.

Physically proven during release hardening before RC1 identity transition:

- updater/provenance changes;
- DMR ID manager normal/forced update and empty-database health handling;
- canonical OLED owner reporting/restart behavior;
- Talkgroup Manager confirmation cleanup;
- version/provenance consistency;
- coherent admin bridge through an application update with no transient dashboard admin error;
- MMDVMHost, DMRGateway, Dashboard and Activity service survival plus BrandMeister reconnect.

The RF baseline is intentionally unchanged by RC1 release prep:

```text
MMDVM-Host  dea6e9b2c35857fe6f904c5092bebadb86cbf079
DMRGateway  2a3306de313cf4c094c2031c9ced5a6858bbbfcc
```

Optional RX Monitor/passive voice observation continues to use:

```text
lib/mmdvm_patches/0001-ywd-dmr-voice-mqtt.patch
```

Normal application updates still do **not** recompile MMDVM-Host or DMRGateway.

## 0.1.0-alpha22.7.3-dev — Pre-main Runtime Cleanup

**Status:** physically validated on the Pi and promoted to `dev`.

- retires the bundled `system-info` and `service-heartbeat` proof packages now that the real plugin lifecycle is physically proven;
- removes their historical implicit-installed defaults from package registration;
- removes the retired MMDVM Live Telemetry plugin adapter, API panel, and polling implementation while retaining trusted core MMDVM telemetry infrastructure;
- leaves a tiny `plugin-telemetry.js` compatibility shim temporarily so browsers with an older cached `app.js` do not request a missing asset during update turnover;
- keeps RX Monitor, passive DMR voice, transactional package updates, BrandMeister routing, RF config generation, and MMDVM-Host/DMRGateway pins unchanged.

## 0.1.0-alpha22.7.2-dev — Pre-main Candidate Hardening

**Status:** physically validated on the Pi and promoted to `dev`.

- adds capability-based staged-candidate validation independent of branch name;
- plugin UI/package-update, passive voice, and telemetry markers now require complete matching runtime sets;
- incoming `UPDATE.sh` repeats candidate coherence checks before plugin quiesce or other live service work;
- fresh installs run the same coherence check;
- plugin candidate self-tests no longer depend on the historical `system-info` / `service-heartbeat` proof IDs;
- reconciles `MANIFEST.txt` with the current voice bridge and Plugin UI/Wasm runtime;
- documentation refreshed for simplex/duplex, plugin updates, passive RX audio, three update channels, and current branch policy;
- no MMDVM-Host/DMRGateway pin, RF config-generation, BrandMeister routing, or RX audio algorithm changes.

## 0.1.0-alpha22.7.1-dev — Talkgroup Modal Hotfix

**Status:** physically accepted UI hotfix.

- converts remaining Talkgroup Manager browser `confirm()` paths to YWD themed dialogs;
- includes Status-page static-TG removal, Drop QSO, Drop Dynamic, saved-set deletion/replacement, and planned TG apply confirmation;
- no BrandMeister API/routing semantics changed.

## 0.1.0-alpha22.7-dev — Transactional Plugin Updates

**Status:** physically validated on the Pi using an older RX Monitor package updated in place to the current candidate.

- upload/review distinguishes new install from update/reinstall/downgrade/replacement;
- same-ID plugin updates preserve config/data and prior valid installed/enabled intent;
- re-verifies package/signature before apply;
- blocks built-in ID replacement and incompatible kind/provenance changes;
- atomic package swap with rollback on apply failure;
- plugin update review shows current/candidate metadata and capability changes.

## 0.1.0-alpha22.6.1-dev — WebUI / Plugin Polish Proven

**Status:** physically validated.

- themed confirmation coverage expanded across dashboard/plugin/TG controls;
- `.ywdplugin` upload gained real progress, verification/review modal, and explicit install confirmation;
- redundant MMDVM Live Telemetry plugin retired while trusted core telemetry remained;
- RX Monitor presentation cleaned up with single Start/Stop Audio toggle and collapsed diagnostics;
- 22.6.1 fixed retired-plugin references left in install/update source validation;
- RX Monitor 0.4.0-alpha6.1 fixed presentation cleanup that had removed DOM nodes still used by the proven base engine.

## 0.1.0-alpha22.5-dev — Passive Voice Transport Stabilization

**Status:** physically validated; foundation for proven live RX audio.

- separates passive voice ingestion from whole-ring JSON snapshot writing using a lower-priority writer process;
- removes the large shared delivery stalls seen on the original Pi Zero;
- preserves MMDVM-Host as sole modem owner and does not rebuild the radio stack during normal updates;
- paired RX Monitor development introduced AUTO call locking, 100 ms PCM chunks, maintained jitter reservoir, non-destructive handoff, and browser timestamp-based call decisions;
- network and RF browser audio were both physically heard working; busy Worldwide TG91 AUTO playback reached useful/stable quality.

## 0.1.0-alpha22.4-dev — Adaptive RX Polling

- RX Monitor live audio polling drops from the normal 250 ms UI cadence to 100 ms while audio is active;
- manual single-timeslot monitoring proved materially better than mixing simultaneous TS1/TS2 traffic.

## 0.1.0-alpha22.3-dev — Voice Bridge Pacing Fix

- replaces selector + buffered `TextIOWrapper.readline()` consumption with nonblocking unbuffered pipe draining;
- drains all available MQTT lines on readiness instead of stranding prefetched records;
- corrected live voice cadence from roughly 30 seconds of bridge time for 10 seconds of AMBE payload toward real-time delivery.

## 0.1.0-alpha22.2-dev — Live Browser Wasm Support

- scoped Plugin UI CSP support for browser Wasm only on `read:dmr-voice` frames;
- no broad same-origin/network permission added;
- first live RX browser audio candidate installed and produced audio, exposing transport/playout jitter that later Alpha22 builds corrected.

## 0.1.0-alpha22.1-dev — Duplex BrandMeister TG Routing Fix

**Status:** physically proven.

- BrandMeister controls became mode/timeslot aware instead of hard-coding simplex slot 0;
- duplex static TG add/remove works independently on TS1 and TS2;
- route identity is `(slot,tg)` and saved TG sets preserve slot;
- Drop QSO / Drop Dynamic operate across valid duplex slots;
- multiple static TGs and update persistence were physically validated.

## 0.1.0-alpha22-dev — RX Monitor Phase 3B

- browser-side DMR A/B/C deinterleave, Golay/FEC correction, AMBE+2 descrambling, 49-bit vocoder-frame recovery, continuity counters, and bounded capture export;
- golden captures proved 500 recovered frames = 10 seconds nominal AMBE with zero gaps/unrecoverable frames on clean traffic.

## 0.1.0-alpha21.x-dev — Duplex + RX Phase 3A

- canonical config schema 6 added explicit `simplex` / `duplex` radio modes;
- duplex uses separate hotspot RX/TX frequencies and TS1 + TS2;
- update/migration preserves older simplex behavior unless explicitly changed;
- duplex RF TS1 and TS2 were physically validated;
- RX Monitor Phase 3A proved three AMBE coded blocks recovered per DMR voice burst.

## Alpha20.x — Passive DMR Voice Tap

- introduced a passive MMDVM-Host voice-frame copy to a separate loopback MQTT topic;
- kept MMDVM-Host as sole serial/RF owner;
- moved expensive MMDVM patch preparation out of normal service startup/update dependencies;
- background build/guarded activation/rollback behavior was developed specifically around the original Pi Zero compile budget.

## Alpha19 — Plugin UI v1

**Status:** physically validated.

- signed browser UI packages;
- isolated iframe execution with restrictive CSP/Permissions Policy;
- narrow MessageChannel bridge instead of trusted-dashboard DOM injection;
- UI smoke-test lifecycle physically proven before RX Monitor work began.

## Alpha16–18 — Package / Telemetry / Backup Foundations

- persistent uploaded `.ywdplugin` package source and AVAILABLE / INSTALLED / ENABLED / ACTIVE separation;
- dependency/hardware checks;
- signed service-package lifecycle;
- loopback MMDVM telemetry and normalized DMR sessions;
- encrypted/protected settings backup/restore integration;
- plugin update-safety capture/quiesce/restore across application updates.

## Alpha13–15 — Plugin Framework / Service Sandbox

- global Plugin Support master switch;
- declarative package/config framework;
- shared `ywd-plugin@.service` sandbox for service plugins;
- service lifecycle/health/log controls;
- application-update plugin quiesce/restore and rollback safety.

## Alpha11–12 — Self-update / Instrumentation / OLED Integration

- About-page software update controls and detached `ywd-update.service`;
- stage-driven update progress surviving dashboard restart;
- responsive live DMR instrumentation;
- unified OLED renderer and single-owner policy on YWD-Hotspot OS;
- GitHub-managed source/runtime separation and protected rollback backups.

## Earlier Alpha history

Earlier builds established the basic Raspberry Pi + MMDVM appliance, canonical configuration, MMDVM-Host/DMRGateway pinning, BrandMeister controls, dashboard/OLED/diagnostics, calibration, GitHub update management, and RF-state-preserving installer/updater behavior.

Detailed Alpha21/22 implementation notes are archived in [`docs/history/ALPHA21-22-DEVELOPMENT-NOTES.md`](docs/history/ALPHA21-22-DEVELOPMENT-NOTES.md); earlier detail remains available in Git history and checkpoint refs.

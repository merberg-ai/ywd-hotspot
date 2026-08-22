# 🗒️ Changelog

[Project README](README.md) · [Docs](docs/README.md) · [0.2.0-rc1 Release Notes](docs/RELEASE-NOTES-0.2.0-rc1.md)

---

## 0.2.0-rc1 — Public Appliance / Runtime Variants

**Status:** physically accepted public release candidate. The tested source is frozen at tag `v0.2.0-rc1` / commit `1575344d732994a7b54d5afc7f15a88040a274ec` and checkpoint `checkpoint-release-0.2.0-rc1-image-proven`.

Accepted public image:

```text
image_2026-08-22-ywd-hotspot-0.2.0-rc1-pi-zero-lite.img.xz
SHA256 f15232ec599cef550a23dd462ee0f30839cdde6cdf45b7e4b4b1fa929605190c
```

The exact image was flashed and physically tested on the reference Raspberry Pi Zero W + duplex MMDVM appliance before source promotion/tagging.

Starting point:

```text
checkpoint-builder-0.1.0-image-boot-proven
a5a6d9483a7cad519ee5288661447875f346b4e7
```

That earlier baseline had physically passed Pi Zero W + duplex MMDVM first boot, OLED one-time-code setup, Wi-Fi, dashboard handoff, BrandMeister, Parrot, RF, reboot/settings persistence and explicitly enabled RF autostart.

### Release changes

- introduces a true public factory-image workflow with no operator/builder preconfiguration;
- public image ships no Wi-Fi, callsign/DMR ID, BM credentials/API key, dashboard password, imported settings, RF autostart, builder SSH authorized key, or reusable SSH server host identity;
- public first boot uses the YWD setup AP followed by the OLED-code protected hotspot wizard;
- setup wizard shows finish progress/errors beside the final action and hands off to the actual configured dashboard URL;
- setup submission preserves canonical schema/config and exposes explicit simplex/duplex plus duplex RX/TX fields;
- adds persistent MMDVM runtime variants:
  - `ywd-extended` — default/recommended, exact pinned upstream plus verified YWD extension patch;
  - `upstream` — exact pinned stock upstream with no YWD extensions;
- separates compile-cache identities for Stock vs Extended;
- records MMDVM runtime/build provenance independently from application Git provenance;
- migration adopts an existing 0.1.x MMDVM binary without rebuilding/switching it, classifying Extended only when provenance supports it;
- adds plugin requirement tokens for YWD Extended/API/passive-voice capability so incompatible packages are refused cleanly;
- establishes trusted loopback MMDVM telemetry/voice infrastructure on `127.0.0.1:18883`;
- fixes MQTT daemon/client packaging and broker readiness/service ordering;
- preserves shared `/run/ywd-hotspot` runtime state across first-boot setup completion;
- adds enhanced LIVE DMR animation, BER/history presentation and data-aware RSSI behavior;
- suppresses RSSI/dBm presentation when HAT firmware reports no usable RSSI instead of guessing from BER;
- physically confirms the RC1 reference duplex HAT reports valid BER/voice data with RSSI unavailable (`0`);
- adds dashboard-managed optional SSH access:
  - factory SSH OFF;
  - unique server host keys generated on first enable;
  - public-key-only auth;
  - password/root SSH disabled;
  - one-time generated client key export;
  - server identity export clearly separated as recovery-only;
- settings backup/restore, duplex dashboard controls and SSH/static UI assets are covered by coherent candidate/static-route validation;
- public release builds generate machine-readable `BUILD-METADATA.json` and `README-FIRST.txt` beside the image;
- refreshes installation/build/OS/repository/security/plugin/passive-voice/telemetry/update documentation around the public appliance workflow.

Pinned radio identity remains:

```text
MMDVM-Host  dea6e9b2c35857fe6f904c5092bebadb86cbf079
DMRGateway  2a3306de313cf4c094c2031c9ced5a6858bbbfcc
YWD API     2
YWD patch   f3542c80d6b854552f8affea933e6cd306908eb1ebc32c0cc55f6161e0ba362a
```

Full notes: [`docs/RELEASE-NOTES-0.2.0-rc1.md`](docs/RELEASE-NOTES-0.2.0-rc1.md).

## 0.1.0 — First Stable Release

**Status:** physically accepted and promoted through `dev` to `main` after the complete RC1 acceptance matrix passed.

Physical acceptance covered:

- clean Git provenance/update-channel behavior;
- reboot persistence and zero failed systemd units;
- duplex RF TS1/TS2 including BrandMeister Parrot;
- Talkgroup Manager controls;
- RF controls and authoritative OLED ownership;
- settings save/apply and encrypted `.ywdsettings` backup/restore;
- diagnostics;
- plugin lifecycle/update persistence;
- RadioID maintenance;
- invalid-candidate refusal before live services were touched;
- desktop/mobile WebUI sweeps;
- final reboot/soak validation.

Pinned RF baseline:

```text
MMDVM-Host  dea6e9b2c35857fe6f904c5092bebadb86cbf079
DMRGateway  2a3306de313cf4c094c2031c9ced5a6858bbbfcc
```

## 0.1.0-rc1 — First Release Candidate

**Status:** physically accepted, promoted through `dev`, and used as the runtime tree for 0.1.0 stable.

RC1 release hardening established staged candidate validation, provenance/update-channel separation, RadioID management, split privileged admin behavior, authoritative OLED ownership, duplex-aware Talkgroup Manager confirmation ownership, version/provenance consistency, and the first complete release documentation/build guide.

## Alpha22.x — RX Monitor / Plugin / Duplex hardening

Major physically tested work included:

- transactional `.ywdplugin` updates;
- plugin UI/signature/sandbox polish;
- passive voice transport stabilization;
- adaptive browser RX polling/playout;
- DMR voice bridge pacing fixes;
- browser Wasm support scoped to the passive voice capability;
- duplex BrandMeister TG routing;
- browser DMR FEC/AMBE frame recovery;
- explicit simplex/duplex schema with separate duplex RX/TX;
- capability-based candidate validation.

## Alpha20–21 — Passive MMDVM observation + duplex foundation

- introduced the passive MMDVM-Host voice-frame copy while preserving MMDVM-Host as sole modem owner;
- developed guarded patch build/activation/fallback around the Pi Zero compile budget;
- added explicit duplex configuration and physically validated duplex TS1/TS2.

## Alpha13–19 — Plugin framework foundations

- Plugin Support master state;
- declarative and sandboxed service framework;
- signed browser UI packages in isolated iframes;
- package/telemetry/backup foundations;
- application-update plugin quiesce/restore safety.

## Earlier Alpha history

Earlier builds established the core Raspberry Pi + MMDVM appliance, canonical configuration, pinned radio stack, BrandMeister controls, dashboard/OLED/diagnostics, calibration, GitHub update management, and RF-state-preserving installer/updater behavior.

Detailed Alpha21/22 implementation archaeology remains in [`docs/history/ALPHA21-22-DEVELOPMENT-NOTES.md`](docs/history/ALPHA21-22-DEVELOPMENT-NOTES.md), with older detail preserved in Git history and immutable checkpoint refs.

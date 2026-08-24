# 🗒️ Changelog

[Project README](README.md) · [Docs](docs/README.md) · [0.2.0-rc3 Release Notes](docs/RELEASE-NOTES-0.2.0-rc3.md) · [0.2.0-rc2 Release Notes](docs/RELEASE-NOTES-0.2.0-rc2.md) · [0.2.0-rc1 Release Notes](docs/RELEASE-NOTES-0.2.0-rc1.md)

---

## 0.2.0-rc3 — DMR RX Monitor / Runtime Hardening

**Status:** final release candidate after physically accepted pre-image UI polish. Exact factory-image and published RC2 -> final RC3 updater acceptance remain pending before public promotion.

RC3 integrates the physically proven Phase 3J DMR RX Monitor path and the hardening found during Raspberry Pi Zero validation:

- trusted persistent AF_UNIX live-audio transport and DMR AMBE49/FEC recovery;
- 10-frame / 200 ms vocoder batching;
- external YWD Vocoder Protocol v1 decoder boundary with no bundled mbelib/libmbe/AMBE Wasm;
- sandboxed browser plugin receives PCM only;
- selected external-vocoder scheduling policy `Nice=0`, `CPUWeight=200`;
- demand-gated MMDVM voice tap controlled by installed+enabled plugin capability demand;
- current-vs-legacy YWD Extended runtime recognition and explicit refresh instead of surprise MMDVM recompilation;
- guarded plugin feature reconciliation that restores DMRGateway safely on Pi Zero transitions;
- DMRGateway private MQTT corrected to the YWD loopback broker on `127.0.0.1:18883`;
- encrypted settings restore fixed for uploaded UI-plugin package state and trusted feature-runtime reconciliation;
- new runtime, telemetry, streamed-audio and settings-restore regression smokes;
- pre-image WebUI polish adds a readiness-gated branded startup overlay with RF-style animation, a blocking stage-aware Save / Save & Apply transaction modal, and responsive cyber-style toggle switches for boolean settings on mobile and desktop.

Physical development/candidate validation covered duplex TS1/TS2 Parrot, RF/network paths, RX Monitor lifecycle/audio cleanup, reboot persistence, application-update preservation, encrypted backup/restore including a real config delta, MQTT/BrandMeister recovery, zero failed systemd units, and the final UI polish batch on the running appliance.

Final exact-artifact acceptance still requires the published RC2 -> final RC3 updater test and the exact RC3 factory-image fresh-flash/first-boot/RF/plugin/vocoder/reboot test before promotion.

Full candidate notes: [`docs/RELEASE-NOTES-0.2.0-rc3.md`](docs/RELEASE-NOTES-0.2.0-rc3.md).

## 0.2.0-rc2 — Documentation / Updater Validation

**Status:** physically tested, updater-proven, published release candidate.

Accepted identity:

```text
v0.2.0-rc2
5f0d2967ce0ed728169f7819d2bc227687d6a9b2

checkpoint-release-0.2.0-rc2-image-updater-proven
5f0d2967ce0ed728169f7819d2bc227687d6a9b2

published image
ywd-hotspot-0.2.0-rc2.img.xz

SHA256
60f74d4c6d25d6a7d9ec35aea24b97bae7a50d35f103a21dc50ee1cbe80f1649
```

RC2 intentionally retained the physically accepted RC1 RF/runtime baseline. Its release changes were documentation/version/release-packaging identity only; no MMDVM/DMRGateway pin, RF behavior, dashboard runtime, telemetry service, updater implementation, plugin runtime, systemd policy, or SSH security implementation was intentionally changed.

Acceptance proved both paths:

```text
fresh RC2 image -> PASS
published RC1 -> dashboard updater -> RC2 -> PASS
post-update reboot -> PASS
failed systemd units -> 0
```

The GitHub-facing image filename was cleaned up by copying the exact tested compressed artifact byte-for-byte and verifying the same SHA-256 before publication; the artifact was not rebuilt/recompressed after acceptance.

Full notes: [`docs/RELEASE-NOTES-0.2.0-rc2.md`](docs/RELEASE-NOTES-0.2.0-rc2.md).

## 0.2.0-rc1 — Public Appliance / Runtime Variants

**Status:** physically accepted public release candidate. The tested source is frozen at tag `v0.2.0-rc1` / commit `1575344d732994a7b54d5afc7f15a88040a274ec` and checkpoint `checkpoint-release-0.2.0-rc1-image-proven`.

Accepted public image SHA256:

```text
f15232ec599cef550a23dd462ee0f30839cdde6cdf45b7e4b4b1fa929605190c
```

RC1 established the public-appliance baseline:

- true factory image with no operator/builder preconfiguration;
- first-boot setup AP + OLED-code protected wizard;
- explicit simplex/duplex configuration with separate duplex RX/TX and TS1/TS2;
- persistent MMDVM runtime variants (`ywd-extended` default/recommended and stock `upstream`);
- separate Stock/Extended compile-cache identities and runtime provenance;
- trusted loopback MMDVM telemetry/voice infrastructure;
- data-aware BER/RSSI presentation without synthetic dBm;
- optional dashboard-managed SSH with factory SSH OFF, unique server host keys, public-key-only auth and one-time client-key export;
- coherent backup/restore, update, plugin-state and release-image validation;
- machine-readable release metadata and first-readme generation.

Pinned radio identity:

```text
MMDVM-Host  dea6e9b2c35857fe6f904c5092bebadb86cbf079
DMRGateway  2a3306de313cf4c094c2031c9ced5a6858bbbfcc
YWD API     2
YWD patch   f3542c80d6b854552f8affea933e6cd306908eb1ebc32c0cc55f6161e0ba362a
```

Full notes: [`docs/RELEASE-NOTES-0.2.0-rc1.md`](docs/RELEASE-NOTES-0.2.0-rc1.md). The completed release plan/acceptance record is archived at [`docs/history/RELEASE-PLAN-0.2.0-rc1.md`](docs/history/RELEASE-PLAN-0.2.0-rc1.md).

## 0.1.0 — First Stable Release

**Status:** physically accepted and promoted through `dev` to `main` after the complete RC1 acceptance matrix passed.

Physical acceptance covered Git provenance/update channels, reboot persistence, zero failed units, duplex RF TS1/TS2 including BrandMeister Parrot, Talkgroup Manager controls, RF/OLED ownership, settings backup/restore, diagnostics, plugin lifecycle/update persistence, RadioID maintenance, invalid-candidate refusal, desktop/mobile UI sweeps, and final reboot/soak validation.

Pinned RF baseline:

```text
MMDVM-Host  dea6e9b2c35857fe6f904c5092bebadb86cbf079
DMRGateway  2a3306de313cf4c094c2031c9ced5a6858bbbfcc
YWD API     2
YWD patch   f3542c80d6b854552f8affea933e6cd306908eb1ebc32c0cc55f6161e0ba362a
```

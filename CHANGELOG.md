# 🗒️ Changelog

[Project README](README.md) · [Docs](docs/README.md) · [0.2.0-rc2 Release Notes](docs/RELEASE-NOTES-0.2.0-rc2.md) · [0.2.0-rc1 Release Notes](docs/RELEASE-NOTES-0.2.0-rc1.md)

---

## Unreleased — Repository Housekeeping

Development after `0.2.0-rc2` is currently kept on `dev` while `main` remains frozen at the accepted RC2 public/update commit.

Repository housekeeping includes:

- pruning redundant historical working/checkpoint branch labels while retaining durable release and plugin-development anchors;
- pruning redundant pre-plugin Alpha/OS tags while preserving the final historical OS archive and plugin/RX history;
- moving the completed RC1 release plan into `docs/history/`;
- adding a historical-documentation index;
- removing the obsolete milestone-specific builder compatibility alias in favor of the unified builder entry points;
- refreshing current README/install/build/update/development/repository documentation around the accepted RC2 state and release-freeze policy.

No RF/runtime behavior change is intended by this housekeeping work.

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
```

## 0.1.0-rc1 — First Release Candidate

**Status:** physically accepted, promoted through `dev`, and used as the runtime tree for `0.1.0` stable.

This release-hardening cycle established staged candidate validation, provenance/update-channel separation, RadioID management, split privileged admin behavior, authoritative OLED ownership, duplex-aware Talkgroup Manager confirmation ownership, version/provenance consistency, and the first complete release documentation/build guide.

## Alpha19–22 — Plugin / Passive RX / Duplex hardening

Major physically tested work included:

- transactional `.ywdplugin` updates and package/UI/signature/sandbox behavior;
- passive MMDVM-Host voice-frame observation while preserving MMDVM-Host as sole modem owner;
- adaptive browser RX polling/playout and browser DMR recovery work;
- explicit duplex configuration with separate RX/TX and TS1/TS2;
- capability-based candidate validation;
- guarded YWD MMDVM extension build/activation/fallback work.

Detailed Alpha21/22 implementation archaeology remains in [`docs/history/ALPHA21-22-DEVELOPMENT-NOTES.md`](docs/history/ALPHA21-22-DEVELOPMENT-NOTES.md). Plugin/RX/voice/vocoder development checkpoints/tags are intentionally retained separately from ordinary repository cleanup.

## Earlier Alpha history

Earlier builds established the core Raspberry Pi + MMDVM appliance, canonical configuration, pinned radio stack, BrandMeister controls, dashboard/OLED/diagnostics, calibration, GitHub update management, RadioID maintenance, and RF-state-preserving installer/updater behavior. Exact detail remains available through Git history and retained historical refs.

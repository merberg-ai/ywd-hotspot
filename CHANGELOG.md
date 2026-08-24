# 🗒️ Changelog

[Project README](README.md) · [Docs](docs/README.md) · [0.2.0-rc2 Release Notes](docs/RELEASE-NOTES-0.2.0-rc2.md) · [0.2.0-rc1 Release Notes](docs/RELEASE-NOTES-0.2.0-rc1.md)

---

## Unreleased — RC3 Development

Development after `0.2.0-rc2` is integrated on `dev` while `main` remains frozen at the accepted RC2 public/update commit. `dev-plugins` starts from the same baseline and is reserved for intentionally isolated plugin/framework experiments.

Current post-RC2 work includes:

- integrating the physically proven Phase 3J DMR RX Monitor core path into `dev`;
- trusted direct AF_UNIX live-audio transport, DMR AMBE49 recovery/FEC and 10-frame/200 ms vocoder batching;
- YWD Vocoder Protocol v1 integration with a separately installed external decoder backend; no mbelib/AMBE decoder is bundled in core or the plugin;
- the selected Pi Zero scheduling policy for the known external backend (`Nice=0`, `CPUWeight=200`);
- streamed PCM delivery to the sandboxed browser plugin while preserving MMDVM-Host as the sole RF/modem owner;
- hardening candidate validation so streamed RX/audio/vocoder candidates fail closed when the audio-stream bridge, AMBE recovery helper, vocoder policy/backend scaffolding or dashboard wrapper integration is incomplete;
- bringing `MANIFEST.txt` up to date with the trusted Phase 3J/vocoder runtime and documentation assets;
- archiving completed Phase 3H planning/observation notes under `docs/history/`;
- pruning redundant historical working/checkpoint branch labels while retaining durable release and plugin/RX/vocoder anchors;
- refreshing README, plugin, vocoder, passive-voice, development and repository-policy documentation around the integrated `dev` baseline and RC3 workflow.

The Phase 3J runtime itself was physically proven before integration. The validation/manifest/documentation cleanup above is intended to strengthen candidate completeness and repository reproducibility without changing the selected RF/audio tuning baseline.

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

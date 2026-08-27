# RC3 Factory Image / Publication Acceptance

This record freezes the final public acceptance evidence for YWD-Hotspot `0.2.0-rc3`.

## Accepted source

```text
Tag
  v0.2.0-rc3

Release branch
  release/0.2.0-rc3

Accepted source commit
  3823140b9fd4d6e73fe9066af4b2280628f62f5e

Immutable pre-image checkpoint
  checkpoint-release-0.2.0-rc3-final-ui-wiring-proven-pre-image
```

The annotated `v0.2.0-rc3` tag resolves to the accepted source commit above. The release branch and immutable checkpoint remain audit references and must not be moved.

## Published factory image

```text
Filename
  ywd-hotspot-0.2.0-rc3.img.xz

SHA256
  5c3151b2a39f5a800b703d8925c53cddcf7bf49d8fcb59eda6bed30afc4413cc

GitHub release
  https://github.com/merberg-ai/ywd-hotspot/releases/tag/v0.2.0-rc3
```

The public filename was normalized after the build. The renamed compressed artifact was re-hashed on Windows and retained the same SHA-256 as the exact image that passed physical testing. No rebuild or recompression occurred after acceptance.

GitHub's uploaded release asset reports the same SHA-256 digest.

## Fresh-flash acceptance

The exact published image passed the final Raspberry Pi Zero W + MMDVM fresh-flash acceptance, including the release-critical paths introduced or hardened during RC3:

- factory-clean first boot with no builder/operator personalization;
- setup AP and Wi-Fi handoff;
- OLED one-time setup-code flow;
- first-run setup / dashboard handoff;
- dashboard authentication and control unlock;
- RF initially OFF;
- SSH initially OFF;
- System MODEM / MMDVM inventory UI and refresh path;
- About / Software Update / Change Channel UI and approved branch inventory;
- current YWD Extended runtime identity and capability classification;
- BrandMeister connectivity;
- duplex TS1 and TS2 Parrot sanity;
- settings/runtime persistence across reboot;
- private MQTT loopback health;
- zero failed systemd units at acceptance.

Earlier RC3 candidate acceptance also covered the DMR RX Monitor / Phase 3J streamed-audio path, external vocoder boundary, plugin demand gating, encrypted settings restore, current-vs-legacy runtime recognition, explicit YWD Extended refresh, and the published RC2 -> RC3 application updater path.

## Runtime identity

```text
MMDVM-Host upstream
  dea6e9b2c35857fe6f904c5092bebadb86cbf079

YWD Extended patch SHA256
  77c712fae4a02c59ded8bfa777e796041cc081ba445817b2f0c07c3456a40994

Extension API
  2

Current capabilities
  slot_affinity_queued_work
  dmr_pdu_route_metadata
  dmr_rx_audio_events

DMRGateway upstream
  2a3306de313cf4c094c2031c9ced5a6858bbbfcc
```

MMDVM-Host binary SHA values are toolchain/build specific and are not used as the release identity. Runtime acceptance is based on the exact upstream source, YWD patch identity, API/capabilities, marker state, and physical RF behavior.

## Publication

The GitHub release is published as a prerelease under `v0.2.0-rc3` with these primary assets:

```text
ywd-hotspot-0.2.0-rc3.img.xz
SHA256SUMS
BUILD-METADATA.json
README-FIRST.txt
```

`main` was promoted to the accepted RC3 source only after the exact factory artifact passed. Post-release documentation commits may move `main` and `dev` beyond the immutable tag without changing the accepted RC3 source or image identity.

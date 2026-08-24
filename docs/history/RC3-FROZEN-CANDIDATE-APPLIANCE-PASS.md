# RC3 Frozen Candidate Appliance Acceptance

The original frozen RC3 source was physically tested on the reference Raspberry Pi Zero W + duplex MMDVM appliance:

```text
release/0.2.0-rc3
cba7648d1428c07ee7592be8f423d88ae5568c99
VERSION 0.2.0-rc3
```

Physical result for that core/RF frozen source: **PASS**.

Validated:

- managed Git source clean on the exact frozen source;
- installed version `0.2.0-rc3`;
- current YWD Extended MMDVM runtime `in_sync=true`;
- patch SHA-256 `77c712fae4a02c59ded8bfa777e796041cc081ba445817b2f0c07c3456a40994`;
- extension API 2;
- capabilities `passive-dmr-voice`, `plugin-rx-monitor`, and `demand-gated-dmr-voice`;
- RX Monitor demand active with `desired=true`;
- trusted DMR voice bridge enabled/active;
- live MMDVM process inherited `YWD_DMR_VOICE_TAP=1`;
- MMDVMHost active;
- DMRGateway active;
- both MMDVM-Host and DMRGateway established to private MQTT `127.0.0.1:18883`;
- DMRGateway MQTT connection accepted;
- BrandMeister login successful;
- external mbelib vocoder inactive with browser audio stopped;
- zero failed systemd units.

The inactive legacy `ywd-oled.service` is expected on this appliance because the selected headless OLED service owns the physical display.

## Pre-image UI polish

A narrow UI-only polish window was reopened after the original frozen-source pass. The functional UI batch was physically accepted at:

```text
6593687a5ec477609483ec8cd6eaa3386bcbec7b
```

Accepted UI additions:

- readiness-gated branded startup/loading overlay with RF-style animation;
- blocking stage-aware Save / Save & Apply transaction modal;
- responsive cyber-style toggle switches replacing native checkbox presentation while preserving checkbox semantics/data binding.

The release candidate was then re-frozen after documentation/release-record updates. The exact current `release/0.2.0-rc3` ref must be used for the remaining final artifact acceptance.

## Still gated

This acceptance does **not** promote `main`, create/move `v0.2.0-rc3`, or create/move the immutable proven RC3 checkpoint.

The next step must be the final image/updater acceptance:

1. published RC2 -> exact final RC3 updater test;
2. verify ordinary app update does not silently rebuild MMDVM-Host or DMRGateway;
3. verify RC2 legacy YWD Extended classification and explicit refresh to the current demand-gated patch;
4. exact RC3 factory-image build;
5. fresh flash / first boot / setup / duplex RF / BrandMeister;
6. separately installed external vocoder backend + Alpha19 RX Monitor;
7. reboot and final RF/audio/zero-failed-units regression.

Only after those exact-artifact tests pass may `main`, the public RC3 tag, and the immutable RC3 proven checkpoint be promoted.

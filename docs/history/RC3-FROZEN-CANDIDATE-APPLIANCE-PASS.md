# RC3 Frozen Candidate Appliance Acceptance

Exact frozen source tested on the reference Raspberry Pi Zero W + duplex MMDVM appliance:

```text
release/0.2.0-rc3
cba7648d1428c07ee7592be8f423d88ae5568c99
VERSION 0.2.0-rc3
```

Physical result: **PASS**.

Validated after updating the development appliance to the exact frozen release branch:

- managed Git source clean on `release/0.2.0-rc3` at the exact commit above;
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

This acceptance does **not** promote `main`, create `v0.2.0-rc3`, or create/move the immutable proven RC3 checkpoint. Those remain gated on the published RC2 -> exact frozen RC3 updater test and exact RC3 factory-image/fresh-flash acceptance.

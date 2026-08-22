# YWD-Hotspot 0.2.0-rc2 Release Notes

**Status:** physically tested, updater-proven, published release candidate.

`0.2.0-rc2` intentionally makes **no RF/runtime feature changes**. It publishes the post-RC1 documentation refresh under a new version and, more importantly, exercises the normal YWD-Hotspot updater path against a deliberately low-risk candidate.

## Accepted identity

```text
Version
  0.2.0-rc2

Tag / source
  v0.2.0-rc2
  5f0d2967ce0ed728169f7819d2bc227687d6a9b2

Proven checkpoint
  checkpoint-release-0.2.0-rc2-image-updater-proven
  5f0d2967ce0ed728169f7819d2bc227687d6a9b2

Published image
  ywd-hotspot-0.2.0-rc2.img.xz

Image SHA256
  60f74d4c6d25d6a7d9ec35aea24b97bae7a50d35f103a21dc50ee1cbe80f1649
```

The GitHub-facing image filename was cleaned up after physical testing by copying the exact tested compressed artifact byte-for-byte. SHA-256 verification confirmed identical image contents; the image was not rebuilt or recompressed.

## Scope

RC2 contains:

- the complete post-RC1 documentation refresh;
- the dedicated `docs/SSH.md` guide for dashboard-managed SSH/SFTP access;
- corrected SSH navigation wording: `SYSTEM -> SSH ACCESS`;
- updated installation, security, backup/restore, builder, repository, release, telemetry, display, calibration, talkgroup, plugin and contributor documentation;
- corrected documentation for current loopback MQTT telemetry, RSSI availability behavior, duplex/TS1/TS2 operation, normalized DMR sessions and Plugin UI voice capability;
- release-artifact/help wording fixes for future SSH client-key exports and public image instructions;
- version/release packaging identity updated to `0.2.0-rc2`.

RC2 does **not intentionally change**:

- MMDVM-Host or DMRGateway pins;
- YWD Extended patch/API identity;
- RF configuration/application behavior;
- simplex/duplex behavior;
- telemetry services;
- dashboard runtime behavior;
- plugin runtime behavior;
- updater implementation;
- systemd service policy;
- SSH authentication/security implementation.

## Physical acceptance

The exact RC2 factory image was flashed to the reference Raspberry Pi Zero W + duplex MMDVM appliance and completed the expected first-boot/setup/runtime smoke path without release-blocking issues.

Accepted fresh-image result:

```text
[PASS] image boots
[PASS] first-boot/setup path
[PASS] dashboard
[PASS] configured RF / BrandMeister operation
[PASS] reboot
[PASS] zero failed systemd units
```

## RC1 -> RC2 updater proof

A previously published `0.2.0-rc1` appliance was booted without manual source modification and updated through the normal authenticated dashboard update flow.

The updater successfully performed the intended transition:

```text
0.2.0-rc1
   -> check main/update candidate
   -> candidate validation
   -> protected backup
   -> application replacement
   -> dashboard restart/reconnect
   -> managed source advancement
   -> 0.2.0-rc2
```

After the update the appliance reported:

```text
Installed version
  0.2.0-rc2

Source
  github / main
  5f0d2967ce0ed728169f7819d2bc227687d6a9b2

Git state
  clean

Updater
  UP TO DATE
```

A subsequent reboot preserved the RC2 source/version state and `systemctl --failed --no-pager` reported zero failed units.

This establishes a real published-image updater baseline rather than only a source-level updater test.

## RC1 baseline

The runtime baseline remains the physically accepted RC1 source/image:

```text
v0.2.0-rc1
1575344d732994a7b54d5afc7f15a88040a274ec

RC1 image SHA256
f15232ec599cef550a23dd462ee0f30839cdde6cdf45b7e4b4b1fa929605190c
```

RC2 deliberately retains that RF/runtime behavior while proving the release/update machinery around it.

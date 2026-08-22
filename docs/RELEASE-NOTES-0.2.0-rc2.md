# YWD-Hotspot 0.2.0-rc2 Release Notes

**Status:** documentation/update-system release candidate derived from the physically accepted `v0.2.0-rc1` line.

`0.2.0-rc2` intentionally makes **no RF/runtime feature changes**. Its purpose is to publish the post-RC1 documentation refresh under a new version so real appliances can exercise the normal YWD-Hotspot updater path against a deliberately low-risk candidate.

## Scope

RC2 contains:

- the complete post-RC1 documentation refresh;
- the new `docs/SSH.md` guide for dashboard-managed SSH/SFTP access;
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

## Why publish a documentation-only RC?

The updater is itself a release-critical feature. A low-risk release gives testers a useful real-world transition:

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

The expected result is that operator configuration, RF active/enabled policy, selected MMDVM runtime, plugins, SSH state/keys, BrandMeister configuration and normal dashboard behavior survive unchanged while the installed application version/source advances.

## Recommended RC1 -> RC2 updater test

Before updating, note:

```bash
ywd-hotspotctl version
ywd-hotspotctl source
sudo python3 /opt/ywd-hotspot/app/lib/runtime_build.py status
systemctl is-active ywd-mmdvmhost.service ywd-dmrgateway.service
systemctl is-enabled ywd-mmdvmhost.service ywd-dmrgateway.service
systemctl --failed --no-pager
```

Then use the authenticated dashboard update flow or:

```bash
sudo ywd-hotspotctl update --check
sudo ywd-hotspotctl update --dry-run
sudo ywd-hotspotctl update
```

After the update, verify:

- version reports `0.2.0-rc2`;
- source points to the accepted RC2 commit/update channel;
- hotspot configuration is unchanged;
- RF running/enabled state matches the pre-update state;
- selected MMDVM runtime/provenance is unchanged;
- BrandMeister still connects;
- SSH remains in the same enabled/disabled state and existing authorized keys still work when enabled;
- plugins retain compatible prior intent/state;
- dashboard reconnect completes;
- `systemctl --failed --no-pager` remains clean.

## RC1 acceptance baseline

The runtime baseline remains the physically accepted `v0.2.0-rc1` source/image:

```text
v0.2.0-rc1
1575344d732994a7b54d5afc7f15a88040a274ec
```

Accepted RC1 public image SHA256:

```text
f15232ec599cef550a23dd462ee0f30839cdde6cdf45b7e4b4b1fa929605190c
```

RC2 should be promoted/tagged only after its exact source/build and the RC1 -> RC2 updater transition are exercised successfully.

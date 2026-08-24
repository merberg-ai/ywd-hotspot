# YWD-Hotspot 0.2.0-rc3 Test Ledger

This document tracks pre-freeze RC3 validation on the integrated `dev` line. It is a working test record, not final release notes.

## Test 1 — core runtime and RF regression

Status: **PASS**

Tested on the reference Raspberry Pi Zero W + duplex MMDVM appliance.

Validated:

- managed Git source on `dev` and clean;
- current YWD Extended MMDVM runtime recognized exactly;
- extension API 2;
- current patch SHA-256 `77c712fae4a02c59ded8bfa777e796041cc081ba445817b2f0c07c3456a40994`;
- capabilities `passive-dmr-voice`, `plugin-rx-monitor`, and `demand-gated-dmr-voice`;
- MMDVMHost active;
- DMRGateway active and logged into BrandMeister;
- network -> RF and RF -> BrandMeister traffic;
- Parrot 9990;
- duplex TS1 and TS2;
- zero failed systemd units.

The development appliance predates canonical DMRGateway provenance/cache state, so `runtime_build.py status` cannot cryptographically classify that already-running gateway binary as canonical even though the running gateway reports the pinned upstream Git ID. The published factory-image path creates canonical DMRGateway provenance during `runtime_build.py install`; no provenance was fabricated for the older development binary.

## Test 2 — RX Monitor / vocoder lifecycle

Status: **PASS after blocker fix**

Validated before the blocker was found:

- enabling RX Monitor activates the trusted DMR voice bridge;
- `YWD_DMR_VOICE_TAP=1` is written and inherited by live MMDVM-Host;
- Start Audio activates the external mbelib vocoder;
- vocoder policy is `Nice=0`, `CPUWeight=200`;
- live AF_UNIX audio socket appears while streaming;
- external vocoder socket is present;
- stopping audio removes the live audio socket and allows the vocoder service to go idle;
- zero failed systemd units during streamed audio operation.

### Blocker discovered

Disabling RX Monitor could leave DMRGateway inactive on the Pi Zero. The plugin state and voice-gate file had already transitioned before the privileged feature-runtime reconcile completed.

Root cause:

- plugin mutation requests allowed only 40 seconds for the privileged reconcile;
- a Pi Zero guarded MMDVM transition may exceed that window;
- timeout could terminate the helper after DMRGateway was stopped but before restoration;
- `_guarded_mmdvm_restart()` also lacked unconditional Gateway restoration if later verification raised an exception.

Fix:

- plugin mutation timeout increased to 120 seconds;
- guarded MMDVM restart now uses best-effort `finally` restoration for a previously active DMRGateway;
- regression smoke added at `tools/plugin-feature-runtime-smoke.py`.

Physical retest after the fix:

- RX Monitor disabled cleanly;
- `desired=false`;
- bridge disabled/inactive;
- voice env file absent;
- live MMDVM process has no `YWD_DMR_VOICE_TAP`;
- MMDVMHost active;
- DMRGateway active;
- DMRGateway re-authenticated to BrandMeister successfully;
- zero failed systemd units.

## Test 3 — application update preservation + private MQTT telemetry

Status: **PASS after telemetry config fix**

Application-update preservation was tested with DMR RX Monitor installed and enabled while browser audio was stopped.

Validated:

- update from `0cc125a377...` to `923007634f...` preserved the enabled `dmr-rx-monitor` state;
- trusted feature-runtime reconciliation retained `desired=true`;
- `YWD_DMR_VOICE_TAP=1` remained inherited by live MMDVM-Host;
- voice bridge remained enabled/active;
- MMDVMHost and DMRGateway returned active;
- external mbelib vocoder remained inactive while browser audio was stopped;
- live audio socket remained absent while browser audio was stopped;
- short Start Audio / Stop Audio check returned the vocoder to inactive and removed the live audio socket;
- zero failed systemd units.

A transient pre-update `gateway_active=false` snapshot was investigated with the persistent journal. DMRGateway was not stranded: it restarted during the guarded MMDVM transition, authenticated to BrandMeister, and remained running until the application updater intentionally stopped it.

### Telemetry issue discovered

DMRGateway repeatedly logged `MQTT Error connecting: Connection refused` even though YWD's private Mosquitto broker and MMDVM telemetry path were healthy.

Root cause:

- MMDVM-Host was generated with private MQTT `127.0.0.1:18883`;
- DMRGateway was incorrectly generated with `127.0.0.1:1883`;
- the private YWD broker listens only on `127.0.0.1:18883`.

Fix:

- DMRGateway config generation now uses MQTT port `18883`;
- `tools/telemetry-config-smoke.py` verifies both publishers target the same private broker.

Physical retest on core `cf2b3d7e66246c8e78165a5d652b17e564cc8573`:

- source smoke reports MMDVM-Host on `127.0.0.1:18883`;
- source smoke reports DMRGateway on `127.0.0.1:18883`;
- generated `/etc/ywd-hotspot/DMRGateway.ini` contains `Port=18883`;
- live TCP state shows both `MMDVM-Host` and `DMRGateway` established to `127.0.0.1:18883`;
- `ywd-mqtt.service`, `ywd-mmdvmhost.service`, and `ywd-dmrgateway.service` are active;
- zero failed systemd units.

## Test 4A — reboot and runtime persistence

Status: **PASS**

Tested with DMR RX Monitor enabled and browser audio stopped on the physically proven `cf2b3d7e...` runtime.

Pre-reboot state:

- RX Monitor demand active;
- voice bridge enabled/active;
- `YWD_DMR_VOICE_TAP=1` active;
- MMDVMHost and DMRGateway active;
- external mbelib vocoder inactive;
- zero failed units.

Post-reboot validation:

- managed source remained clean on `dev @ cf2b3d7e...`;
- RX Monitor persisted enabled with `desired=true`;
- voice bridge returned enabled/active;
- live MMDVM process inherited `YWD_DMR_VOICE_TAP=1`;
- `ywd-mqtt`, MMDVMHost, DMRGateway, Dashboard and voice bridge all active;
- external mbelib vocoder remained inactive while browser audio was stopped;
- MMDVM-Host and DMRGateway each established a TCP connection to private MQTT `127.0.0.1:18883`;
- DMRGateway MQTT connection was accepted;
- DMRGateway logged into BrandMeister successfully;
- zero failed units.

A short post-boot Start Audio / Stop Audio check also passed: the vocoder returned inactive, the live audio socket disappeared, MMDVMHost and DMRGateway remained active, and zero units failed.

## Next — Test 4B

Verify encrypted portable settings backup/restore:

1. export an authenticated encrypted `.ywdsettings` backup without Wi-Fi;
2. verify the backup previews correctly with the test passphrase;
3. make reversible non-destructive state/config changes;
4. restore through the supported settings restore path with RF requested active;
5. verify core config, plugin enabled state, demand-gated voice runtime, RF autostart, MQTT publishers, BrandMeister and zero failed units return correctly;
6. verify a failed/wrong-passphrase preview does not change live state.

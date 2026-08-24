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

## Next — Test 3

Verify application-update preservation with RX Monitor installed and enabled:

1. begin from the physically proven Test 2 state;
2. enable RX Monitor but leave browser audio stopped;
3. apply the next validated `dev` application update;
4. verify plugin package/config/enabled state is preserved;
5. verify trusted feature-runtime reconciliation restores the demand-gated voice bridge;
6. verify MMDVMHost and DMRGateway return active and BrandMeister reconnects;
7. verify no failed units;
8. perform a short Start Audio / Stop Audio check after the update.

# YWD-Hotspot 0.2.0-rc3 Release Notes

**Status:** frozen release candidate; pre-freeze development regression physically passed. Exact factory-image and published RC2 -> RC3 updater acceptance are still pending before public promotion.

RC3 integrates the physically proven DMR RX Monitor / Phase 3J path and the runtime hardening discovered while validating it on the reference Raspberry Pi Zero W + duplex MMDVM hotspot.

## Major RC3 changes

- DMR RX Monitor live audio over a persistent trusted AF_UNIX stream rather than repeated per-chunk HTTP decode requests;
- trusted AMBE49/FEC recovery and 10-frame / 200 ms vocoder batching in core;
- persistent external YWD Vocoder Protocol v1 client, with the mbelib decoder remaining separately installed and not bundled with YWD-Hotspot or the plugin;
- sandboxed browser plugin receives PCM only;
- selected Raspberry Pi Zero vocoder scheduling policy: `Nice=0`, `CPUWeight=200`;
- demand-gated MMDVM voice tap: `YWD_DMR_VOICE_TAP=1` is present only while an installed+enabled plugin demands `read:dmr-voice`;
- exact current-vs-legacy YWD Extended runtime classification so normal app updates do not silently recompile MMDVM-Host;
- explicit legacy-runtime refresh path for the current demand-gated voice capability;
- safer plugin feature-runtime reconciliation with unconditional best-effort DMRGateway restoration and a longer Pi Zero mutation timeout;
- DMRGateway private MQTT telemetry corrected to `127.0.0.1:18883`, matching MMDVM-Host and the YWD loopback broker;
- encrypted settings restore fixed to inventory uploaded UI plugins correctly and reconcile the trusted feature runtime after restore/rollback;
- additional regression smokes for runtime compatibility, plugin feature lifecycle, streamed audio, telemetry endpoint consistency, and settings-restore plugin/runtime behavior.

## Pre-freeze physical acceptance

The integrated development runtime was exercised on the reference duplex appliance before the RC3 version freeze.

Validated:

- current YWD Extended MMDVM runtime is exactly in sync;
- extension API 2 and current demand-gated patch identity;
- Parrot 9990 on duplex TS1 and TS2;
- RF -> BrandMeister and network -> RF traffic;
- RX Monitor enable/disable lifecycle;
- external vocoder Start Audio / Stop Audio lifecycle;
- vocoder returns dormant with browser audio stopped;
- live audio socket is removed after Stop Audio;
- application update preserves installed/enabled RX Monitor state;
- reboot preserves plugin demand state, voice gate, MQTT telemetry and BrandMeister connectivity;
- encrypted `.ywdsettings` backup/restore restores uploaded RX Monitor package registration, enabled state, trusted feature runtime and an ordinary configuration delta;
- MMDVM-Host and DMRGateway both maintain private MQTT connections on `127.0.0.1:18883`;
- zero failed systemd units at acceptance points.

The physically exercised functional RC3 code line reached `dev @ 3e33bb82e0b3d7bdf986bf6b2cbd9295d0f679c8`; subsequent pre-freeze commits before this release branch are documentation/version/inventory-only unless otherwise noted in the test ledger.

## MMDVM runtime compatibility

RC3 keeps the upstream pins unchanged:

```text
MMDVM-Host
  dea6e9b2c35857fe6f904c5092bebadb86cbf079

DMRGateway
  2a3306de313cf4c094c2031c9ced5a6858bbbfcc

YWD extension API
  2
```

Current YWD Extended patch:

```text
77c712fae4a02c59ded8bfa777e796041cc081ba445817b2f0c07c3456a40994
```

The RC1/RC2 YWD Extended patch is recognized as a legacy-compatible runtime rather than silently rebuilt. Operators who need the RC3 demand-gated voice capability use the explicit runtime refresh command documented in `docs/UPGRADING.md`.

## External vocoder boundary

RC3 does not bundle mbelib, libmbe, AMBE Wasm, or an automatic decoder installer. The optional external decoder backend is installed separately by the operator and communicates through YWD Vocoder Protocol v1.

Normal DMR/RF operation remains independent of the optional external vocoder.

## Remaining release acceptance

Before RC3 is promoted to `main` and tagged, the exact frozen candidate must still pass:

1. candidate validation from the frozen release branch;
2. published RC2 -> exact RC3 updater test, including legacy YWD Extended recognition and explicit refresh to the current patch;
3. exact RC3 factory-image build and fresh-flash setup/boot validation;
4. separately installed external vocoder backend + Alpha19 RX Monitor package on the fresh image;
5. final reboot/RF/audio regression and zero failed units.

Only after those exact-artifact tests pass will the immutable RC3 proven checkpoint, `main`, and public `v0.2.0-rc3` tag be moved to the accepted source.

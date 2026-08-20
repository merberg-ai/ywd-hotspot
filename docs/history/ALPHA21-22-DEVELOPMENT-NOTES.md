# Alpha21–22 Development Notes

These notes are archived implementation history from the rapid Alpha21/22 development cycle. They are preserved for archaeology and rollback context; current behavior is documented in the main `docs/` guides and `CHANGELOG.md`.

---

# Alpha21 — Duplex HAT + RX Monitor Phase 3A

## Proven parent checkpoint

Alpha21 is layered on the physically proven Alpha20.3 checkpoint:

```text
ywd-hotspot
  checkpoint-alpha20.3-dmr-rx-proven
  0e414b16aebaf1fa1cae843cd024eb68bd091f2a

ywd-hotspot-plugins
  checkpoint-alpha20.3-dmr-rx-proven
  2638a0cd3571a836d1b4547fdf170dadbe7d0f18
```

That checkpoint was physically tested on the Raspberry Pi Zero W with the newly
installed duplex-capable MMDVM HAT while still configured in simplex mode. OLED,
normal DMR/BrandMeister traffic, Parrot RF/network paths, and the signed
`dmr-rx-monitor` v0.1.0 capability bridge all worked normally.

## Core build

Version:

```text
0.1.0-alpha21-dev
```

Alpha21 does not change the proven MMDVM voice-frame patch or trusted raw-frame
bridge. It adds configuration/UI behavior around that foundation.

### Simplex / duplex HAT mode

Canonical config schema 6 adds:

```json
{
  "radio": {
    "mode": "simplex",
    "frequency_hz": 446525000,
    "rx_frequency_hz": 446525000,
    "tx_frequency_hz": 446525000
  }
}
```

Migration is intentionally conservative: every pre-schema-6 installation
migrates to `mode=simplex`, with the current simplex frequency copied into the
new duplex RX/TX fields. An update therefore cannot silently switch an existing
hotspot into duplex mode.

Simplex rendering remains:

- MMDVM `Duplex=0`
- one RX/TX frequency
- DMR network slot 1 off
- DMR network slot 2 on
- BrandMeister pass-all TG/PC on slot 2

Duplex rendering becomes:

- MMDVM `Duplex=1`
- separate hotspot RX and hotspot TX frequencies
- DMR network slots 1 and 2 on
- DMRGateway `[Info]` reports duplex + both slots + matching frequencies
- BrandMeister pass-all TG/PC rules cover slots 1 and 2

The WebUI shows only the fields relevant to the selected HAT mode. Duplex mode
must always be an explicit operator choice; hardware detection never silently
changes RF mode.

### Hero branding

The live `YWD//HOTSPOT` / version overlay remains real DOM text, but its dark
rounded panel background/border/shadow are removed so it sits transparently over
the hero artwork.

## RX Monitor Phase 3A

Plugin version:

```text
dmr-rx-monitor 0.2.0
```

Phase 3A stays entirely browser-side after the proven `read:dmr-voice` bridge.
It uses the same DMR A/B/C bit-position tables as the pinned MMDVM-Host
`AMBEFEC.cpp` implementation to de-interleave each 33-byte DMR voice burst into
three 72-bit coded AMBE+2 channel/FEC blocks.

This phase validates structure and timing only:

- three coded AMBE blocks per DMR burst
- zero extraction errors during clean traffic
- approximately one DMR burst every 60 ms during continuous voice
- approximately 50 coded AMBE blocks/sec
- optional display of the three latest 72-bit block values as hex

It does **not** yet Golay/FEC-decode the blocks into 49-bit vocoder payloads and
does not produce PCM/browser audio.

## Physical validation plan

1. Update core to `0.1.0-alpha21-dev` while leaving HAT mode at Simplex.
2. Confirm MMDVMHost, DMRGateway, OLED and dashboard remain healthy.
3. Confirm the migrated config still says `radio.mode=simplex` and generated
   MMDVM config still says `Duplex=0` / slot 2 only.
4. Build/sign/install `dmr-rx-monitor-0.2.0.ywdplugin`.
5. Make a sustained Parrot test in Simplex mode. Validate RF + NET frames,
   `3 × 72-bit`, zero extraction errors and near-60 ms cadence.
6. In Settings select Duplex. Confirm only duplex RX/TX fields are exposed.
7. Enter appropriate duplex frequencies and SAVE & APPLY.
8. Confirm generated MMDVM/DMRGateway configs show `Duplex=1`, both slots and
   the selected RX/TX frequencies.
9. Program/test radios against the duplex frequency pair before considering the
   duplex path physically proven.
10. Return to Simplex if any RF behavior is unexpected; the Alpha20.3 checkpoint
    remains available as the frozen rollback foundation.

---

# 0.1.0-alpha22.1-dev

Duplex BrandMeister talkgroup-control fix layered on the physically proven Alpha22 RX Monitor Phase 3B checkpoint.

- static TG add/remove now carries explicit BrandMeister timeslots in duplex mode
- Talkgroup Manager plans track `(timeslot, talkgroup)` routes instead of TG numbers alone
- multiple static TGs can coexist on a duplex timeslot without the last add replacing the previous route
- the same TG can be planned independently on TS1 and TS2
- current static/dynamic pills show their timeslot
- Control-page static add gets TS1/TS2 selection in duplex mode
- DROP QSO and DROP ALL DYNAMIC target both duplex timeslots
- simplex behavior remains slot 0
- no MMDVM-Host, DMRGateway, voice-tap, or RX Monitor code changes

---

# Alpha22.2 — RX Monitor live-audio browser support

This development step is layered directly on the proven Alpha22.1 duplex BrandMeister talkgroup fix. It does not change MMDVM-Host, DMRGateway, modem ownership, RF frequencies, the passive voice tap, or the RX Monitor frame bridge.

## Purpose

RX Monitor Phase 3D proved that the pinned mbelib AMBE+2 decoder can run successfully in a browser and produce intelligible Web Audio playback from a known capture. Phase 3E begins live playback inside the sandboxed RX Monitor UI.

The browser decoder is WebAssembly. Ordinary Plugin UI v1 frames keep the original strict `script-src 'self'` CSP. Only an installed/enabled UI plugin that already holds the trusted `read:dmr-voice` capability receives the narrower `wasm-unsafe-eval` allowance required for WebAssembly compilation.

This does **not** grant JavaScript `unsafe-eval`, direct network access, same-origin access, device access, forms, popups, microphone/camera, serial/USB, filesystem access, or Pi-side execution.

## Safety baseline

- Parent/proven core: Alpha22.1 TG fix (`aa8f03e60860ec7bd0ff6d96462e7d3b5e26fcfd`).
- The duplex TG routing fix remains in the ancestry of this build.
- No MMDVM rebuild.
- No RX voice-tap rebuild.
- MMDVM-Host remains sole modem owner.
- Audio decode remains browser-side.

---

# Alpha22.3 RX Voice Bridge Pacing Fix

Phase 3E live browser audio proved that AMBE recovery and browser decode work, but a busy network test produced heavily choppy audio.

The attached test capture recovered every AMBE frame with zero sequence gaps and zero unrecoverable frames, while 500 recovered AMBE frames (10.00 seconds nominal audio) were assigned bridge receive timestamps spanning roughly 29.8 seconds.

Root cause: `mmdvm_voice_bridge.py` combined `selectors` with a buffered text `readline()`. A text wrapper may prefetch several MQTT lines into userspace while the selector only reports kernel-level readability. Extra complete lines could therefore remain buffered until more kernel data arrived, creating artificial 100-400 ms delivery gaps.

Alpha22.3 changes only the first-party passive voice bridge subscriber path:

- `mosquitto_sub` stdout is binary and unbuffered.
- the pipe fd is non-blocking.
- selector wakeups drain all currently available bytes with `os.read()`.
- every complete newline-delimited MQTT record already available is parsed in the same wakeup.
- the trusted runtime ring, capability checks, RF ownership model, MMDVM voice tap, DMRGateway, BrandMeister TG controls, and Plugin UI sandbox remain unchanged.

The existing RX Monitor v0.4.0-alpha1 can be re-tested after this core update. A successful test should show substantially smoother live NETWORK audio and bridge receive cadence much closer to the DMR stream rate.

---

# Alpha22.4 — RX Monitor adaptive-poll test baseline

Alpha22.4 is intentionally a core-behavior carry-forward release for the RX Monitor v0.4.0-alpha2 test.

## Core behavior

No RF-path, modem, DMRGateway, BrandMeister, voice-tap, plugin-host, WebAssembly-policy, or passive voice-bridge behavior changes are introduced beyond Alpha22.3.

The Alpha22.3 passive voice-bridge pacing fix remains unchanged. The proven duplex BrandMeister talkgroup fix remains in ancestry and saved static talkgroup state continues to be preserved by normal updates.

## Paired RX Monitor test

RX Monitor v0.4.0-alpha2 changes browser-side polling only:

- 250 ms while live audio is stopped;
- 100 ms while START AUDIO is active;
- returns to 250 ms on STOP AUDIO;
- decoder, FEC recovery, fixed 20 ms AMBE audio clock, and Pi-side trusted bridge remain unchanged.

The first comparison test should use NETWORK, the active timeslot, and a 240 ms jitter target. If stable, step down through 200 ms and 160 ms while watching underruns and intelligibility.

RF-side live-audio validation is still pending.

---

# Alpha22.5 — RX voice snapshot writer isolation

Alpha22.5 is a narrow live-RX transport build. It does not change MMDVM-Host,
DMRGateway, RF configuration, duplex talkgroup routing, the MMDVM voice tap, or
plugin capabilities.

## Change

The trusted `mmdvm_voice_bridge.py` no longer serializes/replaces the complete
bounded `voice.json` ring in the MQTT ingestion interpreter.

- The foreground process remains responsible for the non-blocking
  `mosquitto_sub` drain, validation, timestamping, and sequence assignment.
- A separate nice'd Python writer process owns the bounded runtime ring.
- Ingest forwards compact frame/status events to that writer.
- The writer coalesces snapshots to at most 10 Hz while maintaining the existing
  one-second heartbeat when idle.
- Full-ring `json.dump()` and atomic replace therefore cannot hold the ingest
  process GIL while new voice bursts are waiting in the MQTT subscriber pipe.
- The public bridge status now exposes `writer`, `snapshot_write_ms`, and
  `snapshot_write_max_ms` for diagnostics.

The runtime file schema remains schema 1 and the capability-gated DMR voice API
is unchanged.

## Test target

Pair with RX Monitor `0.4.0-alpha3` and test NETWORK audio using AUTO, then TS1
and TS2 manually, beginning at a 160 ms jitter buffer. Compare underruns and
capture timestamp gaps against Alpha22.4/alpha2.

---

# Alpha22.6 — WebUI and plugin polish

Alpha22.6 is a presentation/package-management polish build on top of the physically proven Alpha22.5 RF and DMR voice runtime. It does not change MMDVM-Host, DMRGateway, the MMDVM voice tap, the Alpha22.5 voice bridge/writer, duplex configuration, or BrandMeister routing behavior.

## Alpha22.6.1 updater hotfix

The first Alpha22.6 candidate correctly removed the retired `mmdvm-live-telemetry` package, but `UPDATE.sh`, `INSTALL.sh`, and `MANIFEST.txt` still treated that package as required source. WebUI update validation therefore stopped safely before touching the live application with `Update source missing .../mmdvm-live-telemetry/plugin.json`.

Alpha22.6.1 removes those stale package requirements, explicitly validates that the retired package is absent from the service-plugin catalog, and leaves the core `ywd-mmdvm-telemetry.service` infrastructure unchanged. The failure happened before plugin quiesce/application replacement, so the prior live RF/runtime was not modified by the failed attempt.

## Confirmation UI

- `DROP QSO` now uses the YWD in-app confirmation dialog instead of a browser-native `confirm()` dialog.
- The existing confirmation audit was rechecked. Internal navigation away from dirty Settings already uses the YWD modal, as do update, backup/restore, plugin lifecycle, RF runtime, calibration, and destructive talkgroup actions.
- Browser/tab close or reload with dirty Settings intentionally remains the browser-provided `beforeunload` prompt; browsers do not allow that prompt to be replaced safely with custom markup.

## Plugin upload/install review

The `.ywdplugin` upload flow is split into explicit stages:

1. client-side package preparation;
2. upload with a real request progress bar;
3. archive + signature verification on the hotspot;
4. a YWD review modal showing plugin identity, version, description, type, trust/signature state, RF ownership, provider/service information, and requested capabilities;
5. explicit `INSTALL PLUGIN` or `CANCEL`.

Upload no longer implicitly feels like installation. A successful upload leaves the package available until the operator explicitly confirms installation. Installation still does not enable the plugin.

## MMDVM Live Telemetry plugin retirement

The old `mmdvm-live-telemetry` service-plugin package has been retired. It was only a sandboxed journal adapter reading the already-existing core telemetry snapshot; it did not provide telemetry to the dashboard.

The core `ywd-mmdvm-telemetry.service`, trusted telemetry bridge, runtime snapshot, dashboard telemetry consumers, and RX Monitor/voice path remain intact.

During an update, the existing plugin update-safety helper quiesces plugin services before application replacement. Because the retired package is absent from the target catalog, restore leaves it disabled rather than restarting it.

## Paired RX Monitor candidate

RX Monitor `0.4.0-alpha6` is the UI-polish companion candidate. Its proven alpha5 decoder, AUTO selection, reservoir controller, 100 ms chunk scheduler, FEC path, and browser audio behavior are unchanged. Alpha6 adds only a presentation controller:

- one animated `START AUDIO` / `STOP AUDIO` toggle;
- cleaner RX audio heading/copy;
- technical audio counters collapsed under Advanced Audio Stats;
- capture/FEC and raw frame diagnostics collapsed by default;
- obsolete experimental/debug-facing notes removed from the normal view.

The Alpha22.5 + RX alpha5 proof checkpoint remains immutable at `checkpoint-alpha22.5-rx3e-alpha5-live-audio-proven`.

---

# Alpha22.7 — transactional plugin install/update

Alpha22.7 extends the uploaded `.ywdplugin` package workflow so a verified package can be installed as new source or applied as an in-place update without the manual disable → uninstall → remove-package cycle.

This build does not change MMDVM-Host, DMRGateway, duplex RF configuration, BrandMeister routing, the MMDVM voice tap, or the proven Alpha22.5 RX voice transport.

## Review first, mutate second

Package review is non-mutating. The dashboard uploads the candidate to the trusted verifier, which checks the archive format, per-file hashes, Ed25519 trust, plugin manifest, requirements, version relation, capabilities, and configuration-schema compatibility. The existing package is not replaced during review.

The review classifies a candidate as:

- `INSTALL` for a new plugin ID;
- `UPDATE` when a SemVer-compatible candidate is newer;
- `REINSTALL` for the same version;
- `DOWNGRADE` when the candidate is older;
- `REPLACE` when version ordering cannot be determined.

The modal shows current → candidate version, plugin type, signature state, requirements, configuration/data preservation, installed/enabled-state preservation, and capability additions/removals before the operator confirms anything.

## Safety boundaries

- Built-in/core plugin IDs cannot be replaced by uploaded packages.
- An uploaded plugin cannot change execution kind during an update (for example Browser UI → Service).
- Existing signer continuity is enforced. A different signing key requires an explicit remove/reinstall decision rather than silently inheriting the old package's trust.
- Capability additions are highlighted in the review UI.
- Service-plugin updates quiesce only that plugin service. Core RF/DMR services are not part of the transaction.
- Plugin data remains outside the package directory and is not touched by package replacement.
- Plugin configuration is preserved and normalized against the candidate schema. New fields receive defaults, obsolete fields are removed, and values that no longer validate are reset to the candidate field default. No plugin-supplied migration code runs as root.

## Transactional apply

`UPDATE PLUGIN` re-verifies the archive and then performs a same-filesystem staged package swap. The transaction captures the old package state, plugin enabled state, configuration, and service runtime where applicable. The candidate is validated before the old package is moved aside.

On success, the previous installed/enabled state is restored for an update. A brand-new install is registered as installed but remains disabled until explicitly enabled, matching the existing YWD plugin lifecycle.

On failure, the trusted helper restores the previous package directory, package registration state, plugin state, configuration, and service runtime before returning an error.

## First proof target

RX Monitor `0.4.0-alpha7` is intentionally the first real-world update test. With Alpha22.7 installed, leave the proven `0.4.0-alpha6.1` package installed and enabled, upload alpha7, confirm that the review shows `PLUGIN UPDATE`, then apply it without manually disabling/uninstalling/removing alpha6.1.

The RX alpha7 candidate keeps the physically proven alpha5 audio engine unchanged and advances presentation only.

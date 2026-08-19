# 🎧 Passive DMR Voice / RX Monitor Core Path

[← Docs index](README.md) · [Architecture](ARCHITECTURE.md) · [Plugins](PLUGINS.md) · [Plugin UI](PLUGIN-UI.md)

YWD-Hotspot's passive DMR voice path exists to let an isolated browser plugin observe received DMR voice without ever becoming the modem owner.

## Safety invariant

**MMDVM-Host remains the only process that owns the MMDVM serial/RF path.**

RX Monitor/plugin code never:

- opens `/dev/serial0`;
- starts a competing MMDVM process;
- obtains RF TX authority;
- receives arbitrary MQTT/network access;
- writes canonical radio configuration.

## Current path

```text
MMDVM modem / BrandMeister
          │
          ▼
      MMDVM-Host
          │ normal DMR processing continues unchanged
          ├──────────────────────────────────────────────► DMRGateway / RF
          │
          └─ accepted voice-frame copy
                    │
                    ▼
             ywd-mmdvm/voice
             loopback MQTT only
                    │
                    ▼
          trusted voice bridge
          bounded state / cursor transport
                    │
                    ▼
          read:dmr-voice capability
                    │
                    ▼
          sandboxed RX Monitor iframe
                    │
                    ├─ DMR A/B/C deinterleave
                    ├─ Golay/FEC correction
                    ├─ AMBE+2 descrambling
                    ├─ 49-bit vocoder recovery
                    └─ browser-side AMBE→PCM playback
```

The Pi performs no AMBE speech synthesis. Expensive decode/playout work happens on the browser device.

## Upstream pin and patch

Pinned MMDVM-Host commit:

```text
dea6e9b2c35857fe6f904c5092bebadb86cbf079
```

YWD patch:

```text
lib/mmdvm_patches/0001-ywd-dmr-voice-mqtt.patch
```

The patch mirrors accepted `DT_VOICE_SYNC` / `DT_VOICE` frames to the loopback observation topic while normal MMDVM processing continues.

## Build/activation model

Preparing the patched MMDVM binary is deliberately **not** part of ordinary RF startup or normal application-update critical path.

```text
ywd-mmdvm-voice-build.service
  → low-priority background preparation
  → exact pinned source + exact patch verification
  → make -j1 / resumable compatible object build
  → guarded binary install/activation
  → fallback to previously working binary on failed activation
```

The original Pi Zero can take a long time to compile MMDVM-Host, so compiler work must never block normal hotspot startup or the detached application updater.

Status helper:

```bash
sudo python3 /opt/ywd-hotspot/app/lib/mmdvm_voice_build.py status
```

Normal application updates do not recompile MMDVM-Host.

## Voice-frame envelope

The passive copy carries metadata plus the existing 33-byte DMR voice burst, for example:

```json
{
  "DMRVoice": {
    "source": "rf",
    "slot": 2,
    "src_id": 3196104,
    "dst_id": 9,
    "group": "yes",
    "seq_no": 12,
    "n": 4,
    "ber": 0,
    "rssi": 57,
    "frame_hex": "...66 lowercase hex characters..."
  }
}
```

`source` is `rf` or `network`. Headers/end/session events stay on the separate telemetry/session path.

## Trusted bridge

`lib/mmdvm_voice_bridge.py` consumes the loopback topic into bounded runtime state. It never owns the modem.

A key Pi Zero optimization is that ingestion and whole-ring JSON snapshot writing are separated: the foreground process drains/parses incoming voice data, while a lower-priority writer process coalesces `voice.json` snapshots. This removed the large shared delivery stalls seen in earlier live-audio tests.

Runtime snapshot:

```text
/run/ywd-hotspot-voice/voice.json
```

Core exposes only a bounded capability-gated view through the Plugin UI bridge.

## Browser recovery path

RX Monitor recovers three AMBE+2 codewords per DMR voice burst.

Browser work includes:

1. DMR A/B/C bit deinterleave;
2. Golay correction of protected words;
3. C1 descrambling seeded from corrected C0 data;
4. recovery of the 49-bit AMBE+2 2450 vocoder frame;
5. bounded capture/continuity diagnostics;
6. browser-side vocoder decode and Web Audio playback.

A clean continuous DMR call produces roughly:

```text
~16.67 DMR bursts/sec
3 AMBE frames/burst
≈50 AMBE frames/sec
1 AMBE frame = 20 ms
```

So 500 recovered AMBE frames represent approximately 10 seconds of nominal voice.

## Live-audio player

The proven player architecture keeps vocoder state at 20 ms frame cadence but coalesces decoded PCM into 100 ms chunks before Web Audio scheduling.

Key behavior:

- adaptive 100 ms plugin polling while audio is running;
- 5 AMBE frames / 100 ms PCM chunks;
- configurable jitter target, with the useful tested region around 140–170 ms;
- maintained playout reservoir rather than startup-only buffering;
- tiny playback-rate correction to prevent long-term browser/audio-clock drift;
- AUTO call locking so simultaneous duplex timeslots do not thrash the decoder;
- bridge timestamps used for call/handoff decisions rather than JavaScript callback delay alone;
- non-destructive call handoff so scheduled old-call audio is not abruptly discarded.

The browser's AudioContext may run at 44.1/48 kHz; the recovered voice PCM remains 8 kHz speech data and is resampled by the browser audio stack.

## Physical validation status

Physically exercised on the reference Pi Zero + duplex MMDVM setup:

- duplex TS1 and TS2 normal DMR operation while the passive observer is present;
- network-path voice-frame recovery;
- RF-path voice-frame recovery;
- 49-bit AMBE+2 recovery with zero gaps/unrecoverable frames on clean captures;
- offline AMBE→PCM intelligibility proof;
- browser decoder playback from captured frames;
- live browser audio from busy network talkgroups;
- stable AUTO operation on busy Worldwide traffic;
- live RF-side browser audio heard successfully;
- normal RF/DMRGateway ownership unchanged.

The passive RX path is therefore functionally proven. Remaining work before a public RX Monitor release is primarily packaging/source canonicalization and the separate mbelib/Wasm distribution/licensing decision—not RF-path architecture.

## Capture diagnostics

RX Monitor can export a bounded JSON ring of recovered AMBE frames with route/timestamp/FEC metadata. Because the ring is shared by observed traffic, a long network return can replace earlier RF frames before export; capture source filtering/polish is a diagnostics concern rather than an RF correctness issue.

## Licensing / distribution boundary

Development has used an mbelib-based browser decoder built locally from a pinned upstream source. The repository intentionally does **not** treat a generated decoder artifact as automatically safe to publish merely because local development works.

Before promoting RX Monitor from a local signed development candidate to a canonical public package, review the upstream licensing/patent notice and decide what source/binary distribution model the project will support.

Private signing keys remain outside both repositories and never belong on the hotspot.
